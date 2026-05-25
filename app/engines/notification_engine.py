from __future__ import annotations

from datetime import date
from typing import Any

from app.invoice_repository import InvoiceRepository
from app.notification_repository import NotificationRepository
from app.models import (
    NotificationRead,
    NotificationListResponse,
    NotificationGenerateResponse,
    NotificationSummaryResponse,
)


# Window definitions: (window_key, days_offset, kind, severity, title_prefix)
#   days_offset > 0  → days UNTIL due (reminder before due)
#   days_offset < 0  → days SINCE due (overdue alert)
# A notification fires when (today - due_date) >= -days_offset
# i.e. when the threshold has been crossed.
_WINDOWS: list[tuple[str, int, str, str, str]] = [
    ("T-3",  3,   "invoice_due_soon", "info",     "Vade yaklaşıyor (3 gün)"),
    ("T-1",  1,   "invoice_due_soon", "warning",  "Vade yarın!"),
    ("T+1",  -1,  "invoice_overdue",  "warning",  "Fatura gecikti (1 gün)"),
    ("T+7",  -7,  "invoice_overdue",  "critical", "Fatura 7 gün gecikti"),
    ("T+14", -14, "invoice_overdue",  "critical", "Fatura 14 gün gecikti"),
]


class NotificationEngine:
    def __init__(
        self,
        *,
        notif_repo: NotificationRepository,
        invoice_repo: InvoiceRepository,
    ) -> None:
        self._notif = notif_repo
        self._invoices = invoice_repo

    # ── Scanning / generation ────────────────────────────────────────────────

    def scan_invoices(
        self,
        *,
        company: str | None,
        today: date | None = None,
    ) -> NotificationGenerateResponse:
        """Walk every unpaid invoice and create any missing window notifications.

        Idempotent — the underlying UNIQUE(subject_type, subject_id, window_key)
        constraint quietly drops duplicates, so this can run on every request
        or on a schedule without spamming.
        """
        ref_date = today or date.today()
        # mark_overdue first so list_invoices reflects current state
        self._invoices.mark_overdue(company_name=company)

        invoices = self._invoices.list_invoices(
            company_name=company, limit=10_000
        )
        unpaid = [
            inv for inv in invoices
            if inv.get("status") not in ("paid", "cancelled")
        ]

        created_ids: list[int] = []
        scanned = len(unpaid)
        for inv in unpaid:
            for window_key, threshold_days, kind, severity, prefix in _WINDOWS:
                if self._window_triggered(
                    due_date=inv["due_date"],
                    threshold_days=threshold_days,
                    today=ref_date,
                ):
                    nid = self._notif.insert_if_absent(
                        company_name=str(inv["company_name"]),
                        kind=kind,
                        severity=severity,
                        subject_type="invoice",
                        subject_id=int(inv["id"]),
                        window_key=window_key,
                        title=prefix,
                        message=self._build_message(inv, window_key),
                    )
                    if nid is not None:
                        created_ids.append(nid)

        return NotificationGenerateResponse(
            company=company,
            scanned=scanned,
            created=len(created_ids),
            created_ids=created_ids,
        )

    @staticmethod
    def _window_triggered(
        *,
        due_date: str,
        threshold_days: int,
        today: date,
    ) -> bool:
        """Has the window threshold been crossed?

        Positive threshold_days = reminder N days BEFORE due (fires when
        days_until_due <= threshold_days AND > previous tier threshold).

        Negative threshold_days = alert N days PAST due (fires when
        days_since_due >= |threshold_days|).

        We keep this monotonic: once crossed, the notification exists
        forever — the UNIQUE constraint stops re-creation.
        """
        try:
            due = date.fromisoformat(due_date)
        except ValueError:
            return False
        delta = (due - today).days  # +ve = future, -ve = past
        if threshold_days > 0:
            # Reminder window: fires when due is within `threshold_days` from today
            # and still in the future (or today). Negative delta is for overdue
            # tiers, not reminder tiers.
            return 0 <= delta <= threshold_days
        # Overdue window: fires when invoice is at least |threshold_days| past due
        return delta <= threshold_days  # both negative

    @staticmethod
    def _build_message(inv: dict[str, Any], window_key: str) -> str:
        amount = float(inv.get("amount", 0))
        paid = float(inv.get("paid_amount") or 0)
        outstanding = round(amount - paid, 2)
        title = str(inv.get("title") or "")
        due = str(inv.get("due_date") or "")
        return (
            f"Fatura #{inv['id']} ({title}) — vade {due}, "
            f"açık bakiye {outstanding:.2f} {inv.get('currency') or 'TRY'} "
            f"[{window_key}]"
        )

    # ── Query API ────────────────────────────────────────────────────────────

    def list_notifications(
        self,
        *,
        company: str | None,
        severity: str | None = None,
        unread_only: bool = False,
        kind: str | None = None,
        limit: int = 200,
    ) -> NotificationListResponse:
        rows = self._notif.list_notifications(
            company_name=company, severity=severity,
            unread_only=unread_only, kind=kind, limit=limit,
        )
        items = [self._to_read(r) for r in rows]
        unread = sum(1 for r in rows if not r.get("is_read"))
        return NotificationListResponse(
            total=len(items), unread_count=unread, notifications=items
        )

    def mark_read(self, notification_id: int) -> NotificationRead | None:
        row = self._notif.mark_read(notification_id)
        return self._to_read(row) if row else None

    def get(self, notification_id: int) -> NotificationRead | None:
        row = self._notif.get(notification_id)
        return self._to_read(row) if row else None

    def summary(self, *, company: str | None) -> NotificationSummaryResponse:
        raw = self._notif.summary(company_name=company)
        return NotificationSummaryResponse(
            company=company,
            total=int(raw.get("total", 0)),
            unread=int(raw.get("unread", 0)),
            info=int(raw.get("info", 0)),
            warning=int(raw.get("warning", 0)),
            critical=int(raw.get("critical", 0)),
        )

    @staticmethod
    def _to_read(row: dict[str, Any]) -> NotificationRead:
        return NotificationRead(
            id=int(row["id"]),
            company=str(row["company_name"]),
            kind=str(row["kind"]),
            severity=str(row["severity"]),
            subject_type=str(row["subject_type"]),
            subject_id=int(row["subject_id"]),
            window_key=str(row["window_key"]),
            title=str(row["title"]),
            message=str(row.get("message") or ""),
            is_read=bool(row.get("is_read", 0)),
            created_at=int(row["created_at"]),
            updated_at=int(row["updated_at"]),
        )
