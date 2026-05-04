from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.scheduled_report_repository import ScheduledReportRepository
from app.engines.schedule_engine import ScheduleEngine
from app.models import ScheduledReportCreateRequest


def _tmp_repo() -> tuple[ScheduledReportRepository, tempfile.TemporaryDirectory]:
    tmp = tempfile.TemporaryDirectory()
    repo = ScheduledReportRepository(str(Path(tmp.name) / "sched.db"))
    return repo, tmp


class ScheduledReportRepositoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = ScheduledReportRepository(
            str(Path(self._tmp.name) / "sched_test.db")
        )

    def tearDown(self):
        self.repo.close()
        self._tmp.cleanup()

    def _create(self, name: str = "Daily Ledger", report_type: str = "ledger",
                fmt: str = "xlsx") -> dict:
        return self.repo.create_job(
            name=name,
            report_type=report_type,
            format=fmt,
            company_name="Alpha Corp",
            params_json={"note": "test"},
            schedule_cron="0 8 * * *",
            recipient="cfo@example.com",
            created_by="admin",
        )

    def test_create_and_retrieve(self):
        row = self._create()
        self.assertEqual(row["name"], "Daily Ledger")
        self.assertEqual(row["report_type"], "ledger")
        self.assertEqual(row["format"], "xlsx")
        self.assertEqual(row["is_active"], 1)

    def test_list_all(self):
        self._create("Job1")
        self._create("Job2")
        rows = self.repo.list_jobs()
        self.assertEqual(len(rows), 2)

    def test_list_active_only_filters_inactive(self):
        row = self._create("Active Job")
        self._create("Another Job")
        self.repo.deactivate_job(row["id"])
        active = self.repo.list_jobs(active_only=True)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["name"], "Another Job")

    def test_get_job_returns_none_for_missing(self):
        result = self.repo.get_job(99999)
        self.assertIsNone(result)

    def test_update_job_status(self):
        row = self._create()
        self.repo.update_job_status(row["id"], last_run_at=9999999, last_status="ok")
        updated = self.repo.get_job(row["id"])
        self.assertEqual(updated["last_run_at"], 9999999)
        self.assertEqual(updated["last_status"], "ok")

    def test_deactivate_job(self):
        row = self._create()
        self.repo.deactivate_job(row["id"])
        updated = self.repo.get_job(row["id"])
        self.assertEqual(updated["is_active"], 0)

    def test_params_json_stored_as_string_retrieved_as_dict(self):
        row = self._create()
        raw = self.repo.get_job(row["id"])
        # Repository returns raw dict — params_json may be string or decoded
        import json
        params = raw["params_json"]
        if isinstance(params, str):
            params = json.loads(params)
        self.assertEqual(params.get("note"), "test")


class ScheduleEngineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        repo = ScheduledReportRepository(str(Path(self._tmp.name) / "eng_test.db"))
        self.engine = ScheduleEngine(repo)

    def tearDown(self):
        self.engine._repo.close()
        self._tmp.cleanup()

    def _payload(self, name: str = "Weekly Report") -> ScheduledReportCreateRequest:
        return ScheduledReportCreateRequest(
            name=name,
            report_type="budget_vs_actual",
            format="pdf",
            company_name=None,
            params_json={},
            schedule_cron="0 9 * * 1",
            recipient="cto@example.com",
        )

    def test_create_job_returns_read(self):
        result = self.engine.create_job(payload=self._payload(), created_by="admin")
        self.assertEqual(result.name, "Weekly Report")
        self.assertEqual(result.report_type, "budget_vs_actual")
        self.assertTrue(result.is_active)

    def test_list_jobs_response(self):
        self.engine.create_job(payload=self._payload("J1"), created_by="admin")
        self.engine.create_job(payload=self._payload("J2"), created_by="admin")
        response = self.engine.list_jobs()
        self.assertEqual(response.total, 2)
        self.assertEqual(len(response.jobs), 2)

    def test_trigger_job_returns_response(self):
        job = self.engine.create_job(payload=self._payload(), created_by="admin")
        result = self.engine.trigger_job(job_id=job.id)
        self.assertEqual(result.id, job.id)
        self.assertIn("/api/v1/reports/finance/", result.download_path)

    def test_trigger_missing_job_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.engine.trigger_job(job_id=99999)

    def test_deactivate_job(self):
        job = self.engine.create_job(payload=self._payload(), created_by="admin")
        deactivated = self.engine.deactivate_job(job_id=job.id)
        self.assertFalse(deactivated.is_active)

    def test_deactivate_missing_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.engine.deactivate_job(job_id=99999)

    def test_list_active_only(self):
        j1 = self.engine.create_job(payload=self._payload("Active"), created_by="admin")
        self.engine.create_job(payload=self._payload("Inactive"), created_by="admin")
        self.engine.deactivate_job(job_id=j1.id)
        active = self.engine.list_jobs(active_only=True)
        self.assertEqual(active.total, 1)
        self.assertEqual(active.jobs[0].name, "Inactive")


class ScheduleEngineApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app import create_app

        self._temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self._temp_dir.name) / "sched_api_test.db"
        self._original_env = {k: os.getenv(k) for k in [
            "AQ_DATABASE_PATH", "AQ_AUTH_USERS", "AQ_ENABLE_DEMO_USERS",
            "AQ_JWT_SECRET", "AQ_ENV", "AQ_MARKET_OFFLINE",
            "AQ_MACRO_OFFLINE", "AQ_WEB_OFFLINE",
        ]}
        os.environ["AQ_DATABASE_PATH"] = str(db_path)
        os.environ["AQ_AUTH_USERS"] = (
            "admin:admin12345:admin,"
            "viewer:viewer12345:viewer"
        )
        os.environ["AQ_ENABLE_DEMO_USERS"] = "false"
        os.environ["AQ_JWT_SECRET"] = "test-secret-sched"
        os.environ["AQ_ENV"] = "development"
        os.environ["AQ_MARKET_OFFLINE"] = "true"
        os.environ["AQ_MACRO_OFFLINE"] = "true"
        os.environ["AQ_WEB_OFFLINE"] = "true"

        self.client = TestClient(create_app())
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin12345"},
        )
        self.admin_token = resp.json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}

        resp2 = self.client.post(
            "/api/v1/auth/login",
            json={"username": "viewer", "password": "viewer12345"},
        )
        self.viewer_token = resp2.json()["access_token"]
        self.viewer_headers = {"Authorization": f"Bearer {self.viewer_token}"}

    def tearDown(self):
        self.client.close()
        for key, value in self._original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._temp_dir.cleanup()

    def _create_payload(self) -> dict:
        return {
            "name": "API Test Job",
            "report_type": "ledger",
            "format": "xlsx",
            "schedule_cron": "0 6 * * *",
            "recipient": "test@example.com",
        }

    def test_create_requires_auth(self):
        resp = self.client.post(
            "/api/v1/reports/schedule", json=self._create_payload()
        )
        self.assertEqual(resp.status_code, 401)

    def test_create_requires_admin(self):
        resp = self.client.post(
            "/api/v1/reports/schedule",
            json=self._create_payload(),
            headers=self.viewer_headers,
        )
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_create(self):
        resp = self.client.post(
            "/api/v1/reports/schedule",
            json=self._create_payload(),
            headers=self.admin_headers,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["name"], "API Test Job")
        self.assertTrue(body["is_active"])

    def test_list_jobs(self):
        self.client.post(
            "/api/v1/reports/schedule",
            json=self._create_payload(),
            headers=self.admin_headers,
        )
        resp = self.client.get(
            "/api/v1/reports/schedule", headers=self.admin_headers
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("jobs", body)
        self.assertGreaterEqual(body["total"], 1)

    def test_trigger_job(self):
        create_resp = self.client.post(
            "/api/v1/reports/schedule",
            json=self._create_payload(),
            headers=self.admin_headers,
        )
        job_id = create_resp.json()["id"]
        trigger_resp = self.client.post(
            f"/api/v1/reports/schedule/{job_id}/trigger",
            headers=self.admin_headers,
        )
        self.assertEqual(trigger_resp.status_code, 200)
        self.assertIn("download_path", trigger_resp.json())

    def test_trigger_missing_job_returns_404(self):
        resp = self.client.post(
            "/api/v1/reports/schedule/99999/trigger",
            headers=self.admin_headers,
        )
        self.assertEqual(resp.status_code, 404)

    def test_deactivate_job(self):
        create_resp = self.client.post(
            "/api/v1/reports/schedule",
            json=self._create_payload(),
            headers=self.admin_headers,
        )
        job_id = create_resp.json()["id"]
        del_resp = self.client.delete(
            f"/api/v1/reports/schedule/{job_id}",
            headers=self.admin_headers,
        )
        self.assertEqual(del_resp.status_code, 200)
        self.assertFalse(del_resp.json()["is_active"])

    def test_list_after_deactivate_active_only(self):
        create_resp = self.client.post(
            "/api/v1/reports/schedule",
            json=self._create_payload(),
            headers=self.admin_headers,
        )
        job_id = create_resp.json()["id"]
        self.client.delete(
            f"/api/v1/reports/schedule/{job_id}", headers=self.admin_headers
        )
        resp = self.client.get(
            "/api/v1/reports/schedule",
            params={"active_only": True},
            headers=self.admin_headers,
        )
        body = resp.json()
        self.assertEqual(body["total"], 0)


if __name__ == "__main__":
    unittest.main()
