"""BZ3: CommunityEngine — changelog + roadmap voting testleri."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.engines.community_engine import CommunityEngine
from app.identity_repository import IdentityRepository
from app.migration_manager import MigrationManager


class CommunityEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "community_test.db"
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

        bootstrap = IdentityRepository(str(self._db_path))
        bootstrap.close()
        self.manager = MigrationManager(str(self._db_path), str(migrations_dir))
        self.manager.apply_all()

        self.engine = CommunityEngine(database_path=str(self._db_path))

    def tearDown(self) -> None:
        self.engine.close()
        self.manager.close()
        self._tmp.cleanup()

    # ── Changelog ──────────────────────────────────────────────────────

    def test_publish_changelog_entry(self) -> None:
        entry = self.engine.publish_changelog_entry(
            version="0.7.0",
            title="A2 Anomaly Detection yayınlandı",
            description="Self-learning cross-company sızıntı dedektörü",
            category="feature",
            created_by="admin",
        )
        self.assertGreater(entry["id"], 0)
        self.assertEqual(entry["version"], "0.7.0")
        self.assertEqual(entry["category"], "feature")
        self.assertEqual(entry["created_by"], "admin")

    def test_list_changelog_orders_by_released_desc(self) -> None:
        old = self.engine.publish_changelog_entry(
            version="0.5.0", title="Eski", released_at=1700000000,
        )
        new = self.engine.publish_changelog_entry(
            version="0.7.0", title="Yeni", released_at=1750000000,
        )
        entries = self.engine.list_changelog()
        self.assertGreaterEqual(len(entries), 2)
        self.assertEqual(entries[0]["id"], new["id"])
        self.assertEqual(entries[1]["id"], old["id"])

    def test_changelog_category_filter(self) -> None:
        self.engine.publish_changelog_entry(version="0.7", title="X", category="feature")
        self.engine.publish_changelog_entry(version="0.7.1", title="Y", category="fix")
        features = self.engine.list_changelog(category="feature")
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0]["category"], "feature")

    def test_publish_invalid_category_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.publish_changelog_entry(
                version="0.7", title="X", category="garbage",
            )

    def test_publish_empty_title_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.publish_changelog_entry(version="0.7", title="   ")

    def test_publish_too_long_description_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.publish_changelog_entry(
                version="0.7", title="X", description="x" * 2001,
            )

    # ── Roadmap submission ─────────────────────────────────────────────

    def test_submit_roadmap_idea_starts_in_idea_status(self) -> None:
        item = self.engine.submit_roadmap_idea(
            title="Logo Tiger commit pipeline",
            description="Staging'den gerçek tablolara aktarım",
            category="integration",
            submitter="ahmet",
        )
        self.assertEqual(item["status"], "idea")
        self.assertEqual(item["upvotes"], 0)
        self.assertEqual(item["submitter"], "ahmet")

    def test_submit_invalid_category_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.submit_roadmap_idea(
                title="X", description="x", category="garbage", submitter="u",
            )

    # ── Roadmap status updates ─────────────────────────────────────────

    def test_admin_can_promote_to_planned(self) -> None:
        item = self.engine.submit_roadmap_idea(
            title="X", description="x", category="feature", submitter="u",
        )
        updated = self.engine.update_roadmap_status(
            item_id=item["id"], status="planned",
            target_quarter="Q3 2026",
        )
        assert updated is not None
        self.assertEqual(updated["status"], "planned")
        self.assertEqual(updated["target_quarter"], "Q3 2026")

    def test_shipped_status_requires_changelog_link(self) -> None:
        """shipped_changelog_id sadece status='shipped' ile geçerli."""
        item = self.engine.submit_roadmap_idea(
            title="X", description="x", category="feature", submitter="u",
        )
        # status=planned + shipped_changelog_id → hata
        with self.assertRaises(ValueError):
            self.engine.update_roadmap_status(
                item_id=item["id"], status="planned",
                shipped_changelog_id=99,
            )

    def test_shipped_links_to_changelog(self) -> None:
        changelog = self.engine.publish_changelog_entry(
            version="0.8", title="Feature X yayınlandı",
        )
        item = self.engine.submit_roadmap_idea(
            title="Feature X", description="x", category="feature", submitter="u",
        )
        updated = self.engine.update_roadmap_status(
            item_id=item["id"], status="shipped",
            shipped_changelog_id=changelog["id"],
        )
        assert updated is not None
        self.assertEqual(updated["status"], "shipped")
        self.assertEqual(updated["shipped_changelog_id"], changelog["id"])

    def test_update_nonexistent_returns_none(self) -> None:
        result = self.engine.update_roadmap_status(
            item_id=99999, status="planned",
        )
        self.assertIsNone(result)

    # ── Voting ─────────────────────────────────────────────────────────

    def test_toggle_vote_adds_then_removes(self) -> None:
        item = self.engine.submit_roadmap_idea(
            title="X", description="x", category="feature", submitter="u",
        )
        result1 = self.engine.toggle_vote(item_id=item["id"], user_id="alice")
        self.assertTrue(result1.voted)
        self.assertEqual(result1.upvotes_after, 1)
        # İkinci toggle geri çeker
        result2 = self.engine.toggle_vote(item_id=item["id"], user_id="alice")
        self.assertFalse(result2.voted)
        self.assertEqual(result2.upvotes_after, 0)

    def test_vote_nonexistent_item_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.toggle_vote(item_id=99999, user_id="x")

    def test_multiple_users_vote_independently(self) -> None:
        item = self.engine.submit_roadmap_idea(
            title="X", description="x", category="feature", submitter="u",
        )
        self.engine.toggle_vote(item_id=item["id"], user_id="alice")
        self.engine.toggle_vote(item_id=item["id"], user_id="bob")
        result = self.engine.toggle_vote(item_id=item["id"], user_id="charlie")
        self.assertEqual(result.upvotes_after, 3)

    def test_list_roadmap_orders_by_upvotes_desc(self) -> None:
        a = self.engine.submit_roadmap_idea(
            title="A", description="x", category="feature", submitter="u",
        )
        b = self.engine.submit_roadmap_idea(
            title="B", description="x", category="feature", submitter="u",
        )
        # B'ye 2 oy, A'ya 1 oy
        self.engine.toggle_vote(item_id=b["id"], user_id="u1")
        self.engine.toggle_vote(item_id=b["id"], user_id="u2")
        self.engine.toggle_vote(item_id=a["id"], user_id="u3")

        items = self.engine.list_roadmap()
        self.assertEqual(items[0]["id"], b["id"])
        self.assertEqual(items[0]["upvotes"], 2)
        self.assertEqual(items[1]["id"], a["id"])
        self.assertEqual(items[1]["upvotes"], 1)

    def test_has_voted_flag_for_viewer(self) -> None:
        item = self.engine.submit_roadmap_idea(
            title="X", description="x", category="feature", submitter="u",
        )
        self.engine.toggle_vote(item_id=item["id"], user_id="alice")
        items = self.engine.list_roadmap(viewer_user_id="alice")
        self.assertTrue(items[0]["has_voted"])
        items_bob = self.engine.list_roadmap(viewer_user_id="bob")
        self.assertFalse(items_bob[0]["has_voted"])

    def test_get_roadmap_item_with_viewer(self) -> None:
        item = self.engine.submit_roadmap_idea(
            title="X", description="x", category="feature", submitter="u",
        )
        self.engine.toggle_vote(item_id=item["id"], user_id="alice")
        fetched = self.engine.get_roadmap_item(
            item["id"], viewer_user_id="alice",
        )
        assert fetched is not None
        self.assertTrue(fetched["has_voted"])

    # ── Filtering ──────────────────────────────────────────────────────

    def test_list_roadmap_status_filter(self) -> None:
        a = self.engine.submit_roadmap_idea(
            title="A", description="x", category="feature", submitter="u",
        )
        b = self.engine.submit_roadmap_idea(
            title="B", description="x", category="feature", submitter="u",
        )
        self.engine.update_roadmap_status(item_id=b["id"], status="planned")
        idea_only = self.engine.list_roadmap(status="idea")
        self.assertEqual(len(idea_only), 1)
        self.assertEqual(idea_only[0]["id"], a["id"])

    def test_list_roadmap_invalid_status_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.list_roadmap(status="garbage")

    # ── Stats ──────────────────────────────────────────────────────────

    def test_public_stats_aggregates(self) -> None:
        self.engine.publish_changelog_entry(version="0.1", title="X")
        self.engine.publish_changelog_entry(version="0.2", title="Y")
        item = self.engine.submit_roadmap_idea(
            title="A", description="x", category="feature", submitter="u",
        )
        self.engine.toggle_vote(item_id=item["id"], user_id="v1")
        self.engine.update_roadmap_status(
            item_id=item["id"], status="planned",
        )
        stats = self.engine.public_stats()
        self.assertGreaterEqual(stats["shipped_features"], 2)
        self.assertGreaterEqual(stats["planned"], 1)
        self.assertGreaterEqual(stats["total_votes"], 1)


if __name__ == "__main__":
    unittest.main()
