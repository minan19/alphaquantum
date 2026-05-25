"""S-343 — Pluggable channel provider abstraction.

Design goals:
- Providers are pure I/O adapters; business logic stays in DeliveryEngine.
- ConsoleProvider is the default for dev/CI — it never makes outbound calls
  and always succeeds, so tests stay hermetic.
- Real providers (SendGrid, Twilio, 360dialog) must default to sandbox mode
  when their API key is missing. Production has to opt in by setting both
  the API key AND `AQ_NOTIFICATION_SANDBOX=false`.
- Each provider returns a typed `ProviderResult` so the engine can log a
  consistent delivery record regardless of channel.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProviderResult:
    """What a provider returns after attempting to send a message."""
    success: bool                              # True if delivered or sandbox-accepted
    status: str = "queued"                     # 'sent' | 'sandbox' | 'failed'
    provider_message_id: str = ""              # opaque ID from provider, if any
    error_message: str = ""


class ChannelProvider(ABC):
    """Abstract sender. Subclasses bind to a single channel + provider."""

    #: short slug used in delivery_log.channel
    channel: str = "unknown"
    #: short slug used in delivery_log.provider
    name: str = "abstract"

    @abstractmethod
    def send(
        self, *, recipient: str, subject: str, body: str
    ) -> ProviderResult:
        """Attempt to deliver. Must NEVER raise — return failed result instead."""


class ConsoleProvider(ChannelProvider):
    """Dev/CI default. Logs to stdout via the standard logging module."""

    channel = "console"
    name = "console"

    def send(
        self, *, recipient: str, subject: str, body: str
    ) -> ProviderResult:
        logger.info(
            "[console-provider] to=%s subject=%r body=%r",
            recipient or "<empty>", subject, body,
        )
        return ProviderResult(
            success=True,
            status="sent",
            provider_message_id="console-" + os.urandom(4).hex(),
        )


class SendGridEmailProvider(ChannelProvider):
    """Email delivery via SendGrid Web API v3.

    Sandbox behavior:
      - If no API key, returns 'sandbox' status without making any call.
      - If env `AQ_NOTIFICATION_SANDBOX=true`, the SendGrid request is made
        with `mail_settings.sandbox_mode.enable=true` — the API validates the
        payload but doesn't send.

    Configuration:
      AQ_SENDGRID_API_KEY        (required to leave sandbox)
      AQ_SENDGRID_FROM_EMAIL     (defaults to no-reply@alphaquantum.local)
      AQ_NOTIFICATION_SANDBOX    (default 'true' → safe)
    """

    channel = "email"
    name = "sendgrid"

    API_URL = "https://api.sendgrid.com/v3/mail/send"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        from_email: str | None = None,
        sandbox: bool | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("AQ_SENDGRID_API_KEY", "")
        self._from_email = (
            from_email
            or os.getenv("AQ_SENDGRID_FROM_EMAIL", "no-reply@alphaquantum.local")
        )
        if sandbox is None:
            sandbox = os.getenv("AQ_NOTIFICATION_SANDBOX", "true").lower() != "false"
        self._sandbox = sandbox

    def send(
        self, *, recipient: str, subject: str, body: str
    ) -> ProviderResult:
        if not recipient or "@" not in recipient:
            return ProviderResult(
                success=False, status="failed",
                error_message="invalid recipient email",
            )
        if not self._api_key:
            # No credentials configured → never actually call SendGrid.
            logger.info(
                "[sendgrid-sandbox] to=%s subject=%r (no API key configured)",
                recipient, subject,
            )
            return ProviderResult(
                success=True, status="sandbox",
                provider_message_id="sandbox-no-key",
            )

        payload = {
            "personalizations": [{"to": [{"email": recipient}]}],
            "from": {"email": self._from_email},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }
        if self._sandbox:
            payload["mail_settings"] = {"sandbox_mode": {"enable": True}}

        req = urllib.request.Request(
            self.API_URL,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                message_id = resp.headers.get("X-Message-Id", "")
                status = "sandbox" if self._sandbox else "sent"
                return ProviderResult(
                    success=True, status=status,
                    provider_message_id=message_id,
                )
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode(errors="replace")[:500]
            return ProviderResult(
                success=False, status="failed",
                error_message=f"HTTP {exc.code}: {body_text}",
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return ProviderResult(
                success=False, status="failed",
                error_message=f"network error: {exc}",
            )


# ── Registry ─────────────────────────────────────────────────────────────────

@dataclass
class ProviderRegistry:
    """Holds the active provider for each channel.

    Default config (no env): {'console': ConsoleProvider(), 'email': SendGridEmailProvider()}
    — both safe for dev / CI / tests, neither calls outbound by default.
    """
    providers: dict[str, ChannelProvider] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "ProviderRegistry":
        return cls(providers={
            "console": ConsoleProvider(),
            "email": SendGridEmailProvider(),
        })

    def get(self, channel: str) -> ChannelProvider | None:
        return self.providers.get(channel)

    def channels(self) -> list[str]:
        return sorted(self.providers.keys())

    def register(self, provider: ChannelProvider) -> None:
        self.providers[provider.channel] = provider
