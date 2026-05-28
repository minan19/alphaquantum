"""A4: KVKK Engine + API tests.

Coverage:
- KVKKEngine unit tests (consent, deletion lifecycle, incident, HMAC export)
- /api/v1/me/* user-facing endpoints (data subject rights, KVKK madde 11)
- /api/v1/admin/kvkk/* admin endpoints (decision + incident, madde 12)
- /api/v1/data-processing-activities (transparency, madde 13)
"""
import hashlib
import hmac
import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import create_app
from app.engines.kvkk_engine import KVKKEngine
from app.identity_repository import IdentityRepository
from app.kvkk_repository import KVKKRepository
from app.migration_manager import MigrationManager


class KVKKEngineUnitTests(unittest.TestCase):
    """KVKKEngine.* methods exercised directly without FastAPI overhead."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "kvkk_unit.db"
        self._migrations_dir = (
            Path(__file__).resolve().parent.parent / "migrations"
        )

        # bootstrap schema + apply all migrations (incl. 022 KVKK)
        IdentityRepository(str(self._db_path)).close()
        self.migrations = MigrationManager(
            str(self._db_path), str(self._migrations_dir)
        )
        self.migrations.apply_all()

        self.kvkk_repo = KVKKRepository(str(self._db_path))
        self.identity_repo = IdentityRepository(str(self._db_path))
        self.engine = KVKKEngine(
            kvkk_repo=self.kvkk_repo, identity_repo=self.identity_repo
        )

        # seed a role + user via the public IdentityRepository API
        self.identity_repo.create_role("viewer", "test viewer role")
        user = self.identity_repo.create_user(
            username="testuser",
            password_hash="x" * 64,
            role_name="viewer",
        )
        self.user_id = int(user["id"])

    def _username_now(self) -> str:
        row = self.identity_repo._conn.execute(  # type: ignore[attr-defined]
            "SELECT username FROM users WHERE id = ?", (self.user_id,)
        ).fetchone()
        return str(row["username"])

    def tearDown(self) -> None:
        self.kvkk_repo.close()
        self.identity_repo.close()
        self.migrations.close()
        self._temp_dir.cleanup()

    def test_record_and_get_consent(self) -> None:
        status = self.engine.record_consent(self.user_id, version="v2")
        self.assertEqual(status.consent_version, "v2")
        self.assertGreater(status.consent_at, 0)

        fetched = self.engine.get_consent_status(self.user_id)
        self.assertEqual(fetched.consent_version, "v2")

    def test_export_user_data_is_hmac_signed_and_stable(self) -> None:
        resp = self.engine.export_user_data(
            self.user_id,
            username="testuser",
            role="viewer",
            company_scopes=["*"],
            created_at=1700000000,
            updated_at=1700000000,
            signing_secret="secret-abc",
        )
        self.assertTrue(resp.export_signature.startswith("hmac-sha256="))
        # signature must verify over the canonical payload structure
        payload = {
            "user_id": self.user_id,
            "username": "testuser",
            "role": "viewer",
            "company_scopes": ["*"],
            "created_at": 1700000000,
            "updated_at": 1700000000,
            "consent_at": resp.kvkk_consent["consent_at"],
            "consent_version": resp.kvkk_consent["consent_version"],
            "exported_at": resp.exported_at,
        }
        expected = hmac.new(
            b"secret-abc",
            json.dumps(payload, sort_keys=True).encode(),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(resp.export_signature, f"hmac-sha256={expected}")

    def test_deletion_request_lifecycle_approve_anonymizes(self) -> None:
        created = self.engine.create_deletion_request(
            user_id=self.user_id, reason="GDPR-aligned right to erasure"
        )
        self.assertEqual(created.status, "pending")

        decided = self.engine.decide_deletion(
            created.id,
            decision="approved",
            decision_by=self.user_id,
            decision_note="OK",
        )
        self.assertIsNotNone(decided)
        assert decided is not None  # narrow type for mypy
        self.assertEqual(decided.status, "completed")
        self.assertTrue(len(decided.anonymized_fields) > 0)

        # user PII must be anonymized post-flow
        self.assertNotEqual(self._username_now(), "testuser")

    def test_deletion_request_lifecycle_reject_preserves_data(self) -> None:
        created = self.engine.create_deletion_request(
            user_id=self.user_id, reason="test"
        )
        decided = self.engine.decide_deletion(
            created.id,
            decision="rejected",
            decision_by=self.user_id,
            decision_note="not eligible",
        )
        assert decided is not None
        self.assertEqual(decided.status, "rejected")

        # username untouched
        self.assertEqual(self._username_now(), "testuser")

    def test_incident_high_severity_sets_kvkk_notification_required(
        self,
    ) -> None:
        inc = self.engine.report_incident(
            reported_by=self.user_id,
            incident_type="unauthorized_access",
            severity="high",
            description="Login from suspicious IP",
            affected_record_count=42,
        )
        self.assertTrue(inc.kvkk_notification_required)
        self.assertEqual(inc.severity, "high")
        self.assertEqual(inc.resolution_status, "open")

    def test_incident_low_severity_no_notification_required(self) -> None:
        inc = self.engine.report_incident(
            reported_by=self.user_id,
            incident_type="rate_limit_burst",
            severity="low",
            description="benign",
        )
        self.assertFalse(inc.kvkk_notification_required)

    def test_processing_activities_static_contract(self) -> None:
        resp = self.engine.get_processing_activities()
        self.assertGreaterEqual(len(resp.activities), 6)
        # every activity must declare a legal basis (KVKK madde 13 zorunluluğu)
        for a in resp.activities:
            self.assertTrue(a.legal_basis.startswith("KVKK") or "rıza" in a.legal_basis)


class KVKKApiTests(unittest.TestCase):
    """End-to-end via FastAPI TestClient — auth + RBAC included."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "kvkk_api.db"
        self._original_env = {
            k: os.getenv(k)
            for k in (
                "AQ_DATABASE_PATH",
                "AQ_AUTH_USERS",
                "AQ_ENABLE_DEMO_USERS",
                "AQ_JWT_SECRET",
                "AQ_ENV",
                "AQ_MARKET_OFFLINE",
                "AQ_MACRO_OFFLINE",
                "AQ_WEB_OFFLINE",
            )
        }
        os.environ["AQ_DATABASE_PATH"] = str(self._db_path)
        os.environ["AQ_AUTH_USERS"] = (
            "admin:admin12345:admin,viewer:viewer12345:viewer"
        )
        os.environ["AQ_ENABLE_DEMO_USERS"] = "false"
        os.environ["AQ_JWT_SECRET"] = "kvkk-test-secret"
        os.environ["AQ_ENV"] = "development"
        os.environ["AQ_MARKET_OFFLINE"] = "true"
        os.environ["AQ_MACRO_OFFLINE"] = "true"
        os.environ["AQ_WEB_OFFLINE"] = "true"

        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.client.close()
        for k, v in self._original_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._temp_dir.cleanup()

    def _token(self, username: str, password: str) -> str:
        r = self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["access_token"]

    def test_consent_and_export_roundtrip(self) -> None:
        token = self._token("viewer", "viewer12345")
        headers = {"Authorization": f"Bearer {token}"}

        # consent
        r = self.client.post(
            "/api/v1/me/consent",
            headers=headers,
            json={"consent_version": "v1"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["consent_version"], "v1")

        # consent status fetch
        r = self.client.get("/api/v1/me/consent", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["consent_version"], "v1")

        # data export — HMAC signed
        r = self.client.get("/api/v1/me/data", headers=headers)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["export_signature"].startswith("hmac-sha256="))
        self.assertEqual(body["username"], "viewer")

    def test_deletion_request_user_can_create_admin_decides(self) -> None:
        viewer_tok = self._token("viewer", "viewer12345")
        admin_tok = self._token("admin", "admin12345")

        # viewer opens a deletion request
        r = self.client.post(
            "/api/v1/me/deletion-request",
            headers={"Authorization": f"Bearer {viewer_tok}"},
            json={"reason": "I want my data removed"},
        )
        self.assertEqual(r.status_code, 201, r.text)
        request_id = r.json()["id"]
        self.assertEqual(r.json()["status"], "pending")

        # viewer cannot decide (admin permission required)
        r = self.client.post(
            f"/api/v1/admin/kvkk/deletion-requests/{request_id}",
            headers={"Authorization": f"Bearer {viewer_tok}"},
            json={"decision": "approved", "decision_note": "self"},
        )
        self.assertEqual(r.status_code, 403)

        # admin lists pending
        r = self.client.get(
            "/api/v1/admin/kvkk/deletion-requests?status=pending",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.json()["total"], 1)

        # admin rejects
        r = self.client.post(
            f"/api/v1/admin/kvkk/deletion-requests/{request_id}",
            headers={"Authorization": f"Bearer {admin_tok}"},
            json={"decision": "rejected", "decision_note": "policy hold"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "rejected")

        # second decision attempt should 400 (not pending anymore)
        r = self.client.post(
            f"/api/v1/admin/kvkk/deletion-requests/{request_id}",
            headers={"Authorization": f"Bearer {admin_tok}"},
            json={"decision": "approved", "decision_note": "flip"},
        )
        self.assertEqual(r.status_code, 400)

    def test_incident_report_admin_only(self) -> None:
        viewer_tok = self._token("viewer", "viewer12345")
        admin_tok = self._token("admin", "admin12345")

        # viewer blocked
        r = self.client.post(
            "/api/v1/admin/kvkk/incidents",
            headers={"Authorization": f"Bearer {viewer_tok}"},
            json={
                "incident_type": "data_leak",
                "severity": "critical",
                "description": "x",
            },
        )
        self.assertEqual(r.status_code, 403)

        # admin can create — critical → notification_required must auto-set
        r = self.client.post(
            "/api/v1/admin/kvkk/incidents",
            headers={"Authorization": f"Bearer {admin_tok}"},
            json={
                "incident_type": "data_leak",
                "severity": "critical",
                "description": "leaked PII via misconfigured S3",
                "affected_record_count": 1000,
            },
        )
        self.assertEqual(r.status_code, 201, r.text)
        body = r.json()
        self.assertTrue(body["kvkk_notification_required"])

        # admin list filtering
        r = self.client.get(
            "/api/v1/admin/kvkk/incidents?severity=critical",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.json()["total"], 1)

    def test_processing_activities_public_to_authenticated_users(self) -> None:
        token = self._token("viewer", "viewer12345")
        r = self.client.get(
            "/api/v1/data-processing-activities",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("activities", body)
        self.assertGreaterEqual(len(body["activities"]), 6)


if __name__ == "__main__":
    unittest.main()
