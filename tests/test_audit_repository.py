import tempfile
import unittest
from pathlib import Path

from app.audit_repository import AuditRepository


class AuditRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "audit_test.db"
        self.repo = AuditRepository(str(self._db_path))

    def tearDown(self) -> None:
        self.repo.close()
        self._temp_dir.cleanup()

    def test_write_and_list_logs(self) -> None:
        self.repo.write_log(
            request_id="req-1",
            username="admin",
            role="admin",
            method="GET",
            path="/api/v1/health",
            status_code=200,
            ip_address="127.0.0.1",
            user_agent="pytest",
            duration_ms=12.4,
        )

        rows = self.repo.list_logs(limit=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["request_id"], "req-1")
        self.assertEqual(rows[0]["path"], "/api/v1/health")


if __name__ == "__main__":
    unittest.main()
