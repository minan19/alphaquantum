"""G+4: Audit hash chain tests — tamper detection.

Senaryo: 5 audit entry yazılır → zincir verify. Sonra entry içeriği veya
hash'i değiştirilir → tampering tespit edilir.

Kanıt-grade: bağımsız denetçi log dokunulup dokunulmadığını O(N) check ile
anlar.
"""
import tempfile
import unittest
from pathlib import Path

from app.audit_hash import (
    GENESIS_PREV_HASH,
    canonical_payload,
    compute_entry_hash,
    verify_chain_link,
    verify_entry,
)
from app.audit_repository import AuditRepository
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager


class AuditHashHelperTests(unittest.TestCase):
    """Pure function tests — DB'siz."""

    def test_canonical_payload_deterministic(self) -> None:
        entry1 = {
            "request_id": "abc",
            "username": "user",
            "role": "admin",
            "method": "GET",
            "path": "/x",
            "status_code": 200,
            "ip_address": None,
            "user_agent": None,
            "duration_ms": 12.5,
            "created_at": 1700000000,
            "event_type": None,
            "event_detail": None,
            "prev_hash": GENESIS_PREV_HASH,
        }
        # Aynı entry her zaman aynı string
        c1 = canonical_payload(entry1)
        c2 = canonical_payload(entry1)
        self.assertEqual(c1, c2)

    def test_canonical_payload_sorted_keys(self) -> None:
        entry = {"username": "a", "request_id": "b"}
        c = canonical_payload(entry)
        # username key alfabetik olarak request_id'den sonra
        # Ama canonical_payload bizim sabit field listemizi kullanıyor.
        # Bunlar None olur ama deterministik.
        self.assertIn('"request_id"', c)
        self.assertIn('"username"', c)

    def test_compute_entry_hash_64_char_hex(self) -> None:
        entry = {"created_at": 1, "prev_hash": GENESIS_PREV_HASH}
        h = compute_entry_hash(entry)
        self.assertEqual(len(h), 64)
        # Hex chars
        int(h, 16)  # raises if not hex

    def test_compute_entry_hash_changes_on_content_change(self) -> None:
        e1 = {"username": "alice", "created_at": 1, "prev_hash": "x"}
        e2 = {"username": "bob", "created_at": 1, "prev_hash": "x"}
        self.assertNotEqual(compute_entry_hash(e1), compute_entry_hash(e2))

    def test_verify_entry_detects_tampering(self) -> None:
        entry = {
            "request_id": "abc",
            "username": "user",
            "role": "admin",
            "method": "GET",
            "path": "/x",
            "status_code": 200,
            "ip_address": None,
            "user_agent": None,
            "duration_ms": 12.5,
            "created_at": 1700000000,
            "event_type": None,
            "event_detail": None,
            "prev_hash": GENESIS_PREV_HASH,
        }
        entry["entry_hash"] = compute_entry_hash(entry)
        self.assertTrue(verify_entry(entry))

        # Tamper content
        tampered = dict(entry)
        tampered["username"] = "evil"
        # entry_hash kalır eskisi → tampering tespit edilir
        self.assertFalse(verify_entry(tampered))

    def test_verify_chain_link_genesis(self) -> None:
        first = {"prev_hash": GENESIS_PREV_HASH}
        self.assertTrue(verify_chain_link(None, first))
        # Genesis sentinel uyumsuzluğu
        bad = {"prev_hash": "wrong"}
        self.assertFalse(verify_chain_link(None, bad))

    def test_verify_chain_link_continuation(self) -> None:
        prev = {"entry_hash": "abc123"}
        current = {"prev_hash": "abc123"}
        self.assertTrue(verify_chain_link(prev, current))
        # Mismatch
        bad = {"prev_hash": "xyz"}
        self.assertFalse(verify_chain_link(prev, bad))


class AuditRepositoryHashChainTests(unittest.TestCase):
    """DB-bound tests — verify chain integrity through writes + tampering."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "audit_chain_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

        bootstrap_repo = IdentityRepository(str(self._db_path))
        bootstrap_repo.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()
        self.repo = AuditRepository(str(self._db_path))

    def tearDown(self) -> None:
        self.repo.close()
        self.manager.close()
        self._temp_dir.cleanup()

    def _write_n_entries(self, n: int) -> None:
        for i in range(n):
            self.repo.write_log(
                request_id=f"req-{i}",
                username=f"user-{i}",
                role="admin",
                method="GET",
                path=f"/api/v1/test/{i}",
                status_code=200,
                ip_address="127.0.0.1",
                user_agent="test",
                duration_ms=float(i),
            )

    def test_first_entry_uses_genesis_prev_hash(self) -> None:
        self._write_n_entries(1)
        rows = self.repo.list_logs(limit=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["prev_hash"], GENESIS_PREV_HASH)
        self.assertIsNotNone(rows[0]["entry_hash"])

    def test_chain_links_consecutive_entries(self) -> None:
        self._write_n_entries(5)
        rows = self.repo.list_logs(limit=10)
        # list_logs DESC sıralı geliyor — ASC için id-sort
        rows.sort(key=lambda r: r["id"])
        # Her entry'nin prev_hash'i bir önceki entry'nin entry_hash'i
        for i in range(1, len(rows)):
            self.assertEqual(rows[i]["prev_hash"], rows[i - 1]["entry_hash"])

    def test_verify_chain_clean(self) -> None:
        self._write_n_entries(5)
        result = self.repo.verify_chain()
        self.assertTrue(result["verified"])
        self.assertEqual(result["checked_count"], 5)
        self.assertIsNone(result["first_break_id"])
        self.assertEqual(result["legacy_count"], 0)

    def test_verify_chain_detects_content_tampering(self) -> None:
        """Bir entry'nin content'i değiştirilince → entry_hash mismatch."""
        self._write_n_entries(5)
        # Tamper: entry 3'ün username'ini değiştir, entry_hash dokunulmaz
        # (saldırgan content değiştirir ama hash güncellemeyi unutur)
        self.repo._conn.execute(
            "UPDATE audit_logs SET username = ? WHERE id = 3",
            ("MALICIOUS",),
        )
        self.repo._conn.commit()

        result = self.repo.verify_chain()
        self.assertFalse(result["verified"])
        self.assertEqual(result["first_break_id"], 3)
        self.assertEqual(result["first_break_reason"], "entry_hash_mismatch")

    def test_verify_chain_detects_prev_hash_tampering(self) -> None:
        """Bir entry'nin prev_hash'i değiştirilince → zincir kırılır."""
        self._write_n_entries(5)
        # Tamper: entry 3'ün prev_hash'ini değiştir
        # entry_hash kendi içeriğine göre yeniden hesaplanırsa bu testi geçer,
        # ama önceki ile bağlantısı kopar.
        # Simulasyon: prev_hash'i değiştirip entry_hash'i de uygun şekilde
        # güncelleyen saldırgan senaryosu — ama önceki entry ile uyumsuz olur.
        self.repo._conn.execute(
            "UPDATE audit_logs SET prev_hash = ? WHERE id = 3",
            ("0" * 64,),  # genesis sentinel ile yer değiştir
        )
        self.repo._conn.commit()
        result = self.repo.verify_chain()
        self.assertFalse(result["verified"])
        self.assertEqual(result["first_break_id"], 3)

    def test_verify_chain_empty_table(self) -> None:
        result = self.repo.verify_chain()
        self.assertTrue(result["verified"])
        self.assertEqual(result["checked_count"], 0)
        self.assertIsNone(result["genesis_id"])

    def test_verify_chain_event_writes_also_chained(self) -> None:
        """write_event de hash chain'e dahil — business events de korunur."""
        self._write_n_entries(2)
        self.repo.write_event(
            username="cfo@x.tr",
            role="admin",
            event_type="transfer_approved",
            event_detail={"transfer_id": 42},
        )
        self._write_n_entries(1)

        rows = self.repo.list_logs(limit=10)
        rows.sort(key=lambda r: r["id"])
        # 4 entry: 2 log + 1 event + 1 log
        self.assertEqual(len(rows), 4)

        # Tüm zincir doğru
        result = self.repo.verify_chain()
        self.assertTrue(result["verified"])
        self.assertEqual(result["checked_count"], 4)

        # Event entry hash chain'e bağlı
        event_row = [r for r in rows if r["event_type"] == "transfer_approved"][0]
        prev_row = [r for r in rows if r["id"] == event_row["id"] - 1][0]
        self.assertEqual(event_row["prev_hash"], prev_row["entry_hash"])

    def test_chain_break_after_legacy_entries(self) -> None:
        """Pre-G+4 legacy entries (entry_hash NULL) doğru atlanır."""
        # Manual legacy entry insert (no hash columns)
        self.repo._conn.execute(
            """
            INSERT INTO audit_logs(request_id, username, role, method, path,
                status_code, ip_address, user_agent, duration_ms, created_at,
                event_type, event_detail, prev_hash, entry_hash)
            VALUES('legacy-1', 'old', 'user', 'GET', '/old', 200,
                   '1.1.1.1', '', 0.0, 1700000000, NULL, NULL, NULL, NULL)
            """
        )
        self.repo._conn.commit()
        # Now add hash chain entries
        self._write_n_entries(3)

        result = self.repo.verify_chain()
        self.assertTrue(result["verified"])
        self.assertEqual(result["checked_count"], 3)
        self.assertEqual(result["legacy_count"], 1)


if __name__ == "__main__":
    unittest.main()
