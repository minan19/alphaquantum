"""A4: OCR Service — Claude Vision ile fatura/fiş extract.

## Felsefe

KOBİ patronu en çok ne yapar? Fiş/fatura fotoğrafı çeker. WhatsApp'a
atar. Şimdi: yükle → Claude Vision otomatik field extract → ledger
entry oluştur.

## İki implementasyon

  * ClaudeVisionService — Anthropic Claude API (claude-opus-4-7)
  * OfflineOcrService — deterministic fake (tests + dev fallback)

Factory `create_ocr_service()` env'a göre seçer (LLM service paterniyle
uyumlu).

## Çıktı şeması

ExtractedInvoice:
  * vendor_name      — tedarikçi (cari)
  * vendor_tax_number — VKN (varsa)
  * invoice_no       — fatura numarası
  * issue_date       — YYYY-MM-DD
  * total_amount     — toplam tutar (KDV dahil)
  * currency         — TRY default
  * direction        — outgoing (satış) | incoming (alış)
  * category         — auto-detect: kira/yemek/yakıt/hizmet/...
  * confidence_pct   — 0-100, model güveni
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

try:
    import anthropic as _anthropic_module
    anthropic = _anthropic_module
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_MAX_TOKENS = 800


VISION_SYSTEM_PROMPT = """Sen Türkiye finansal evrak uzmanısın. Görüntüdeki fiş/fatura'dan
JSON formatında field extract et.

Çıkartılacak alanlar:
- vendor_name: Tedarikçi/firma adı
- vendor_tax_number: VKN veya TCKN (10 veya 11 hane); yoksa null
- invoice_no: Fatura/fiş numarası; yoksa null
- issue_date: YYYY-MM-DD format; bulamıyorsan null
- total_amount: KDV dahil toplam, sadece sayı (₺/TL/€ silinmiş)
- currency: TRY/USD/EUR default TRY
- direction: "outgoing" (sen sattıysan) veya "incoming" (sen aldıysan).
  Belirsizse "incoming" varsay (fiş genelde gider).
- category: Şu kategorilerden biri seç: kira, yemek, yakıt, ulaşım,
  hizmet, malzeme, vergi, sigorta, telefon, internet, ofis, diğer
- confidence_pct: 0-100, tüm field'lara olan güvenin
- notes: Türkçe kısa not (1 cümle, "ne zorlandın"/varsa)

ÇIKTI ŞABLON (sadece JSON, açıklama yok):
{
  "vendor_name": "...",
  "vendor_tax_number": "...",
  "invoice_no": "...",
  "issue_date": "2026-05-15",
  "total_amount": 1180.00,
  "currency": "TRY",
  "direction": "incoming",
  "category": "yakıt",
  "confidence_pct": 92,
  "notes": "..."
}"""


# ── Output schema ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExtractedInvoice:
    vendor_name: str | None
    vendor_tax_number: str | None
    invoice_no: str | None
    issue_date: str | None
    total_amount: float
    currency: str
    direction: str
    category: str
    confidence_pct: float
    notes: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "vendor_name": self.vendor_name,
            "vendor_tax_number": self.vendor_tax_number,
            "invoice_no": self.invoice_no,
            "issue_date": self.issue_date,
            "total_amount": self.total_amount,
            "currency": self.currency,
            "direction": self.direction,
            "category": self.category,
            "confidence_pct": self.confidence_pct,
            "notes": self.notes,
        }


# ── Protocol ───────────────────────────────────────────────────────────


class OcrServiceProtocol(Protocol):
    def extract_invoice(
        self, *, image_bytes: bytes, mime_type: str = "image/jpeg",
    ) -> ExtractedInvoice:
        ...


# ── Offline implementation ────────────────────────────────────────────


class OfflineOcrService:
    """Deterministic OCR fallback — testler + Anthropic API yokken çalışır.

    Image MD5'in ilk byte'larına göre seudo-random ama deterministic
    değerler üretir. UI testleri için yeterli.
    """

    def extract_invoice(
        self, *, image_bytes: bytes, mime_type: str = "image/jpeg",
    ) -> ExtractedInvoice:
        import hashlib
        h = hashlib.sha256(image_bytes).digest()
        # Deterministic değerler
        amount = 100 + (h[0] * 25) + (h[1] * 0.1)
        vkn_digits = "".join(str(b % 10) for b in h[:10])
        date_offset = h[10] % 60
        from datetime import datetime, timedelta
        issue_date = (
            datetime.now() - timedelta(days=date_offset)
        ).strftime("%Y-%m-%d")
        categories = [
            "yakıt", "yemek", "ofis", "hizmet", "malzeme",
            "kira", "telefon", "internet", "ulaşım", "diğer",
        ]
        category = categories[h[11] % len(categories)]
        vendors = [
            "Shell Akaryakıt", "Migros Ticaret A.Ş.", "Mega Ofis Malzemeleri",
            "Türk Telekom", "BSH Hizmet", "ABC Kırtasiye",
        ]
        vendor = vendors[h[12] % len(vendors)]
        return ExtractedInvoice(
            vendor_name=vendor,
            vendor_tax_number=vkn_digits,
            invoice_no=f"F-{h[13]:02d}{h[14]:02d}{h[15]:02d}",
            issue_date=issue_date,
            total_amount=round(amount, 2),
            currency="TRY",
            direction="incoming",
            category=category,
            confidence_pct=75.0 + (h[16] % 20),  # 75-94 arası
            notes="Offline OCR — deterministik mock çıktı.",
        )


# ── Claude Vision implementation ──────────────────────────────────────


class ClaudeVisionOcrService:
    """Production OCR — Claude API Vision."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        if not _ANTHROPIC_AVAILABLE:
            raise RuntimeError(
                "anthropic SDK not installed — pip install anthropic. "
                "Or set AQ_LLM_OFFLINE=true to use OfflineOcrService."
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def extract_invoice(
        self, *, image_bytes: bytes, mime_type: str = "image/jpeg",
    ) -> ExtractedInvoice:
        # Base64 encode the image
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=[
                {
                    "type": "text",
                    "text": VISION_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Bu fiş/fatura'dan field'ları JSON formatında çıkar.",
                        },
                    ],
                },
            ],
        )

        # Find first text block
        text_response = ""
        for block in response.content:
            if getattr(block, "type", None) == "text":
                text_response = str(block.text)
                break

        return self._parse_json_response(text_response)

    @staticmethod
    def _parse_json_response(text: str) -> ExtractedInvoice:
        """Claude'un cevabını JSON'a çevir. Robust parsing — markdown
        code block veya açıklama metni varsa temizler."""
        cleaned = text.strip()
        # Remove markdown code fence if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        # Try to find {...} block if extra text
        if not cleaned.startswith("{"):
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start >= 0 and end > start:
                cleaned = cleaned[start:end + 1]
        try:
            data = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            # Fallback minimal
            return ExtractedInvoice(
                vendor_name=None, vendor_tax_number=None, invoice_no=None,
                issue_date=None, total_amount=0.0, currency="TRY",
                direction="incoming", category="diğer",
                confidence_pct=0.0,
                notes="OCR JSON parse hatası — manuel doldurun.",
            )
        return ExtractedInvoice(
            vendor_name=data.get("vendor_name"),
            vendor_tax_number=data.get("vendor_tax_number"),
            invoice_no=data.get("invoice_no"),
            issue_date=data.get("issue_date"),
            total_amount=float(data.get("total_amount", 0) or 0),
            currency=str(data.get("currency", "TRY") or "TRY").upper(),
            direction=str(data.get("direction", "incoming") or "incoming"),
            category=str(data.get("category", "diğer") or "diğer"),
            confidence_pct=float(data.get("confidence_pct", 0) or 0),
            notes=data.get("notes"),
        )


# ── Factory ────────────────────────────────────────────────────────────


def create_ocr_service() -> OcrServiceProtocol:
    """Env'a göre OCR service oluştur.

    AQ_LLM_OFFLINE=true   → OfflineOcrService (test + dev için)
    ANTHROPIC_API_KEY set → ClaudeVisionOcrService
    Yoksa                 → OfflineOcrService (graceful fallback)
    """
    if os.getenv("AQ_LLM_OFFLINE", "").lower() in ("1", "true", "yes"):
        return OfflineOcrService()
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or not _ANTHROPIC_AVAILABLE:
        return OfflineOcrService()
    try:
        return ClaudeVisionOcrService(api_key=api_key)
    except Exception:
        return OfflineOcrService()
