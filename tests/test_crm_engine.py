from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.crm_repository import CRMRepository
from app.engines.crm_engine import CRMEngine
from app.models import (
    CustomerCreateRequest,
    CustomerUpdateRequest,
    ProposalCreateRequest,
    ProposalStatusUpdateRequest,
)


def _setup() -> tuple[CRMEngine, CRMRepository, tempfile.TemporaryDirectory]:
    tmp = tempfile.TemporaryDirectory()
    # Repo doesn't create tables — migrations do. But for unit tests we bootstrap manually.
    repo = CRMRepository(str(Path(tmp.name) / "crm.db"))
    # Create tables directly (mirrors migrations 016)
    repo._conn.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL, full_name TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '',
            sector TEXT NOT NULL DEFAULT 'general', tags TEXT NOT NULL DEFAULT '[]',
            notes TEXT NOT NULL DEFAULT '', is_active INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL, customer_id INTEGER NOT NULL,
            title TEXT NOT NULL, amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'TRY',
            status TEXT NOT NULL DEFAULT 'draft',
            valid_until TEXT, description TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
        );
    """)
    repo._conn.commit()
    return CRMEngine(repo), repo, tmp


class CustomerTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.repo, self._tmp = _setup()

    def tearDown(self):
        self.repo.close()
        self._tmp.cleanup()

    def _create(self, company="Alpha Corp", name="Ahmet Yılmaz") -> object:
        return self.engine.create_customer(
            payload=CustomerCreateRequest(
                company=company, full_name=name,
                email="ahmet@example.com", phone="05001234567",
                sector="emlak", tags=["vip"], notes="Önemli müşteri",
            )
        )

    def test_create_returns_read(self):
        c = self._create()
        self.assertEqual(c.full_name, "Ahmet Yılmaz")
        self.assertEqual(c.company, "Alpha Corp")
        self.assertEqual(c.sector, "emlak")
        self.assertEqual(c.tags, ["vip"])
        self.assertTrue(c.is_active)

    def test_get_customer(self):
        c = self._create()
        fetched = self.engine.get_customer(c.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, c.id)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.engine.get_customer(9999))

    def test_list_customers(self):
        self._create("Acme", "Ali Veli")
        self._create("Acme", "Can Demir")
        result = self.engine.list_customers(company="Acme")
        self.assertEqual(result.total, 2)

    def test_list_active_only(self):
        c = self._create()
        self.engine.update_customer(c.id, payload=CustomerUpdateRequest(is_active=False))
        result = self.engine.list_customers(company="Alpha Corp", active_only=True)
        self.assertEqual(result.total, 0)

    def test_update_customer(self):
        c = self._create()
        updated = self.engine.update_customer(
            c.id,
            payload=CustomerUpdateRequest(full_name="Mehmet Kaya", sector="inşaat"),
        )
        self.assertEqual(updated.full_name, "Mehmet Kaya")
        self.assertEqual(updated.sector, "inşaat")

    def test_update_tags(self):
        c = self._create()
        updated = self.engine.update_customer(
            c.id,
            payload=CustomerUpdateRequest(tags=["premium", "yeni"]),
        )
        self.assertEqual(updated.tags, ["premium", "yeni"])


class ProposalTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.repo, self._tmp = _setup()
        self.customer = self.engine.create_customer(
            payload=CustomerCreateRequest(company="Beta Corp", full_name="Test Müşteri")
        )

    def tearDown(self):
        self.repo.close()
        self._tmp.cleanup()

    def _create_proposal(self, amount=50000.0) -> object:
        return self.engine.create_proposal(
            payload=ProposalCreateRequest(
                company="Beta Corp",
                customer_id=self.customer.id,
                title="Web Projesi Teklifi",
                amount=amount,
                currency="TRY",
                valid_until="2026-12-31",
                description="Detaylı proje teklifi",
            )
        )

    def test_create_proposal(self):
        p = self._create_proposal()
        self.assertEqual(p.status, "draft")
        self.assertEqual(p.amount, 50000.0)
        self.assertEqual(p.customer_id, self.customer.id)

    def test_get_proposal(self):
        p = self._create_proposal()
        fetched = self.engine.get_proposal(p.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.title, "Web Projesi Teklifi")

    def test_list_proposals(self):
        self._create_proposal(10000.0)
        self._create_proposal(20000.0)
        result = self.engine.list_proposals(company="Beta Corp")
        self.assertEqual(result.total, 2)

    def test_update_status_to_sent(self):
        p = self._create_proposal()
        updated = self.engine.update_proposal_status(
            p.id,
            payload=ProposalStatusUpdateRequest(status="sent"),
        )
        self.assertEqual(updated.status, "sent")

    def test_update_status_to_accepted(self):
        p = self._create_proposal()
        updated = self.engine.update_proposal_status(
            p.id,
            payload=ProposalStatusUpdateRequest(status="accepted"),
        )
        self.assertEqual(updated.status, "accepted")

    def test_proposal_summary(self):
        p = self._create_proposal(30000.0)
        self.engine.update_proposal_status(p.id, payload=ProposalStatusUpdateRequest(status="accepted"))
        self._create_proposal(10000.0)  # stays as draft
        summary = self.engine.proposal_summary(company="Beta Corp")
        self.assertEqual(summary.total_count, 2)
        self.assertEqual(summary.accepted_amount, 30000.0)
        self.assertIn("accepted", summary.by_status)

    def test_list_filter_by_status(self):
        p = self._create_proposal()
        self.engine.update_proposal_status(p.id, payload=ProposalStatusUpdateRequest(status="rejected"))
        self._create_proposal()  # still draft
        result = self.engine.list_proposals(company="Beta Corp", status="rejected")
        self.assertEqual(result.total, 1)


class CRMApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app import create_app

        self._tmp = tempfile.TemporaryDirectory()
        db = Path(self._tmp.name) / "crm_api.db"
        self._orig = {k: os.getenv(k) for k in [
            "AQ_DATABASE_PATH", "AQ_AUTH_USERS", "AQ_ENABLE_DEMO_USERS",
            "AQ_JWT_SECRET", "AQ_ENV", "AQ_MARKET_OFFLINE",
            "AQ_MACRO_OFFLINE", "AQ_WEB_OFFLINE",
        ]}
        os.environ.update({
            "AQ_DATABASE_PATH": str(db),
            "AQ_AUTH_USERS": "admin:admin12345:admin",
            "AQ_ENABLE_DEMO_USERS": "false",
            "AQ_JWT_SECRET": "crm-test-secret",
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

    def _seed_company(self) -> str:
        companies = self.client.get("/api/v1/companies", headers=self.headers).json()
        return companies[0]["name"] if companies else "Alpha"

    def test_create_customer_requires_auth(self):
        resp = self.client.post("/api/v1/crm/customers",
                                json={"company": "X", "full_name": "Y"})
        self.assertEqual(resp.status_code, 401)

    def test_create_and_get_customer(self):
        company = self._seed_company()
        resp = self.client.post(
            "/api/v1/crm/customers",
            json={"company": company, "full_name": "Zeynep Şahin",
                  "email": "z@x.com", "sector": "teknoloji"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 201)
        cid = resp.json()["id"]
        get_resp = self.client.get(f"/api/v1/crm/customers/{cid}", headers=self.headers)
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["full_name"], "Zeynep Şahin")

    def test_list_customers(self):
        company = self._seed_company()
        self.client.post("/api/v1/crm/customers",
                         json={"company": company, "full_name": "A"},
                         headers=self.headers)
        resp = self.client.get("/api/v1/crm/customers",
                               params={"company": company},
                               headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["total"], 1)

    def test_create_proposal(self):
        company = self._seed_company()
        c = self.client.post(
            "/api/v1/crm/customers",
            json={"company": company, "full_name": "Teklif Müşterisi"},
            headers=self.headers,
        ).json()
        resp = self.client.post(
            "/api/v1/crm/proposals",
            json={"company": company, "customer_id": c["id"],
                  "title": "Test Teklifi", "amount": 25000},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["status"], "draft")

    def test_proposal_summary(self):
        company = self._seed_company()
        resp = self.client.get("/api/v1/crm/proposals/summary",
                               params={"company": company},
                               headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("total_count", resp.json())

    def test_update_proposal_status(self):
        company = self._seed_company()
        c = self.client.post(
            "/api/v1/crm/customers",
            json={"company": company, "full_name": "Müşteri"},
            headers=self.headers,
        ).json()
        p = self.client.post(
            "/api/v1/crm/proposals",
            json={"company": company, "customer_id": c["id"],
                  "title": "T", "amount": 1000},
            headers=self.headers,
        ).json()
        resp = self.client.patch(
            f"/api/v1/crm/proposals/{p['id']}",
            json={"status": "sent"},
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "sent")

    def test_get_missing_customer_404(self):
        resp = self.client.get("/api/v1/crm/customers/99999", headers=self.headers)
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
