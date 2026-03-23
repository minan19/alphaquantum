from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.models import ConnectorRead, ConnectorSyncJobRead


@dataclass(frozen=True)
class ConnectorSyncExecutionResult:
    success: bool
    health_score: float
    summary: str
    error_message: str | None = None
    error_code: str | None = None


class ConnectorAdapter(Protocol):
    def supports(self, connector: ConnectorRead) -> bool: ...

    def execute(self, connector: ConnectorRead, job: ConnectorSyncJobRead) -> ConnectorSyncExecutionResult: ...


class FinanceConnectorAdapter:
    def supports(self, connector: ConnectorRead) -> bool:
        normalized = connector.connector_type.lower()
        return "fin" in normalized or "ledger" in normalized

    def execute(self, connector: ConnectorRead, job: ConnectorSyncJobRead) -> ConnectorSyncExecutionResult:
        return _execute_with_common_rules(connector, job, domain="finance")


class InventoryConnectorAdapter:
    def supports(self, connector: ConnectorRead) -> bool:
        normalized = connector.connector_type.lower()
        return "inventory" in normalized or "stock" in normalized or "warehouse" in normalized

    def execute(self, connector: ConnectorRead, job: ConnectorSyncJobRead) -> ConnectorSyncExecutionResult:
        return _execute_with_common_rules(connector, job, domain="inventory")


class ProcurementConnectorAdapter:
    def supports(self, connector: ConnectorRead) -> bool:
        normalized = connector.connector_type.lower()
        return "procurement" in normalized or "purchase" in normalized or "tender" in normalized

    def execute(self, connector: ConnectorRead, job: ConnectorSyncJobRead) -> ConnectorSyncExecutionResult:
        return _execute_with_common_rules(connector, job, domain="procurement")


class MarketConnectorAdapter:
    def supports(self, connector: ConnectorRead) -> bool:
        normalized = connector.connector_type.lower()
        return "market" in normalized or "ohlcv" in normalized or "exchange" in normalized

    def execute(self, connector: ConnectorRead, job: ConnectorSyncJobRead) -> ConnectorSyncExecutionResult:
        return _execute_with_common_rules(connector, job, domain="market")


class GenericConnectorAdapter:
    def supports(self, connector: ConnectorRead) -> bool:
        del connector
        return True

    def execute(self, connector: ConnectorRead, job: ConnectorSyncJobRead) -> ConnectorSyncExecutionResult:
        return _execute_with_common_rules(connector, job, domain="generic")


class ConnectorAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: list[ConnectorAdapter] = [
            FinanceConnectorAdapter(),
            InventoryConnectorAdapter(),
            ProcurementConnectorAdapter(),
            MarketConnectorAdapter(),
            GenericConnectorAdapter(),
        ]

    def execute(self, connector: ConnectorRead, job: ConnectorSyncJobRead) -> ConnectorSyncExecutionResult:
        for adapter in self._adapters:
            if adapter.supports(connector):
                return adapter.execute(connector, job)
        return ConnectorSyncExecutionResult(
            success=False,
            health_score=20.0,
            summary="No adapter matched connector.",
            error_message="adapter_not_found",
            error_code="ADAPTER_NOT_FOUND",
        )


def _execute_with_common_rules(
    connector: ConnectorRead,
    job: ConnectorSyncJobRead,
    *,
    domain: str,
) -> ConnectorSyncExecutionResult:
    config = connector.config
    payload = job.request_payload

    if _truthy(payload.get("force_fail")):
        return ConnectorSyncExecutionResult(
            success=False,
            health_score=max(10.0, connector.security_score - 20.0),
            summary=f"{domain} sync failed (forced failure payload).",
            error_message="forced_failure",
            error_code="FORCED_FAILURE",
        )

    fail_until_attempt = _extract_int(config.get("fail_until_attempt"), default=0)
    if fail_until_attempt > 0 and job.attempt_count <= fail_until_attempt:
        return ConnectorSyncExecutionResult(
            success=False,
            health_score=max(15.0, connector.security_score - 15.0),
            summary=f"{domain} sync transient failure on attempt {job.attempt_count}.",
            error_message="transient_provider_error",
            error_code="TRANSIENT_PROVIDER_ERROR",
        )

    base_health = (0.60 * connector.security_score) + (0.40 * connector.readiness_score)
    processing_penalty = 3.0 if payload.get("criticality") == "critical" else 0.0
    health_score = max(30.0, min(100.0, base_health - processing_penalty))
    summary = (
        f"{domain} sync completed for {connector.company_name}/{connector.provider}. "
        f"attempt={job.attempt_count}/{job.max_attempts}"
    )
    return ConnectorSyncExecutionResult(
        success=True,
        health_score=round(health_score, 2),
        summary=summary,
    )


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return value != 0
    return False


def _extract_int(value: object, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            return int(float(text))
        except ValueError:
            return default
    return default
