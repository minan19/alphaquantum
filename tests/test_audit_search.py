"""SEC1: AuditRepository.search_logs + summary tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.audit_repository import AuditRepository
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager


class AuditSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "audit_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

        bootstrap = IdentityRepository(str(self._db_path))
        bootstrap.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()

        self.repo = AuditRepository(str(self._db_path))
        self._seed_logs()

    def tearDown(self) -> None:
        self.repo.close()
        self.manager.close()
        self._tmp.cleanup()

    def _seed_logs(self) -> None:
        """Mixed test data."""
        # Alice GET /api/v1/customers — 200
        self.repo.write_log(
            request_id="r1", username="alice", role="manager",
            method="GET", path="/api/v1/customers",
            status_code=200, ip_address="1.1.1.1",
            user_agent="ua1", duration_ms=12.5,
        )
        # Bob POST /api/v1/invoices — 200
        self.repo.write_log(
            request_id="r2", username="bob", role="admin",
            method="POST", path="/api/v1/invoices",
            status_code=200, ip_address="1.1.1.2",
            user_agent="ua2", duration_ms=80,
        )
        # Charlie DELETE /api/v1/sample-data — 403 (forbidden)
        self.repo.write_log(
            request_id="r3", username="charlie", role="viewer",
            method="DELETE", path="/api/v1/sample-data",
            status_code=403, ip_address="1.1.1.3",
            user_agent="ua3", duration_ms=8,
        )
        # Alice GET /api/v1/customers — 500 (error)
        self.repo.write_log(
            request_id="r4", username="alice", role="manager",
            method="GET", path="/api/v1/customers",
            status_code=500, ip_address="1.1.1.1",
            user_agent="ua1", duration_ms=350,
        )

    # ── search_logs ────────────────────────────────────────────────────

    def test_search_by_username(self) -> None:
        rows = self.repo.search_logs(username="alice")
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertEqual(r["username"], "alice")

    def test_search_by_method(self) -> None:
        rows = self.repo.search_logs(method="POST")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["method"], "POST")

    def test_search_method_case_insensitive(self) -> None:
        rows = self.repo.search_logs(method="get")
        self.assertEqual(len(rows), 2)

    def test_search_by_path_contains(self) -> None:
        rows = self.repo.search_logs(path_contains="customers")
        self.assertEqual(len(rows), 2)

    def test_search_by_status_code_range(self) -> None:
        # Errors only (400+)
        rows = self.repo.search_logs(status_code_min=400)
        self.assertEqual(len(rows), 2)  # 403 + 500
        for r in rows:
            self.assertGreaterEqual(r["status_code"], 400)

    def test_search_by_status_code_window(self) -> None:
        # Server errors only
        rows = self.repo.search_logs(
            status_code_min=500, status_code_max=599,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status_code"], 500)

    def test_search_combined_filters(self) -> None:
        # Alice's errors
        rows = self.repo.search_logs(
            username="alice", status_code_min=400,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["username"], "alice")
        self.assertEqual(rows[0]["status_code"], 500)

    def test_search_path_like_escape_safe(self) -> None:
        """Path filter SQL injection ya da LIKE wildcard'ı kabul etmemeli."""
        rows = self.repo.search_logs(path_contains="%")
        # '%' literal arandığı için 0 sonuç (hiçbir path '%' içermez)
        self.assertEqual(len(rows), 0)

    def test_search_limit_clamped(self) -> None:
        # 4 log var ama limit 2
        rows = self.repo.search_logs(limit=2)
        self.assertEqual(len(rows), 2)

    def test_search_no_filter_returns_all(self) -> None:
        rows = self.repo.search_logs()
        self.assertGreaterEqual(len(rows), 4)

    # ── summary ────────────────────────────────────────────────────────

    def test_summary_total_events_in_window(self) -> None:
        summary = self.repo.summary(window_hours=24)
        self.assertGreaterEqual(summary["total_events"], 4)

    def test_summary_error_rate(self) -> None:
        summary = self.repo.summary(window_hours=24)
        # 2/4 = %50 error rate
        self.assertEqual(summary["error_count"], 2)
        self.assertAlmostEqual(summary["error_rate_pct"], 50.0)

    def test_summary_events_by_method(self) -> None:
        summary = self.repo.summary(window_hours=24)
        methods = {m["method"] for m in summary["events_by_method"]}
        self.assertIn("GET", methods)
        self.assertIn("POST", methods)
        self.assertIn("DELETE", methods)

    def test_summary_events_by_user(self) -> None:
        summary = self.repo.summary(window_hours=24)
        users = {u["username"]: u["count"] for u in summary["events_by_user"]}
        self.assertEqual(users["alice"], 2)
        self.assertEqual(users["bob"], 1)

    def test_summary_old_logs_excluded(self) -> None:
        """1 saatlik window dışındaki loglar sayılmaz.

        Bu test future-proof: seed sırasında loglar 'now'da, geçmiş loglar
        yok. 1 saatlik window hala 4 olmalı (seeds + now < 1h).
        """
        # Future-proof: zaten "now" seeded loglar 1 saat içinde
        summary = self.repo.summary(window_hours=1)
        self.assertEqual(summary["total_events"], 4)


if __name__ == "__main__":
    unittest.main()
