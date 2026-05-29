"""G+5: Observability — structured logging + metrics + domain events.

Enterprise SaaS "0 hata" vizyonu için temel görünürlük katmanı:

  1. **Structured logging**: JSON formatlı log lines (request_id,
     duration_ms, status_code, path, method context).
  2. **Performance counter**: thread-safe in-memory counters (request_count,
     error_count, latency_p50/p95/p99). Cluster-wide metrics için Sentry
     veya Prometheus G+5.2 sprintinde eklenir.
  3. **Domain event emitter**: business-level audit events (transfer
     approved, holding onboarded, vb.) — Audit log'a paralel, agent
     anomalisi tespit etmek için.

## Mimari karar

Standart `logging` module üzerine ince katman. Production'da JSON formatter
otomatik, dev'de human-readable. structlog veya loguru gibi external lib
eklenmedi — minimum dep, max kontrol.

Sentry SDK + OpenTelemetry G+5.2 sprintinde gelecek — bu base katman
production-ready ama "elite" değil; G+5.2 distributed tracing ekleyecek.
"""
from __future__ import annotations

import bisect
import json
import logging
import os
import threading
import time
from collections import deque
from typing import Any


class StructuredFormatter(logging.Formatter):
    """JSON formatter — production log aggregator (Loki/Datadog) için.

    Standard fields: timestamp, level, logger, message, plus tüm "extra"
    field'ları otomatik dahil eder. Stack trace exception_info olarak.

    Dev mode (env AQ_LOG_JSON unset) için fallback simple text formatter.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Extra context'leri dahil et (request_id, holding_id, vs.)
        for key, value in record.__dict__.items():
            if key in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            }:
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def is_json_logging_enabled() -> bool:
    """Production'da AQ_LOG_JSON=1 ile etkinleştirilir."""
    return os.getenv("AQ_LOG_JSON", "").lower() in {"1", "true", "yes"}


# ── Performance counter ──────────────────────────────────────────────────────


class PerformanceCounter:
    """In-memory thread-safe request metrics.

    - request_count: toplam istek
    - error_count: 5xx / unhandled error sayısı
    - status_breakdown: 2xx/3xx/4xx/5xx histogram
    - latency_samples: ring buffer (max 10K), p50/p95/p99 hesaplaması için
    - per_path: path bazında count (top 20 cap)

    /system/metrics endpoint bunları döner — operasyonel görünürlük.
    Sentry/Prometheus G+5.2'de eklenecek; bu in-memory katman pilot
    için yeterli, restart'ta sıfırlanır (tasarım gereği).
    """

    _MAX_LATENCY_SAMPLES = 10_000
    _MAX_PATH_KEYS = 200  # path explosion'a karşı cap

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._request_count = 0
        self._error_count = 0
        self._status_breakdown: dict[str, int] = {
            "2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0,
        }
        self._latency_samples: deque[float] = deque(maxlen=self._MAX_LATENCY_SAMPLES)
        self._per_path: dict[str, int] = {}
        self._started_at = time.time()

    def record(
        self, *, path: str, status_code: int, duration_ms: float
    ) -> None:
        """Tek bir request'i kaydet. Thread-safe."""
        with self._lock:
            self._request_count += 1
            bucket = f"{status_code // 100}xx"
            if bucket in self._status_breakdown:
                self._status_breakdown[bucket] += 1
            if status_code >= 500:
                self._error_count += 1
            self._latency_samples.append(duration_ms)

            # Path counter — overflow guard
            if path in self._per_path:
                self._per_path[path] += 1
            elif len(self._per_path) < self._MAX_PATH_KEYS:
                self._per_path[path] = 1

    def snapshot(self) -> dict[str, Any]:
        """Mevcut metrics snapshot'ı. Read'ler de lock altında."""
        with self._lock:
            samples = list(self._latency_samples)
            uptime = time.time() - self._started_at
            error_rate = (
                self._error_count / self._request_count
                if self._request_count > 0
                else 0.0
            )
            return {
                "uptime_seconds": round(uptime, 1),
                "request_count": self._request_count,
                "error_count": self._error_count,
                "error_rate": round(error_rate, 5),
                "status_breakdown": dict(self._status_breakdown),
                "latency_ms": {
                    "p50": _percentile(samples, 50),
                    "p95": _percentile(samples, 95),
                    "p99": _percentile(samples, 99),
                    "max": max(samples, default=0.0),
                    "samples": len(samples),
                },
                "top_paths": dict(
                    sorted(
                        self._per_path.items(),
                        key=lambda kv: kv[1],
                        reverse=True,
                    )[:20]
                ),
            }


def _percentile(samples: list[float], pct: int) -> float:
    """Inclusive percentile (NIST P/100 method)."""
    if not samples:
        return 0.0
    sorted_samples = sorted(samples)
    # NIST method: rank = (P / 100) * (N - 1)
    rank = (pct / 100.0) * (len(sorted_samples) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_samples) - 1)
    weight = rank - lo
    interpolated = (
        sorted_samples[lo] * (1 - weight) + sorted_samples[hi] * weight
    )
    return round(interpolated, 2)


# Yardımcı: sıralı listede ekleme (test için)
def _insort(samples: list[float], value: float) -> None:
    bisect.insort(samples, value)


# ── Domain event emitter ─────────────────────────────────────────────────────


class DomainEventLogger:
    """Business-level audit events.

    AuditRepository HTTP-level event'leri tutar (request log).
    DomainEventLogger BUSINESS event'leri tutar — örnek:

      - intercompany_transfer_approved (holding_id, transfer_id, approver)
      - holding_onboarded (holding_id, company_count)
      - consolidated_pl_generated (holding_id, period, net)
      - fx_position_concentrated (holding_id, currency, risk_level)

    Bu event'ler "ürün anlama" için kritik — feature kullanım frekansı,
    AI anomaly detection için sinyal, customer success konuşmaları
    için somut data.

    Şu an: structured logger'a JSON event yazar. G+5.2'de Sentry
    breadcrumbs + Prometheus event counter eklenecek.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("alpha_quantum.domain")

    def emit(
        self,
        event_type: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Emit a domain event.

        Args:
            event_type: kebab-case event name, örn 'intercompany-transfer-approved'
            context: structured context, holding_id + actor_id + transfer_id vs.
        """
        extra: dict[str, Any] = {
            "event_type": event_type,
            "event_kind": "domain",
        }
        if context:
            extra.update(context)
        self._logger.info(f"domain.{event_type}", extra=extra)


# ── Module-level singletons ──────────────────────────────────────────────────


_perf_counter: PerformanceCounter | None = None
_domain_logger: DomainEventLogger | None = None


def get_performance_counter() -> PerformanceCounter:
    """Process-wide performance counter."""
    global _perf_counter
    if _perf_counter is None:
        _perf_counter = PerformanceCounter()
    return _perf_counter


def get_domain_logger() -> DomainEventLogger:
    """Process-wide domain event logger."""
    global _domain_logger
    if _domain_logger is None:
        _domain_logger = DomainEventLogger()
    return _domain_logger


def reset_for_tests() -> None:
    """Test fixture cleanup — counter ve domain logger sıfırlanır."""
    global _perf_counter, _domain_logger
    _perf_counter = None
    _domain_logger = None
