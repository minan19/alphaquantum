"""F4: DashboardLayoutEngine — widget layout validation + business kuralları.

## Tasarım

Layout: list of WidgetConfig (widget_id, size, hidden, order).
Backend doğrular: bilinen widget_id'ler, geçerli size'lar, çakışan order yok.

## Desteklenen widget'lar (frontend ile sözleşme)

| widget_id              | İçerik                          | Sahne |
|------------------------|----------------------------------|-------|
| balance                | Konsolide bakiye (ledger-derived) | 1     |
| fx_position            | FX net pozisyon + risk          | 1     |
| consolidated_pl        | Konsolide P&L mini             | 2     |
| pending_transfers      | 4-eyes onay kuyruğu            | 4     |
| exec_summary           | AI exec summary                | 5     |
| aging_analysis         | Alacak yaşlandırma (FinOS)     | -     |
| cashflow_projection    | 30g forecast (FinOS)           | -     |
| recent_invoices        | Son faturalar (FinOS)          | -     |

## Validation kuralları

- widget_id ∈ KNOWN_WIDGETS
- size ∈ {sm, md, lg}
- order ≥ 0
- Aynı widget_id 2 kez listelenemez (uniqueness)
- Max 12 widget (UI sınırı + DoS önlemi)

## Default layout

Kullanıcı henüz set etmediyse → DEFAULT_LAYOUT döner. Frontend bu
fallback'i kullanarak boş ekran göstermez.
"""
from __future__ import annotations

import json
import time
from typing import Any

from app.dashboard_layout_repository import DashboardLayoutRepository
from app.models import (
    DashboardLayoutResponse,
    DashboardWidgetConfig,
)


# Frontend ile sözleşme
KNOWN_WIDGETS = frozenset({
    "balance",
    "fx_position",
    "consolidated_pl",
    "pending_transfers",
    "exec_summary",
    "aging_analysis",
    "cashflow_projection",
    "recent_invoices",
})

VALID_SIZES = frozenset({"sm", "md", "lg"})

MAX_WIDGETS = 12

# Yeni kullanıcı için default layout
DEFAULT_LAYOUT: list[dict[str, Any]] = [
    {"widget_id": "balance",            "size": "md", "hidden": False, "order": 0},
    {"widget_id": "fx_position",        "size": "md", "hidden": False, "order": 1},
    {"widget_id": "consolidated_pl",    "size": "lg", "hidden": False, "order": 2},
    {"widget_id": "pending_transfers",  "size": "md", "hidden": False, "order": 3},
    {"widget_id": "aging_analysis",     "size": "md", "hidden": False, "order": 4},
    {"widget_id": "exec_summary",       "size": "lg", "hidden": False, "order": 5},
]


class DashboardLayoutEngine:
    """User-scoped layout management + validation."""

    def __init__(self, *, repo: DashboardLayoutRepository) -> None:
        self._repo = repo

    def get_layout(self, *, user_id: str) -> DashboardLayoutResponse:
        """Mevcut layout'u döner. Yoksa DEFAULT_LAYOUT.

        Format: validated + sorted by order.
        """
        row = self._repo.get_layout(user_id)
        if row is None:
            return DashboardLayoutResponse(
                user_id=user_id,
                widgets=[DashboardWidgetConfig(**w) for w in DEFAULT_LAYOUT],
                is_default=True,
                updated_at=int(time.time()),
            )

        layout_json = str(row.get("layout_json", "[]"))
        try:
            data = json.loads(layout_json)
            if not isinstance(data, list):
                data = list(DEFAULT_LAYOUT)
        except (TypeError, ValueError):
            data = list(DEFAULT_LAYOUT)

        widgets = [
            DashboardWidgetConfig(**w)
            for w in data
            if isinstance(w, dict) and w.get("widget_id") in KNOWN_WIDGETS
        ]
        widgets.sort(key=lambda w: w.order)
        return DashboardLayoutResponse(
            user_id=user_id,
            widgets=widgets,
            is_default=False,
            updated_at=int(row["updated_at"]),
        )

    def save_layout(
        self,
        *,
        user_id: str,
        widgets: list[DashboardWidgetConfig],
    ) -> DashboardLayoutResponse:
        """Layout'u validate + persist.

        Raises:
            ValueError: bilinmeyen widget_id, invalid size, dup id, > MAX_WIDGETS
        """
        if len(widgets) > MAX_WIDGETS:
            raise ValueError(
                f"Maksimum {MAX_WIDGETS} widget desteklenir (gönderilen: {len(widgets)})"
            )

        seen: set[str] = set()
        for w in widgets:
            if w.widget_id not in KNOWN_WIDGETS:
                raise ValueError(f"Bilinmeyen widget: {w.widget_id}")
            if w.size not in VALID_SIZES:
                raise ValueError(f"Geçersiz size: {w.size} (geçerli: sm, md, lg)")
            if w.order < 0:
                raise ValueError("order ≥ 0 olmalı")
            if w.widget_id in seen:
                raise ValueError(f"Widget '{w.widget_id}' birden fazla kez listelendi")
            seen.add(w.widget_id)

        layout_json = json.dumps(
            [w.model_dump() for w in widgets],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        row = self._repo.upsert_layout(user_id=user_id, layout_json=layout_json)
        return self.get_layout(user_id=user_id) if row else DashboardLayoutResponse(
            user_id=user_id,
            widgets=widgets,
            is_default=False,
            updated_at=int(time.time()),
        )

    def reset_layout(self, *, user_id: str) -> DashboardLayoutResponse:
        """Default'a döner — user'ın saved layout'u silinir."""
        self._repo.delete_layout(user_id)
        return self.get_layout(user_id=user_id)
