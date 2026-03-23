from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import time
from typing import Any

from app.connector_repository import ConnectorRepository
from app.models import (
    ConnectorCanonicalPreviewRequest,
    ConnectorCanonicalPreviewResponse,
    ConnectorCreateRequest,
    ConnectorListResponse,
    ConnectorQueueHealthResponse,
    ConnectorRead,
    ConnectorSyncDispatchRequest,
    ConnectorSyncDispatchResponse,
    ConnectorSyncJobCreateRequest,
    ConnectorSyncJobListResponse,
    ConnectorSyncJobRead,
)

_AUTH_BASE_SCORE = {
    "none": 25.0,
    "basic": 50.0,
    "api_key": 68.0,
    "oauth2": 86.0,
    "mtls": 92.0,
}

_TRIGGER_SCORE = {
    "manual": 70.0,
    "scheduled": 55.0,
    "webhook": 80.0,
    "reconcile": 90.0,
}

_CRITICALITY_SCORE = {
    "low": 40.0,
    "standard": 65.0,
    "high": 85.0,
    "critical": 100.0,
}

_KEY_SANITIZER = re.compile(r"[^a-z0-9]")

_CANONICAL_SCHEMAS: dict[str, dict[str, Any]] = {
    "finance": {
        "target_entity": "finance_ledger_entry",
        "required": [
            "external_id",
            "company_name",
            "entry_type",
            "amount",
            "currency",
            "entry_date",
        ],
        "optional": [
            "category",
            "description",
            "cost_center",
            "counterparty",
        ],
        "aliases": {
            "id": "external_id",
            "transactionid": "external_id",
            "company": "company_name",
            "type": "entry_type",
            "value": "amount",
            "date": "entry_date",
        },
    },
    "inventory": {
        "target_entity": "inventory_snapshot",
        "required": [
            "external_id",
            "company_name",
            "sku",
            "item_name",
            "quantity",
            "updated_at",
        ],
        "optional": [
            "warehouse_id",
            "location",
            "min_level",
            "unit",
        ],
        "aliases": {
            "id": "external_id",
            "company": "company_name",
            "productcode": "sku",
            "productname": "item_name",
            "qty": "quantity",
            "timestamp": "updated_at",
        },
    },
    "procurement": {
        "target_entity": "procurement_event",
        "required": [
            "external_id",
            "company_name",
            "request_title",
            "item_name",
            "quantity",
            "status",
            "updated_at",
        ],
        "optional": [
            "vendor_name",
            "unit_price",
            "currency",
            "delivery_days",
            "compliance_score",
        ],
        "aliases": {
            "id": "external_id",
            "company": "company_name",
            "title": "request_title",
            "item": "item_name",
            "qty": "quantity",
            "timestamp": "updated_at",
            "vendor": "vendor_name",
        },
    },
    "market": {
        "target_entity": "market_ohlcv",
        "required": [
            "symbol",
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ],
        "optional": [
            "source",
            "timeframe",
        ],
        "aliases": {
            "date": "timestamp",
            "time": "timestamp",
            "vol": "volume",
        },
    },
    "generic": {
        "target_entity": "generic_event",
        "required": [
            "external_id",
            "company_name",
            "updated_at",
        ],
        "optional": [
            "status",
            "payload_hash",
            "source",
        ],
        "aliases": {
            "id": "external_id",
            "company": "company_name",
            "timestamp": "updated_at",
            "date": "updated_at",
        },
    },
}


class ConnectorEngine:
    def __init__(self, repo: ConnectorRepository) -> None:
        self._repo = repo

    def create_connector(self, payload: ConnectorCreateRequest, *, created_by: str | None) -> ConnectorRead:
        mapping = _normalize_mapping(payload.mapping)
        schema = _resolve_schema(payload.connector_type)
        existing = self._repo.get_connector_by_signature(
            company_name=payload.company_name,
            connector_type=payload.connector_type,
            provider=payload.provider,
        )
        if existing is not None:
            raise ValueError("Connector already exists for company/type/provider")

        mapping_coverage_score = _coverage_score(
            mapped_fields=set(mapping.values()),
            required_fields=schema["required"],
        )
        security_score = _security_score(payload.auth_mode, payload.config)
        integration_score = _integration_score(payload.base_url, payload.config, mapping)
        readiness_score = round(
            0.45 * mapping_coverage_score + 0.30 * security_score + 0.25 * integration_score,
            2,
        )
        status = _status_from_readiness(readiness_score)

        row = self._repo.create_connector(
            company_name=payload.company_name,
            connector_type=payload.connector_type,
            provider=payload.provider,
            base_url=payload.base_url,
            auth_mode=payload.auth_mode,
            config=payload.config,
            mapping=mapping,
            status=status,
            readiness_score=readiness_score,
            mapping_coverage_score=mapping_coverage_score,
            security_score=security_score,
            created_by=created_by,
        )
        return _to_connector_read(row)

    def list_connectors(
        self,
        *,
        company_name: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> ConnectorListResponse:
        rows = self._repo.list_connectors(
            company_name=company_name,
            status=status,
            limit=limit,
        )
        items = [_to_connector_read(row) for row in rows]
        return ConnectorListResponse(total=len(items), items=items)

    def get_connector(self, connector_id: int) -> ConnectorRead:
        row = self._repo.get_connector(connector_id)
        if row is None:
            raise ValueError("Connector not found")
        return _to_connector_read(row)

    def preview_canonical_mapping(
        self,
        payload: ConnectorCanonicalPreviewRequest,
    ) -> ConnectorCanonicalPreviewResponse:
        schema = _resolve_schema(payload.connector_type)
        sample = payload.sample_payload
        provided_mapping = _normalize_mapping(payload.mapping)
        suggested_mapping = _suggest_mapping(sample, schema)

        merged_mapping = dict(suggested_mapping)
        merged_mapping.update(provided_mapping)

        mapped_fields = sorted(set(merged_mapping.values()))
        missing_required = [
            field
            for field in schema["required"]
            if field not in mapped_fields
        ]
        coverage_score = _coverage_score(
            mapped_fields=set(mapped_fields),
            required_fields=schema["required"],
        )

        sample_lookup = {_normalize_key(key): key for key in sample.keys()}
        canonical_preview: dict[str, object] = {}
        for source_field, canonical_field in merged_mapping.items():
            real_key = sample_lookup.get(_normalize_key(source_field))
            if real_key is None:
                continue
            canonical_preview[canonical_field] = sample[real_key]

        notes = [
            f"Target entity resolved as '{schema['target_entity']}'.",
            f"Coverage score={coverage_score:.2f}/100.",
        ]
        if missing_required:
            notes.append(
                "Missing required canonical fields: "
                + ", ".join(missing_required)
            )
        else:
            notes.append("All required canonical fields are mapped.")
        if not provided_mapping:
            notes.append("Mapping was auto-suggested from sample payload keys.")

        return ConnectorCanonicalPreviewResponse(
            connector_type=payload.connector_type,
            target_entity=schema["target_entity"],
            required_fields=list(schema["required"]),
            mapped_fields=mapped_fields,
            missing_required_fields=missing_required,
            coverage_score=coverage_score,
            suggested_mapping=suggested_mapping,
            canonical_record_preview=canonical_preview,
            validation_notes=notes,
        )

    def create_sync_job(
        self,
        connector_id: int,
        payload: ConnectorSyncJobCreateRequest,
        *,
        requested_by: str | None,
    ) -> ConnectorSyncJobRead:
        connector = self._repo.get_connector(connector_id)
        if connector is None:
            raise ValueError("Connector not found")

        priority_score = _priority_score(
            connector=connector,
            trigger_mode=payload.trigger_mode,
            criticality=payload.criticality,
            priority_boost=payload.priority_boost,
        )
        request_payload = dict(payload.request_payload)
        request_payload.setdefault("criticality", payload.criticality)

        row = self._repo.create_sync_job(
            connector_id=connector_id,
            trigger_mode=payload.trigger_mode,
            priority_score=priority_score,
            max_attempts=payload.max_attempts,
            requested_by=requested_by,
            request_payload=request_payload,
        )
        return _to_sync_job_read(row)

    def list_sync_jobs(
        self,
        *,
        connector_id: int | None = None,
        company_name: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> ConnectorSyncJobListResponse:
        rows = self._repo.list_sync_jobs(
            connector_id=connector_id,
            company_name=company_name,
            status=status,
            limit=limit,
        )
        items = [_to_sync_job_read(row) for row in rows]
        return ConnectorSyncJobListResponse(total=len(items), items=items)

    def claim_next_sync_job(
        self,
        *,
        allowed_company_names: list[str] | None = None,
    ) -> tuple[ConnectorSyncJobRead, ConnectorRead] | None:
        row = self._repo.claim_next_sync_job(allowed_company_names=allowed_company_names)
        if row is None:
            return None
        connector_row = self._repo.get_connector(int(row["connector_id"]))
        if connector_row is None:
            self._repo.complete_sync_job(
                job_id=int(row["id"]),
                status="failed",
                result_summary="Connector not found during claim.",
                error_message="connector_not_found",
                error_code="CONNECTOR_NOT_FOUND",
            )
            return None
        return _to_sync_job_read(row), _to_connector_read(connector_row)

    def finalize_sync_job(
        self,
        *,
        job: ConnectorSyncJobRead,
        connector: ConnectorRead,
        success: bool,
        result_summary: str,
        error_message: str | None,
        error_code: str | None,
        health_score: float,
        allow_retry: bool,
        retry_backoff_seconds: int,
        max_retries_default: int = 3,
    ) -> tuple[ConnectorSyncJobRead, ConnectorRead]:
        if success:
            completed_row = self._repo.complete_sync_job(
                job_id=job.id,
                status="success",
                result_summary=result_summary,
                error_message=None,
                error_code=None,
            )
            connector_status = "active" if health_score >= 70 else "staged"
        else:
            if allow_retry:
                completed_row = self._repo.fail_or_retry_sync_job(
                    job_id=job.id,
                    error_message=error_message or "sync_failed",
                    error_code=error_code,
                    retry_backoff_seconds=retry_backoff_seconds,
                    max_retries_default=max_retries_default,
                )
            else:
                completed_row = self._repo.complete_sync_job(
                    job_id=job.id,
                    status="failed",
                    result_summary=result_summary,
                    error_message=error_message,
                    error_code=error_code,
                )
            final_status = str(completed_row.get("status") or "failed")
            connector_status = "blocked" if final_status == "dead_letter" else "staged"

        self._repo.mark_connector_synced(
            connector.id,
            health_score=health_score,
            status=connector_status,
        )
        connector_row = self._repo.get_connector(connector.id)
        if connector_row is None:
            raise ValueError("Connector not found")
        return _to_sync_job_read(completed_row), _to_connector_read(connector_row)

    def build_queue_health(self, *, company_name: str | None = None) -> ConnectorQueueHealthResponse:
        row = self._repo.queue_health(company_name=company_name)
        return ConnectorQueueHealthResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_connectors=int(row["total_connectors"]),
            active_connectors=int(row["active_connectors"]),
            staged_connectors=int(row["staged_connectors"]),
            blocked_connectors=int(row["blocked_connectors"]),
            queued_jobs=int(row["queued_jobs"]),
            running_jobs=int(row["running_jobs"]),
            success_jobs=int(row["success_jobs"]),
            failed_jobs=int(row["failed_jobs"]),
            dead_letter_jobs=int(row["dead_letter_jobs"]),
            due_retry_jobs=int(row["due_retry_jobs"]),
            average_readiness_score=float(row["average_readiness_score"]),
            average_security_score=float(row["average_security_score"]),
        )

    def acquire_worker_lease(
        self,
        *,
        worker_name: str,
        owner_id: str,
        lease_seconds: int,
    ) -> bool:
        return self._repo.acquire_worker_lease(
            worker_name=worker_name,
            owner_id=owner_id,
            lease_seconds=lease_seconds,
        )

    def renew_worker_lease(
        self,
        *,
        worker_name: str,
        owner_id: str,
        lease_seconds: int,
    ) -> bool:
        return self._repo.renew_worker_lease(
            worker_name=worker_name,
            owner_id=owner_id,
            lease_seconds=lease_seconds,
        )

    def release_worker_lease(self, *, worker_name: str, owner_id: str) -> None:
        self._repo.release_worker_lease(worker_name=worker_name, owner_id=owner_id)

    def dispatch_next_sync_job(
        self,
        payload: ConnectorSyncDispatchRequest,
        *,
        requested_by: str | None,
        allowed_company_names: list[str] | None = None,
    ) -> ConnectorSyncDispatchResponse:
        claimed = self.claim_next_sync_job(allowed_company_names=allowed_company_names)
        if claimed is None:
            return ConnectorSyncDispatchResponse(
                claimed=False,
                message="No queued sync job found for dispatch.",
            )
        job, connector = claimed

        if not payload.auto_complete:
            return ConnectorSyncDispatchResponse(
                claimed=True,
                message="Sync job claimed and left in running state.",
                job=job,
                connector=connector,
            )

        success = payload.success
        if payload.result_summary.strip():
            summary = payload.result_summary.strip()
        else:
            actor = requested_by or "system"
            summary = (
                f"Sync completed successfully by {actor}."
                if success
                else f"Sync failed during dispatch by {actor}."
            )
        error_message = payload.error_message if not success else None

        completed_job, completed_connector = self.finalize_sync_job(
            job=job,
            connector=connector,
            success=success,
            result_summary=summary,
            error_message=error_message,
            error_code="DISPATCH_FAILURE" if not success else None,
            health_score=payload.health_score,
            allow_retry=payload.allow_retry,
            retry_backoff_seconds=payload.retry_backoff_seconds,
        )

        return ConnectorSyncDispatchResponse(
            claimed=True,
            message=f"Sync job dispatched with status '{completed_job.status}'.",
            job=completed_job,
            connector=completed_connector,
        )


def _resolve_schema(connector_type: str) -> dict[str, Any]:
    normalized = connector_type.strip().lower()
    if any(key in normalized for key in ("fin", "ledger", "erp_finance")):
        return _CANONICAL_SCHEMAS["finance"]
    if any(key in normalized for key in ("inventory", "stock", "warehouse")):
        return _CANONICAL_SCHEMAS["inventory"]
    if any(key in normalized for key in ("procurement", "purchase", "tender", "rfq")):
        return _CANONICAL_SCHEMAS["procurement"]
    if any(key in normalized for key in ("market", "ohlcv", "exchange")):
        return _CANONICAL_SCHEMAS["market"]
    return _CANONICAL_SCHEMAS["generic"]


def _normalize_key(value: str) -> str:
    return _KEY_SANITIZER.sub("", value.strip().lower())


def _normalize_mapping(mapping: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for source, target in mapping.items():
        source_key = source.strip()
        target_key = target.strip()
        if not source_key or not target_key:
            continue
        normalized[source_key] = target_key
    return normalized


def _coverage_score(*, mapped_fields: set[str], required_fields: list[str]) -> float:
    if not required_fields:
        return 100.0
    hit = sum(1 for field in required_fields if field in mapped_fields)
    return round((hit / len(required_fields)) * 100, 2)


def _security_score(auth_mode: str, config: dict[str, object]) -> float:
    base = _AUTH_BASE_SCORE.get(auth_mode.strip().lower(), 45.0)
    score = base
    rotate_days = _extract_number(config.get("token_rotate_days"))
    if rotate_days is not None:
        if rotate_days <= 30:
            score += 8
        elif rotate_days <= 90:
            score += 4

    if _truthy(config.get("ip_allowlist_enabled")):
        score += 4
    if _truthy(config.get("mfa_enabled")):
        score += 6
    return round(_clamp(score), 2)


def _integration_score(
    base_url: str | None,
    config: dict[str, object],
    mapping: dict[str, str],
) -> float:
    score = 20.0
    if base_url and base_url.strip():
        score += 30
    if mapping:
        score += 25
    if _truthy(config.get("webhook_enabled")):
        score += 10
    timeout = _extract_number(config.get("timeout_seconds"))
    if timeout is not None and 1 <= timeout <= 120:
        score += 8
    retries = _extract_number(config.get("retry_count"))
    if retries is not None and retries >= 1:
        score += 7
    return round(_clamp(score), 2)


def _status_from_readiness(score: float) -> str:
    if score >= 80:
        return "active"
    if score >= 60:
        return "staged"
    return "blocked"


def _suggest_mapping(sample_payload: dict[str, object], schema: dict[str, Any]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for field in list(schema["required"]) + list(schema["optional"]):
        aliases[_normalize_key(field)] = field
    aliases.update({_normalize_key(k): v for k, v in schema["aliases"].items()})

    suggestions: dict[str, str] = {}
    for source_field in sample_payload.keys():
        canonical = aliases.get(_normalize_key(source_field))
        if canonical:
            suggestions[source_field] = canonical
    return suggestions


def _priority_score(
    *,
    connector: dict[str, Any],
    trigger_mode: str,
    criticality: str,
    priority_boost: float,
) -> float:
    now = int(time.time())
    last_sync_at = connector.get("last_sync_at")
    if last_sync_at is None:
        freshness_score = 100.0
    else:
        age_hours = max(0.0, (now - int(last_sync_at)) / 3600)
        freshness_score = min(100.0, age_hours * 4.0)

    readiness = float(connector.get("readiness_score") or 0.0)
    trigger_score = _TRIGGER_SCORE.get(trigger_mode.strip().lower(), 60.0)
    criticality_score = _CRITICALITY_SCORE.get(criticality.strip().lower(), 65.0)

    priority = (
        0.40 * freshness_score
        + 0.25 * readiness
        + 0.20 * criticality_score
        + 0.15 * trigger_score
        + priority_boost
    )
    return round(_clamp(priority), 2)


def _to_connector_read(row: dict[str, Any]) -> ConnectorRead:
    return ConnectorRead(
        id=int(row["id"]),
        company_name=str(row["company_name"]),
        connector_type=str(row["connector_type"]),
        provider=str(row["provider"]),
        base_url=str(row["base_url"]) if row.get("base_url") else None,
        auth_mode=str(row["auth_mode"]),
        config=_json_loads_dict(row.get("config_json")),
        mapping=_json_loads_mapping(row.get("mapping_json")),
        status=str(row["status"]),
        readiness_score=float(row["readiness_score"]),
        mapping_coverage_score=float(row["mapping_coverage_score"]),
        security_score=float(row["security_score"]),
        created_by=str(row["created_by"]) if row.get("created_by") else None,
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
        last_sync_at=int(row["last_sync_at"]) if row.get("last_sync_at") is not None else None,
    )


def _to_sync_job_read(row: dict[str, Any]) -> ConnectorSyncJobRead:
    return ConnectorSyncJobRead(
        id=int(row["id"]),
        connector_id=int(row["connector_id"]),
        company_name=str(row["company_name"]),
        connector_type=str(row["connector_type"]),
        provider=str(row["provider"]),
        trigger_mode=str(row["trigger_mode"]),
        priority_score=float(row["priority_score"]),
        status=str(row["status"]),
        requested_by=str(row["requested_by"]) if row.get("requested_by") else None,
        request_payload=_json_loads_dict(row.get("request_payload_json")),
        result_summary=str(row.get("result_summary") or ""),
        error_message=str(row["error_message"]) if row.get("error_message") else None,
        error_code=str(row["last_error_code"]) if row.get("last_error_code") else None,
        attempt_count=int(row.get("attempt_count") or 0),
        max_attempts=int(row.get("max_attempts") or 3),
        requested_at=int(row["requested_at"]),
        next_retry_at=int(row["next_retry_at"]) if row.get("next_retry_at") is not None else None,
        dead_lettered_at=(
            int(row["dead_lettered_at"]) if row.get("dead_lettered_at") is not None else None
        ),
        started_at=int(row["started_at"]) if row.get("started_at") is not None else None,
        finished_at=int(row["finished_at"]) if row.get("finished_at") is not None else None,
    )


def _json_loads_dict(value: Any) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _json_loads_mapping(value: Any) -> dict[str, str]:
    raw = _json_loads_dict(value)
    mapping: dict[str, str] = {}
    for key, item in raw.items():
        if not isinstance(key, str):
            continue
        if not isinstance(item, str):
            continue
        source = key.strip()
        target = item.strip()
        if not source or not target:
            continue
        mapping[source] = target
    return mapping


def _extract_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return value != 0
    return False


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return min(maximum, max(minimum, value))
