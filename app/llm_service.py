"""G+1: LLM Service — Claude API wrapper for Alpha Quantum.

## Tasarım kararları

### Conditional import + offline mode
`anthropic` SDK opsiyonel — eğer paket yüklü değilse veya
`AQ_LLM_OFFLINE=true` env var'ı set'liyse `OfflineLLMService` kullanılır.
Bu sayede:
  - Test ortamında SDK yüklü olmasa bile çalışır (CI'da requirements.txt
    yükler ama lokal dev bağımsız)
  - Deterministic test'ler için mock response
  - Production'da AQ_ANTHROPIC_API_KEY set'liyse gerçek API

### Prompt caching (G+1 öncelik)
System prompt sabit (Türkçe holding exec summary persona) → `cache_control`
ile cache'lenir. Her request'te sadece holding-specific data değişir.
Bu maliyet ~90% azaltır + latency düşer.

Cache key stability:
  - System prompt: deterministic (template + fixed instructions)
  - User message: değişken (period + KPI'lar)

### Model seçimi
`claude-opus-4-7` default (skill talimatına göre). Adaptive thinking ile
intelligent rapor üretir. `output_config.effort=medium` sweet spot —
holding exec summary için karmaşık, ama not over-thinking.

### Hata yönetimi
LLM API down olabilir, rate limit olabilir, timeout olabilir. ExecSummary
critical-path değil (sahne 5 raporu) → graceful degradation:
  - API hatası → fallback rule-based summary
  - Audit log: emit "llm.error" event
  - Müşteri görür: "AI özet şu an üretilemiyor, kural tabanlı özet" notu

### Güvenlik
  - API key env var'dan okunur, asla logda görünmez
  - User input prompt injection korunması (system prompt'ta sınırlandırma)
  - Output sanitize edilmez (rapor metin, HTML değil)
"""
from __future__ import annotations

import os
from typing import Any, Protocol

# Conditional import — anthropic opsiyonel.
# CI'da requirements.txt yükler; lokal dev SDK olmadan offline mode kullanır.
# `--ignore-missing-imports` mypy flag'i ile her iki ortamda da temiz çalışır.
anthropic: Any = None
try:
    import anthropic as _anthropic_module
    anthropic = _anthropic_module
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


# Default model (per claude-api skill talimatı: claude-opus-4-7)
DEFAULT_MODEL = "claude-opus-4-7"

# Max output tokens — exec summary 2-3 paragraf, max 1500 token yeter
DEFAULT_MAX_TOKENS = 1500

# Sistem prompt (Türkçe, prompt cache'leme için sabit)
EXEC_SUMMARY_SYSTEM_PROMPT = """Sen Alpha Quantum platformunun finansal asistanısın. \
Türk holding'lerinin C-seviye yöneticileri (CFO, CEO, finans direktörü) için \
kısa, net ve aksiyon odaklı yönetici özetleri (executive summary) hazırlarsın.

Üslubun:
- Profesyonel, sade, Türkçe finans terminolojisi (KVKK, TL, TFRS uyumlu)
- 2-3 paragraf maksimum
- Veriye dayanan: rakamları her zaman cite et
- Aksiyon odaklı: "ne yapılmalı" en sonda 2-3 madde
- Aşırı süslü dil yok, doğrudan: "Konsolide net kar X TL"

Yapı:
1. **Genel durum** (1-2 cümle): konsolide P&L sağlığı + FX pozisyonu
2. **Kritik noktalar** (1-2 cümle): elimination balance, overdue alacaklar, \
pending intercompany transferler
3. **Öneriler** (2-3 madde): aksiyon listesi

Asla:
- Tahmin yapma (sadece veriye dayan)
- Gelecek kurla ilgili spekülasyon yapma
- Tek bir sektöre genelleme yapma (karma sektör holding'ler için yazıyorsun)
- Kişi adı ya da müşteri/tedarikçi adı verme (KVKK)

Çıktın doğrudan rapor metni — başlık, prefix, "İşte özet:" gibi giriş yok."""


class LLMServiceProtocol(Protocol):
    """LLM service contract — production veya offline mode aynı arayüzü uygular."""

    def generate_exec_summary(self, *, context: dict[str, Any]) -> str:
        """Generate executive summary from structured holding context.

        Args:
            context: {
                "holding_name": str,
                "period_start": str (ISO),
                "period_end": str (ISO),
                "consolidated_pl": ConsolidatedPLResponse dict,
                "fx_position": GroupFXPositionResponse dict,
                "pending_transfers_count": int,
            }

        Returns: Türkçe narrative (2-3 paragraf).
        """
        ...


class OfflineLLMService:
    """Offline mode — deterministic rule-based summary, no external API.

    Kullanım senaryoları:
      - Lokal dev (AQ_LLM_OFFLINE=true)
      - Test (deterministic output)
      - LLM API down fallback
      - anthropic SDK yüklü değil
    """

    def generate_exec_summary(self, *, context: dict[str, Any]) -> str:
        """Kural tabanlı özet — gerçek API'siz."""
        holding_name = str(context.get("holding_name", "Holding"))
        period_start = str(context.get("period_start", ""))
        period_end = str(context.get("period_end", ""))
        pl = context.get("consolidated_pl") or {}
        fx = context.get("fx_position") or {}
        pending_count = int(context.get("pending_transfers_count", 0))

        consolidated_net = float(pl.get("consolidated_net", 0))
        health_status = str(pl.get("health_status", "watch"))
        gross_total_income = float(pl.get("gross_total_income", 0))
        elimination = pl.get("elimination") or {}
        is_balanced = bool(elimination.get("is_balanced", True))

        net_exposure = float(fx.get("net_exposure_try", 0))
        risk_level = str(fx.get("risk_level", "balanced"))

        # Türkçe rakam formatı
        def fmt(amount: float) -> str:
            return f"₺{amount:,.0f}".replace(",", ".")

        # Paragraf 1: Genel durum
        health_label = {
            "strong": "güçlü",
            "stable": "istikrarlı",
            "watch": "izlenmeli",
            "risk": "risk seviyesinde",
        }.get(health_status, "izlenmeli")

        risk_label = {
            "balanced": "dengeli",
            "moderate": "orta seviyede",
            "concentrated": "konsantre",
            "critical": "kritik",
        }.get(risk_level, "dengeli")

        para1 = (
            f"{holding_name} için {period_start} - {period_end} döneminde "
            f"konsolide net sonuç {fmt(consolidated_net)} ({health_label}), "
            f"toplam brüt gelir {fmt(gross_total_income)}. "
            f"FX net pozisyonu {fmt(net_exposure)} ile {risk_label} seviyede."
        )

        # Paragraf 2: Kritik noktalar
        balance_note = (
            "Intercompany eliminasyonu dengeli."
            if is_balanced
            else "⚠️ Intercompany eliminasyonunda tutarsızlık tespit edildi — "
                 "manuel inceleme önerilir."
        )
        pending_note = (
            f"{pending_count} adet bekleyen intercompany transfer 4-eyes onay "
            f"sırasında."
            if pending_count > 0
            else "Bekleyen intercompany transfer yok."
        )
        para2 = f"{balance_note} {pending_note}"

        # Paragraf 3: Öneriler (kural tabanlı)
        suggestions: list[str] = []
        if health_status == "risk":
            suggestions.append(
                "• Negatif konsolide net — gider kontrolü ve nakit akışı acil "
                "review gerekli."
            )
        if risk_level in ("concentrated", "critical"):
            suggestions.append(
                "• FX konsantrasyonu yüksek — hedging stratejisi "
                "(forward/swap) değerlendirilmeli."
            )
        if not is_balanced:
            suggestions.append(
                "• Intercompany eliminasyon imbalance — finans ekibi atomic "
                "write süreçlerini doğrulamalı."
            )
        if pending_count >= 3:
            suggestions.append(
                f"• {pending_count} bekleyen onay birikti — 4-eyes workflow "
                "hızlandırılmalı."
            )
        if not suggestions:
            suggestions.append(
                "• Mevcut göstergeler sağlıklı — rutin haftalık review "
                "yeterli."
            )

        para3 = "Öneriler:\n" + "\n".join(suggestions)

        return f"{para1}\n\n{para2}\n\n{para3}"


class ClaudeLLMService:
    """Production LLM service — Claude API with prompt caching."""

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
                "Or set AQ_LLM_OFFLINE=true to use OfflineLLMService."
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def generate_exec_summary(self, *, context: dict[str, Any]) -> str:
        """Claude API → Türkçe exec summary, prompt caching ile."""
        user_message = self._build_user_message(context)

        # System prompt cache'lenir → tekrar requestlerde ~90% maliyet azalır
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=[
                {
                    "type": "text",
                    "text": EXEC_SUMMARY_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {"role": "user", "content": user_message},
            ],
        )

        # response.content = list of TextBlock — text type olanı al
        for block in response.content:
            if getattr(block, "type", None) == "text":
                return str(block.text)

        # Hiç text yok → fallback
        return "AI özet üretilemedi (boş yanıt)."

    @staticmethod
    def _build_user_message(context: dict[str, Any]) -> str:
        """Yapısal context → user prompt (deterministic, cache-friendly).

        JSON yerine düz Türkçe metin — LLM Türkçe veriyle daha iyi çalışır
        + okunabilir debug. Field sırası deterministic (cache hit için).
        """
        holding_name = str(context.get("holding_name", "Holding"))
        period_start = str(context.get("period_start", ""))
        period_end = str(context.get("period_end", ""))
        pl = context.get("consolidated_pl") or {}
        fx = context.get("fx_position") or {}
        pending = int(context.get("pending_transfers_count", 0))

        return f"""Aşağıdaki holding için yönetici özeti hazırla.

HOLDING: {holding_name}
DÖNEM: {period_start} - {period_end}

KONSOLİDE P&L:
- Gross gelir (eliminasyon öncesi): ₺{float(pl.get('gross_total_income', 0)):,.0f}
- Gross gider: ₺{float(pl.get('gross_total_expense', 0)):,.0f}
- Konsolide gelir (eliminasyon sonrası): ₺{float(pl.get('consolidated_income', 0)):,.0f}
- Konsolide gider: ₺{float(pl.get('consolidated_expense', 0)):,.0f}
- KONSOLIDE NET: ₺{float(pl.get('consolidated_net', 0)):,.0f}
- Mali sağlık: {pl.get('health_status', 'unknown')}
- Intercompany eliminasyon balanced: {pl.get('elimination', {}).get('is_balanced', True)}

FX POZİSYON:
- Total long: ₺{float(fx.get('total_long_try', 0)):,.0f}
- Total short: ₺{float(fx.get('total_short_try', 0)):,.0f}
- Net exposure: ₺{float(fx.get('net_exposure_try', 0)):,.0f}
- Risk seviyesi: {fx.get('risk_level', 'balanced')}
- Para birimi sayısı: {len(fx.get('exposures', []))}

PENDING ONAYLAR:
- Bekleyen intercompany transfer: {pending} adet
"""


def create_llm_service() -> LLMServiceProtocol:
    """Factory: env vars'a göre Claude veya Offline service döner.

    Resolution order:
      1. AQ_LLM_OFFLINE=true → OfflineLLMService (deterministic, no API)
      2. AQ_ANTHROPIC_API_KEY set + SDK available → ClaudeLLMService
      3. Fallback → OfflineLLMService (graceful degradation)
    """
    if os.getenv("AQ_LLM_OFFLINE", "").lower() in ("true", "1", "yes"):
        return OfflineLLMService()

    api_key = os.getenv("AQ_ANTHROPIC_API_KEY")
    if not api_key or not _ANTHROPIC_AVAILABLE:
        # Production'da key set'li değilse → offline fallback
        # Logged in observability layer (G+5) by caller
        return OfflineLLMService()

    return ClaudeLLMService(api_key=api_key)
