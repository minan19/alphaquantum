"""AC1: AI Finance Copilot — natural language → structured intent → safe query.

## Felsefe

Kullanıcı: "Geçen ay AcmeCo'ya kaç fatura kestik?"
Copilot: structured intent → SQL whitelisted query → cevap.

## Güvenlik

Direkt LLM → SQL TEHLİKELİ (SQL injection, prompt injection).
Bunun yerine:
  1. LLM intent classification: action + entity + filters
  2. Whitelist mapping: action → predefined SQL template
  3. Parametre placeholder ile execute

## Intent şeması

  * "list_invoices" — fatura listesi
  * "count_invoices" — sayım
  * "sum_amount" — toplam tutar
  * "list_customers" — müşteri listesi
  * "list_anomalies" — anomali sinyalleri
  * "cashflow_balance" — toplam bakiye
  * "vendor_count" — tedarikçi sayısı

Her intent için filter şeması: customer_name, time_window_days,
direction (outgoing/incoming), category.

## Offline fallback

OfflineCopilotService — keyword matching (no API). Production'da
ClaudeIntentParser kullanılır.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any


VALID_INTENTS = frozenset({
    "list_invoices", "count_invoices", "sum_amount",
    "list_customers", "list_anomalies",
    "cashflow_balance", "vendor_count",
    "unknown",
})


@dataclass(frozen=True)
class CopilotIntent:
    intent: str                  # VALID_INTENTS
    entity_name: str | None = None  # customer/vendor name
    time_window_days: int | None = None
    direction: str | None = None   # outgoing | incoming
    category: str | None = None
    confidence_pct: float = 0
    raw_query: str = ""


@dataclass
class CopilotResponse:
    intent: CopilotIntent
    results: list[dict[str, Any]] = field(default_factory=list)
    summary_text: str = ""
    explanation: str = ""        # Bu sonuca nasıl ulaşıldı
    sql_template_used: str | None = None


# ── Offline keyword-based parser ──────────────────────────────────────


class OfflineCopilotParser:
    """Keyword + regex tabanlı intent classifier. Production'da Claude
    API ile değiştirilir; aynı interface."""

    # Türkçe + İngilizce keyword'ler
    INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
        "list_invoices": (
            "fatura", "faturalar", "invoice", "invoices",
        ),
        "count_invoices": (
            "kaç fatura", "fatura sayısı", "how many invoice",
        ),
        "sum_amount": (
            "toplam", "ne kadar", "kaç tl", "kaç lira", "total",
            "sum",
        ),
        "list_customers": (
            "müşteri", "müşteriler", "customer", "customers",
            "cariler", "cari",
        ),
        "list_anomalies": (
            "anomali", "sızıntı", "sinyal", "alarm",
            "anomaly", "leak", "signal",
        ),
        "cashflow_balance": (
            "bakiye", "kasamda", "hesabımda", "balance",
        ),
        "vendor_count": (
            "tedarikçi", "vendor", "supplier",
        ),
    }

    TIME_KEYWORDS: dict[str, int] = {
        "bugün": 1, "today": 1,
        "dün": 2, "yesterday": 2,
        "bu hafta": 7, "this week": 7,
        "geçen hafta": 14, "last week": 14,
        "bu ay": 30, "this month": 30,
        "geçen ay": 60, "last month": 60,
        "son 3 ay": 90, "last 3 months": 90,
        "bu yıl": 365, "this year": 365,
    }

    DIRECTION_KEYWORDS: dict[str, str] = {
        "kestik": "outgoing", "kestiğim": "outgoing",
        "sattığım": "outgoing", "sold": "outgoing",
        "aldık": "incoming", "aldığım": "incoming",
        "tedarik": "incoming", "purchased": "incoming",
    }

    def parse(self, query: str) -> CopilotIntent:
        """Doğal dil → CopilotIntent."""
        q = query.lower().strip()
        if not q:
            return CopilotIntent(intent="unknown", raw_query=query)

        # Intent detection — priority order önemli (en spesifik önce):
        #   1. count_invoices ("kaç fatura")
        #   2. cashflow_balance ("bakiye") — generic "ne kadar"dan önce
        #   3. list_* / vendor_count / sum_amount
        intent = "unknown"
        confidence = 0.0
        priority = (
            "count_invoices",
            "cashflow_balance",
            "list_anomalies",
            "vendor_count",
            "list_customers",
            "list_invoices",
            "sum_amount",
        )
        for name in priority:
            for kw in self.INTENT_KEYWORDS.get(name, ()):
                if kw in q:
                    intent = name
                    confidence = 85.0 if name == "count_invoices" else 75.0
                    break
            if intent != "unknown":
                break

        # Entity (customer name): tırnak içinde veya 'X'a'/X'a/X için
        entity = self._extract_entity(query)

        # Time window
        time_days: int | None = None
        for kw, days in self.TIME_KEYWORDS.items():
            if kw in q:
                time_days = days
                break

        # Direction
        direction: str | None = None
        for kw, d in self.DIRECTION_KEYWORDS.items():
            if kw in q:
                direction = d
                break

        return CopilotIntent(
            intent=intent,
            entity_name=entity,
            time_window_days=time_days,
            direction=direction,
            confidence_pct=confidence,
            raw_query=query,
        )

    @staticmethod
    def _extract_entity(query: str) -> str | None:
        # "AcmeCo'ya", "AcmeCo'dan", "AcmeCo için" → AcmeCo
        # Tırnak içi pattern
        m = re.search(r'"([^"]+)"', query)
        if m:
            return m.group(1).strip()
        # 'Apostrof + ekler' pattern (TR)
        m = re.search(r"\b([A-ZÇĞİÖŞÜ][\wÇçĞğİıÖöŞşÜü]+(?:\s[A-ZÇĞİÖŞÜ][\wÇçĞğİıÖöŞşÜü]+)*)'\w+\b", query)
        if m:
            return m.group(1).strip()
        # 'için' öncesi
        m = re.search(r"(\w+(?:\s\w+){0,3})\s+için\b", query)
        if m:
            return m.group(1).strip()
        return None


class CopilotIntentParserProtocol:
    """Production'da Claude API ile değiştirilebilir."""

    def parse(self, query: str) -> CopilotIntent:
        raise NotImplementedError


def create_copilot_parser() -> OfflineCopilotParser:
    """Factory. Şu an offline default; AC1.1'de Claude API entegrasyonu."""
    _ = os.getenv("AQ_LLM_OFFLINE")  # placeholder for future
    return OfflineCopilotParser()
