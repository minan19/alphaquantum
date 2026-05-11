from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.task_repository import TaskRepository
from app.engines.task_engine import TaskEngine
from app.models import TaskCreateRequest, TaskUpdateRequest


def _setup() -> tuple[TaskEngine, TaskRepository, tempfile.TemporaryDirectory]:
    tmp = tempfile.TemporaryDirectory()
    repo = TaskRepository(str(Path(tmp.name) / "tasks.db"))
    repo._conn.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL, full_name TEXT NOT NULL,
            created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL, title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', assigned_to TEXT NOT NULL DEFAULT '',
            priority TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'open',
            due_date TEXT, customer_id INTEGER,
            created_by TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
        );
    """)
    repo._conn.commit()
    return TaskEngine(repo), repo, tmp


class TaskEngineUnitTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.repo, self._tmp = _setup()

    def tearDown(self):
        self.repo.close()
        self._tmp.cleanup()

    def _create(self, title="Rapor Hazırla", company="Alpha", assigned="ali") -> object:
        return self.engine.create_task(
            payload=TaskCreateRequest(
                company=company, title=title,
                assigned_to=assigned, priority="high",
                due_date="2026-12-31",
            ),
            created_by="admin",
        )

    def test_create_returns_read(self):
        t = self._create()
        self.assertEqual(t.title, "Rapor Hazırla")
        self.assertEqual(t.status, "open")
        self.assertEqual(t.priority, "high")
        self.assertEqual(t.created_by, "admin")

    def test_get_task(self):
        t = self._create()
        fetched = self.engine.get_task(t.id)
        self.assertEqual(fetched.id, t.id)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.engine.get_task(9999))

    def test_list_tasks(self):
        self._create("T1")
        self._create("T2")
        result = self.engine.list_tasks(company="Alpha")
        self.assertEqual(result.total, 2)

    def test_list_filter_by_status(self):
        t = self._create()
        self.engine.update_task(t.id, payload=TaskUpdateRequest(status="done"))
        open_tasks = self.engine.list_tasks(company="Alpha", status="open")
        self.assertEqual(open_tasks.total, 0)

    def test_update_status(self):
        t = self._create()
        updated = self.engine.update_task(
            t.id, payload=TaskUpdateRequest(status="in_progress")
        )
        self.assertEqual(updated.status, "in_progress")

    def test_update_assignment(self):
        t = self._create()
        updated = self.engine.update_task(
            t.id, payload=TaskUpdateRequest(assigned_to="mehmet")
        )
        self.assertEqual(updated.assigned_to, "mehmet")

    def test_status_summary_counts(self):
        t1 = self._create("T1")
        t2 = self._create("T2")
        self.engine.update_task(t1.id, payload=TaskUpdateRequest(status="done"))
        self.engine.update_task(t2.id, payload=TaskUpdateRequest(status="in_progress"))
        summary = self.engine.status_summary(company="Alpha")
        self.assertEqual(summary.done, 1)
        self.assertEqual(summary.in_progress, 1)
        self.assertEqual(summary.open, 0)
        self.assertEqual(summary.total, 2)

    def test_overdue_count(self):
        self.engine.create_task(
            payload=TaskCreateRequest(
                company="Alpha", title="Eski Görev",
                due_date="2020-01-01",  # past date
            )
        )
        summary = self.engine.status_summary(company="Alpha")
        self.assertEqual(summary.overdue, 1)

    def test_list_overdue_only(self):
        self.engine.create_task(
            payload=TaskCreateRequest(
                company="Alpha", title="Gecikmiş",
                due_date="2020-01-01",
            )
        )
        self._create("Gelecek görev")  # due 2026
        result = self.engine.list_tasks(company="Alpha", overdue_only=True)
        self.assertEqual(result.total, 1)
        self.assertEqual(result.tasks[0].title, "Gecikmiş")

    def test_filter_by_assigned_to(self):
        self._create(assigned="ali")
        self._create(assigned="veli")
        result = self.engine.list_tasks(company="Alpha", assigned_to="ali")
        self.assertEqual(result.total, 1)


class TaskApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app import create_app

        self._tmp = tempfile.TemporaryDirectory()
        db = Path(self._tmp.name) / "task_api.db"
        self._orig = {k: os.getenv(k) for k in [
            "AQ_DATABASE_PATH", "AQ_AUTH_USERS", "AQ_ENABLE_DEMO_USERS",
            "AQ_JWT_SECRET", "AQ_ENV", "AQ_MARKET_OFFLINE",
            "AQ_MACRO_OFFLINE", "AQ_WEB_OFFLINE",
        ]}
        os.environ.update({
            "AQ_DATABASE_PATH": str(db),
            "AQ_AUTH_USERS": "admin:admin12345:admin",
            "AQ_ENABLE_DEMO_USERS": "false",
            "AQ_JWT_SECRET": "task-test-secret",
            "AQ_ENV": "development",
            "AQ_MARKET_OFFLINE": "true",
            "AQ_MACRO_OFFLINE": "true",
            "AQ_WEB_OFFLINE": "true",
        })
        self.client = TestClient(create_app())
        token = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin12345"},
        ).json()["access_token"]
        self.headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        self.client.close()
        for k, v in self._orig.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
        self._tmp.cleanup()

    def _company(self) -> str:
        companies = self.client.get("/api/v1/companies", headers=self.headers).json()
        return companies[0]["name"] if companies else "Alpha"

    def test_create_requires_auth(self):
        resp = self.client.post("/api/v1/tasks",
                                json={"company": "X", "title": "Y"})
        self.assertEqual(resp.status_code, 401)

    def test_create_task(self):
        company = self._company()
        resp = self.client.post(
            "/api/v1/tasks",
            json={"company": company, "title": "Fatura Kontrol",
                  "priority": "high", "due_date": "2026-12-31"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["status"], "open")

    def test_list_tasks(self):
        company = self._company()
        self.client.post("/api/v1/tasks",
                         json={"company": company, "title": "Görev 1"},
                         headers=self.headers)
        resp = self.client.get("/api/v1/tasks",
                               params={"company": company},
                               headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["total"], 1)

    def test_task_summary(self):
        company = self._company()
        resp = self.client.get("/api/v1/tasks/summary",
                               params={"company": company},
                               headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("open", body)
        self.assertIn("overdue", body)

    def test_update_task_status(self):
        company = self._company()
        t = self.client.post(
            "/api/v1/tasks",
            json={"company": company, "title": "Güncellenecek Görev"},
            headers=self.headers,
        ).json()
        resp = self.client.patch(
            f"/api/v1/tasks/{t['id']}",
            json={"status": "done"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "done")

    def test_get_missing_task_404(self):
        resp = self.client.patch(
            "/api/v1/tasks/99999",
            json={"status": "done"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
