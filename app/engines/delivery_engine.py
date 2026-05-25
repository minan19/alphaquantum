"""S-343 — DeliveryEngine: routes notifications to configured channel providers.

Responsibility split:
- NotificationEngine generates *what* to say (window + invoice → notification row).
- DeliveryEngine decides *how* and *whether* to send it: resolves the customer,
  checks KVKK consent per channel, calls each registered provider, persists
  one delivery_log row per attempt.
"""
from __future__ import annotations

import os
from typing import Any

from app.channel_providers import ChannelProvider, ProviderRegistry
from app.crm_repository import CRMRepository
from app.delivery_log_repository import DeliveryLogRepository
from app.invoice_repository import InvoiceRepository
from app.notification_repository import NotificationRepository
from app.models import (
    DeliveryLogListResponse,
    DeliveryLogRead,
    DispatchAttempt,
    DispatchResponse,
)


# Maps each channel to the customer column / field that contains the recipient
# and the consent flag column. Sites add more channels by extending this map.
_CHANNEL_RESOLVERS: dict[str, dict[str, str]] = {
    "email":    {"recipient_field": "email",    "consent_field": "email_consent"},
    "sms":      {"recipient_field": "phone",    "consent_field": "sms_consent"},
    "whatsapp": {"recipient_field": "phone",    "consent_field": "whatsapp_consent"},
    # console has no recipient validation — always sends
    "console":  {"recipient_field": "",         "consent_field": ""},
}


class DeliveryEngine:
    def __init__(
        self,
        *,
        delivery_log_repo: DeliveryLogRepository,
        notification_repo: NotificationRepository,
        crm_repo: CRMRepository,
        invoice_repo: InvoiceRepository,
        registry: ProviderRegistry | None = None,
    ) -> None:
        self._log = delivery_log_repo
        self._notif = notification_repo
        self._crm = crm_repo
        self._invoices = invoice_repo
        self._registry = registry or ProviderRegistry.default()

    # ── Dispatch ─────────────────────────────────────────────────────────────

    def dispatch(
        self,
        *,
        notification_id: int,
        channels: list[str] | None = None,
    ) -> DispatchResponse | None:
        """Send a notification across the requested (or env-configured) channels.

        Returns None if the notification doesn't exist. Otherwise returns a
        DispatchResponse with one DispatchAttempt per channel — including
        skipped ones (no consent, no contact info) which are still logged so
        operators can audit the gap.
        """
        notif = self._notif.get(notification_id)
        if notif is None:
            return None

        wanted = channels or self._configured_channels()
        # Filter out channels with no registered provider; log skipped channels
        # implicitly by not attempting them.
        active = [c for c in wanted if self._registry.get(c) is not None]

        # Resolve customer (best-effort — invoice → customer_id → customer row)
        customer = self._resolve_customer(notif)

        attempts: list[DispatchAttempt] = []
        successful = failed = skipped = 0

        for channel in active:
            provider = self._registry.get(channel)
            assert provider is not None  # filtered above
            attempt = self._dispatch_one(
                channel=channel,
                provider=provider,
                notification=notif,
                customer=customer,
            )
            attempts.append(attempt)
            if attempt.status in ("sent", "sandbox"):
                successful += 1
            elif attempt.status.startswith("skipped_"):
                skipped += 1
            else:
                failed += 1

        return DispatchResponse(
            notification_id=notification_id,
            company=str(notif["company_name"]),
            attempted_channels=active,
            successful=successful,
            failed=failed,
            skipped=skipped,
            attempts=attempts,
        )

    def _dispatch_one(
        self,
        *,
        channel: str,
        provider: ChannelProvider,
        notification: dict[str, Any],
        customer: dict[str, Any] | None,
    ) -> DispatchAttempt:
        resolver = _CHANNEL_RESOLVERS.get(channel, {})
        recipient_field = resolver.get("recipient_field", "")
        consent_field = resolver.get("consent_field", "")

        recipient = ""
        skipped_status: str | None = None

        if channel == "console":
            recipient = "console"  # informational only
        elif customer is None:
            skipped_status = "skipped_no_contact"
        else:
            if consent_field and not bool(customer.get(consent_field, 0)):
                skipped_status = "skipped_no_consent"
            else:
                if recipient_field:
                    recipient = str(customer.get(recipient_field) or "").strip()
                if not recipient:
                    skipped_status = "skipped_no_contact"

        # Build subject + body from notification
        subject = str(notification.get("title") or "")
        body = str(notification.get("message") or "")

        if skipped_status is not None:
            log_row = self._log.insert(
                company_name=str(notification["company_name"]),
                notification_id=int(notification["id"]),
                channel=channel,
                provider=provider.name,
                recipient=recipient,
                status=skipped_status,
                error_message="",
                subject=subject, body=body,
            )
            return DispatchAttempt(
                channel=channel, provider=provider.name,
                recipient=recipient, status=skipped_status,
            )

        result = provider.send(
            recipient=recipient, subject=subject, body=body
        )
        log_row = self._log.insert(
            company_name=str(notification["company_name"]),
            notification_id=int(notification["id"]),
            channel=channel,
            provider=provider.name,
            recipient=recipient,
            status=result.status if result.success else "failed",
            error_message=result.error_message,
            provider_message_id=result.provider_message_id,
            subject=subject, body=body,
        )
        return DispatchAttempt(
            channel=channel,
            provider=provider.name,
            recipient=recipient,
            status=log_row["status"],
            error_message=result.error_message,
            provider_message_id=result.provider_message_id,
        )

    # ── Query ────────────────────────────────────────────────────────────────

    def list_log(
        self,
        *,
        company: str | None,
        notification_id: int | None = None,
        channel: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> DeliveryLogListResponse:
        rows = self._log.list_log(
            company_name=company,
            notification_id=notification_id,
            channel=channel,
            status=status,
            limit=limit,
        )
        items = [self._to_read(r) for r in rows]
        return DeliveryLogListResponse(total=len(items), entries=items)

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _configured_channels() -> list[str]:
        """Env-controlled default channel list (defaults to console only).

        AQ_NOTIFICATION_CHANNELS=email,console — comma-separated.
        """
        raw = os.getenv("AQ_NOTIFICATION_CHANNELS", "console")
        return [c.strip() for c in raw.split(",") if c.strip()]

    def _resolve_customer(
        self, notification: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Trace notification → invoice → customer."""
        if notification.get("subject_type") != "invoice":
            return None
        invoice = self._invoices.get_invoice(int(notification["subject_id"]))
        if invoice is None:
            return None
        cid = invoice.get("customer_id")
        if cid is None:
            return None
        return self._crm.get_customer(int(cid))

    @staticmethod
    def _to_read(row: dict[str, Any]) -> DeliveryLogRead:
        return DeliveryLogRead(
            id=int(row["id"]),
            company=str(row["company_name"]),
            notification_id=int(row["notification_id"]),
            channel=str(row["channel"]),
            provider=str(row["provider"]),
            recipient=str(row.get("recipient") or ""),
            status=str(row["status"]),
            error_message=str(row.get("error_message") or ""),
            provider_message_id=str(row.get("provider_message_id") or ""),
            subject=str(row.get("subject") or ""),
            body=str(row.get("body") or ""),
            sent_at=row.get("sent_at"),
            created_at=int(row["created_at"]),
        )
