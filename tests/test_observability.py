"""G+5: Observability tests — structured logging + metrics + domain events."""
import json
import logging
import unittest
from io import StringIO

from app.observability import (
    DomainEventLogger,
    PerformanceCounter,
    StructuredFormatter,
    _percentile,
    get_domain_logger,
    get_performance_counter,
    is_json_logging_enabled,
    reset_for_tests,
)


class StructuredFormatterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.formatter = StructuredFormatter()

    def test_basic_record_to_json(self) -> None:
        record = logging.LogRecord(
            name="alpha_quantum",
            level=logging.INFO,
            pathname="/x.py",
            lineno=1,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        output = self.formatter.format(record)
        payload = json.loads(output)
        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["logger"], "alpha_quantum")
        self.assertEqual(payload["msg"], "hello world")
        self.assertIn("ts", payload)

    def test_extra_context_included(self) -> None:
        """request_id, holding_id, etc. extra → JSON field."""
        record = logging.LogRecord(
            name="alpha_quantum",
            level=logging.INFO,
            pathname="/x.py",
            lineno=1,
            msg="approved",
            args=(),
            exc_info=None,
        )
        record.request_id = "abc123"
        record.holding_id = 42
        record.duration_ms = 12.5

        output = self.formatter.format(record)
        payload = json.loads(output)
        self.assertEqual(payload["request_id"], "abc123")
        self.assertEqual(payload["holding_id"], 42)
        self.assertEqual(payload["duration_ms"], 12.5)

    def test_exception_serialized(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="alpha_quantum",
                level=logging.ERROR,
                pathname="/x.py",
                lineno=1,
                msg="failed",
                args=(),
                exc_info=sys.exc_info(),
            )
        output = self.formatter.format(record)
        payload = json.loads(output)
        self.assertIn("exception", payload)
        self.assertIn("ValueError: boom", payload["exception"])


class PerformanceCounterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pc = PerformanceCounter()

    def test_record_request_increments_count(self) -> None:
        self.pc.record(path="/api/v1/test", status_code=200, duration_ms=12.5)
        snap = self.pc.snapshot()
        self.assertEqual(snap["request_count"], 1)
        self.assertEqual(snap["error_count"], 0)
        self.assertEqual(snap["status_breakdown"]["2xx"], 1)

    def test_5xx_increments_error_count(self) -> None:
        self.pc.record(path="/api/v1/x", status_code=500, duration_ms=200)
        snap = self.pc.snapshot()
        self.assertEqual(snap["error_count"], 1)
        self.assertEqual(snap["status_breakdown"]["5xx"], 1)

    def test_status_breakdown_correct_buckets(self) -> None:
        for code in (200, 201, 301, 404, 400, 500, 502):
            self.pc.record(path="/x", status_code=code, duration_ms=10)
        snap = self.pc.snapshot()
        self.assertEqual(snap["status_breakdown"]["2xx"], 2)
        self.assertEqual(snap["status_breakdown"]["3xx"], 1)
        self.assertEqual(snap["status_breakdown"]["4xx"], 2)
        self.assertEqual(snap["status_breakdown"]["5xx"], 2)

    def test_error_rate_calculation(self) -> None:
        for _ in range(9):
            self.pc.record(path="/ok", status_code=200, duration_ms=10)
        self.pc.record(path="/err", status_code=500, duration_ms=10)
        snap = self.pc.snapshot()
        self.assertEqual(snap["request_count"], 10)
        self.assertEqual(snap["error_count"], 1)
        self.assertEqual(snap["error_rate"], 0.1)

    def test_latency_percentiles(self) -> None:
        for ms in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            self.pc.record(path="/x", status_code=200, duration_ms=ms)
        snap = self.pc.snapshot()
        # p50 ~ ortanca = 55 (NIST interpolation)
        self.assertGreater(snap["latency_ms"]["p50"], 50)
        self.assertLess(snap["latency_ms"]["p50"], 60)
        # p95 yukarı kuyruk
        self.assertGreater(snap["latency_ms"]["p95"], 90)
        self.assertEqual(snap["latency_ms"]["max"], 100)
        self.assertEqual(snap["latency_ms"]["samples"], 10)

    def test_top_paths_sorted_by_count(self) -> None:
        for _ in range(5):
            self.pc.record(path="/popular", status_code=200, duration_ms=10)
        for _ in range(2):
            self.pc.record(path="/secondary", status_code=200, duration_ms=10)
        self.pc.record(path="/rare", status_code=200, duration_ms=10)
        snap = self.pc.snapshot()
        top = snap["top_paths"]
        self.assertEqual(list(top.keys())[0], "/popular")
        self.assertEqual(top["/popular"], 5)

    def test_path_explosion_capped(self) -> None:
        """200 path'i geçen distinct path'ler kaydedilmez (overflow guard)."""
        for i in range(250):
            self.pc.record(path=f"/path-{i}", status_code=200, duration_ms=10)
        snap = self.pc.snapshot()
        # Max 200 path key (top_paths sınırı 20 ama internal dict 200)
        self.assertEqual(snap["request_count"], 250)
        # snapshot top_paths max 20 dönüyor
        self.assertLessEqual(len(snap["top_paths"]), 20)


class PercentileHelperTests(unittest.TestCase):
    def test_empty_returns_zero(self) -> None:
        self.assertEqual(_percentile([], 95), 0.0)

    def test_single_sample(self) -> None:
        self.assertEqual(_percentile([100.0], 95), 100.0)

    def test_median(self) -> None:
        # [10, 20, 30, 40, 50] median (rank=(50/100)*(5-1)=2.0 → idx 2 = 30)
        result = _percentile([10, 20, 30, 40, 50], 50)
        self.assertEqual(result, 30.0)


class DomainEventLoggerTests(unittest.TestCase):
    def setUp(self) -> None:
        # Test logger to a buffer
        self.buffer = StringIO()
        self.handler = logging.StreamHandler(self.buffer)
        self.handler.setFormatter(StructuredFormatter())
        self.test_logger = logging.getLogger("alpha_quantum.test_domain")
        self.test_logger.addHandler(self.handler)
        self.test_logger.setLevel(logging.INFO)
        self.test_logger.propagate = False
        self.emitter = DomainEventLogger(self.test_logger)

    def tearDown(self) -> None:
        self.test_logger.removeHandler(self.handler)

    def test_emit_writes_structured_event(self) -> None:
        self.emitter.emit(
            "intercompany-transfer-approved",
            context={"holding_id": 1, "transfer_id": 42, "approver": "ayse@x.tr"},
        )
        output = self.buffer.getvalue()
        payload = json.loads(output.strip())
        self.assertEqual(payload["event_type"], "intercompany-transfer-approved")
        self.assertEqual(payload["event_kind"], "domain")
        self.assertEqual(payload["holding_id"], 1)
        self.assertEqual(payload["transfer_id"], 42)
        self.assertEqual(payload["approver"], "ayse@x.tr")

    def test_emit_without_context(self) -> None:
        self.emitter.emit("system-started")
        payload = json.loads(self.buffer.getvalue().strip())
        self.assertEqual(payload["event_type"], "system-started")


class SingletonAccessTests(unittest.TestCase):
    def tearDown(self) -> None:
        reset_for_tests()

    def test_performance_counter_singleton(self) -> None:
        c1 = get_performance_counter()
        c2 = get_performance_counter()
        self.assertIs(c1, c2)

    def test_domain_logger_singleton(self) -> None:
        d1 = get_domain_logger()
        d2 = get_domain_logger()
        self.assertIs(d1, d2)

    def test_reset_clears_singletons(self) -> None:
        first = get_performance_counter()
        reset_for_tests()
        second = get_performance_counter()
        self.assertIsNot(first, second)


class JsonLoggingFlagTests(unittest.TestCase):
    def test_default_disabled(self) -> None:
        import os
        os.environ.pop("AQ_LOG_JSON", None)
        self.assertFalse(is_json_logging_enabled())

    def test_enabled_when_env_set(self) -> None:
        import os
        os.environ["AQ_LOG_JSON"] = "1"
        try:
            self.assertTrue(is_json_logging_enabled())
        finally:
            os.environ.pop("AQ_LOG_JSON", None)


if __name__ == "__main__":
    unittest.main()
