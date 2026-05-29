"""BZ3: CommunityEngine — public changelog + roadmap voting.

## Felsefe — aidiyet hissi

Kullanıcı yayınlanan özellikleri görür → şeffaflık.
Roadmap'e oy verir → sözünü hissedilir kılar.
Yeni fikir önerir → ürünün ortağı olur.

## Tek engine, üç repository concern

Changelog ve roadmap birbiriyle ilişkili (shipped item → changelog
entry). Tek engine olarak birleştirildi; içsel olarak ayrı tabloları
yönetir.

## Vote toggle semantiği

vote(user, item):
  * Kullanıcı daha önce oy vermemişse → oy ekle, upvotes++
  * Vermişse → oy sil, upvotes--

upvotes denormalize column'dur — fast sort için. Her vote işlemi
transactional update.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any


VALID_CHANGELOG_CATEGORIES = {"feature", "fix", "improvement", "security"}
VALID_ROADMAP_CATEGORIES = {
    "feature", "integration", "analytics", "ux", "security", "mobile",
}
VALID_ROADMAP_STATUSES = {
    "idea", "planned", "in_progress", "shipped", "declined",
}


@dataclass(frozen=True)
class VoteResult:
    item_id: int
    user_id: str
    voted: bool        # True ise ekledim, False ise geri çektim
    upvotes_after: int


class CommunityEngine:
    """Changelog + roadmap public-facing operasyonlar."""

    DEFAULT_LIMIT = 50
    MAX_TITLE_LENGTH = 140
    MAX_DESCRIPTION_LENGTH = 2000

    def __init__(self, *, database_path: str) -> None:
        self._lock = Lock()
        self._conn = self._connect(database_path)

    @staticmethod
    def _connect(database_path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(database_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def close(self) -> None:
        self._conn.close()

    # ── Changelog ──────────────────────────────────────────────────────

    def publish_changelog_entry(
        self,
        *,
        version: str,
        title: str,
        description: str = "",
        category: str = "feature",
        released_at: int | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        """Yeni changelog girişi ekle (admin)."""
        self._validate_title(title)
        if category not in VALID_CHANGELOG_CATEGORIES:
            raise ValueError(
                f"Geçersiz kategori: {category!r}. "
                f"Geçerli: {sorted(VALID_CHANGELOG_CATEGORIES)}"
            )
        if len(description) > self.MAX_DESCRIPTION_LENGTH:
            raise ValueError(
                f"Açıklama {self.MAX_DESCRIPTION_LENGTH} karakteri geçemez"
            )
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO changelog_entries
                    (version, title, description, category,
                     is_published, released_at, created_at, created_by)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    version.strip()[:50],
                    title.strip(),
                    description.strip(),
                    category,
                    released_at or now,
                    now,
                    created_by,
                ),
            )
            self._conn.commit()
            entry_id = int(cur.lastrowid or 0)
        return self.get_changelog_entry(entry_id) or {}

    def list_changelog(
        self,
        *,
        limit: int = DEFAULT_LIMIT,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """Yayınlanmış changelog entry'leri (yeni → eski)."""
        query = """
            SELECT id, version, title, description, category,
                   released_at, created_at, created_by
            FROM changelog_entries
            WHERE is_published = 1
        """
        params: list[Any] = []
        if category is not None:
            if category not in VALID_CHANGELOG_CATEGORIES:
                raise ValueError(f"Geçersiz kategori: {category!r}")
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY released_at DESC LIMIT ?"
        params.append(min(max(1, limit), 200))
        with self._lock:
            rows = self._conn.execute(query, tuple(params)).fetchall()
        return [self._changelog_row_to_dict(r) for r in rows]

    def get_changelog_entry(self, entry_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT id, version, title, description, category,
                       released_at, created_at, created_by
                FROM changelog_entries
                WHERE id = ?
                """,
                (entry_id,),
            ).fetchone()
        return self._changelog_row_to_dict(row) if row else None

    # ── Roadmap ────────────────────────────────────────────────────────

    def submit_roadmap_idea(
        self,
        *,
        title: str,
        description: str,
        category: str,
        submitter: str,
    ) -> dict[str, Any]:
        """Kullanıcının fikir önerisi. Default status='idea'."""
        self._validate_title(title)
        if category not in VALID_ROADMAP_CATEGORIES:
            raise ValueError(
                f"Geçersiz kategori: {category!r}. "
                f"Geçerli: {sorted(VALID_ROADMAP_CATEGORIES)}"
            )
        if len(description) > self.MAX_DESCRIPTION_LENGTH:
            raise ValueError(
                f"Açıklama {self.MAX_DESCRIPTION_LENGTH} karakteri geçemez"
            )
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO roadmap_items
                    (title, description, category, status, upvotes,
                     submitter, created_at, updated_at)
                VALUES (?, ?, ?, 'idea', 0, ?, ?, ?)
                """,
                (
                    title.strip(),
                    description.strip(),
                    category,
                    submitter,
                    now, now,
                ),
            )
            self._conn.commit()
            item_id = int(cur.lastrowid or 0)
        return self.get_roadmap_item(item_id) or {}

    def update_roadmap_status(
        self,
        *,
        item_id: int,
        status: str,
        target_quarter: str | None = None,
        shipped_changelog_id: int | None = None,
    ) -> dict[str, Any] | None:
        """Admin: durum güncelleme + opsiyonel changelog bağlama."""
        if status not in VALID_ROADMAP_STATUSES:
            raise ValueError(
                f"Geçersiz status: {status!r}. "
                f"Geçerli: {sorted(VALID_ROADMAP_STATUSES)}"
            )
        if shipped_changelog_id is not None and status != "shipped":
            raise ValueError(
                "shipped_changelog_id sadece status='shipped' ile birlikte verilebilir"
            )
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE roadmap_items
                SET status = ?, target_quarter = ?,
                    shipped_changelog_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, target_quarter, shipped_changelog_id, now, item_id),
            )
            self._conn.commit()
            if cur.rowcount == 0:
                return None
        return self.get_roadmap_item(item_id)

    def list_roadmap(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        limit: int = DEFAULT_LIMIT,
        viewer_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Roadmap items — upvotes DESC sort.

        viewer_user_id verilirse her item'a has_voted flag eklenir.
        """
        query = """
            SELECT id, title, description, category, status, upvotes,
                   submitter, target_quarter, shipped_changelog_id,
                   created_at, updated_at
            FROM roadmap_items
        """
        clauses: list[str] = []
        params: list[Any] = []
        if status is not None:
            if status not in VALID_ROADMAP_STATUSES:
                raise ValueError(f"Geçersiz status: {status!r}")
            clauses.append("status = ?")
            params.append(status)
        if category is not None:
            if category not in VALID_ROADMAP_CATEGORIES:
                raise ValueError(f"Geçersiz kategori: {category!r}")
            clauses.append("category = ?")
            params.append(category)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY upvotes DESC, created_at DESC LIMIT ?"
        params.append(min(max(1, limit), 200))

        with self._lock:
            rows = self._conn.execute(query, tuple(params)).fetchall()
            items = [self._roadmap_row_to_dict(r) for r in rows]
            if viewer_user_id and items:
                ids = [it["id"] for it in items]
                placeholder = ",".join(["?"] * len(ids))
                voted_rows = self._conn.execute(
                    f"""
                    SELECT item_id FROM roadmap_votes
                    WHERE user_id = ? AND item_id IN ({placeholder})
                    """,
                    [viewer_user_id, *ids],
                ).fetchall()
                voted_set = {int(r["item_id"]) for r in voted_rows}
                for it in items:
                    it["has_voted"] = it["id"] in voted_set
        return items

    def get_roadmap_item(
        self, item_id: int, *, viewer_user_id: str | None = None,
    ) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT id, title, description, category, status, upvotes,
                       submitter, target_quarter, shipped_changelog_id,
                       created_at, updated_at
                FROM roadmap_items
                WHERE id = ?
                """,
                (item_id,),
            ).fetchone()
            if not row:
                return None
            item = self._roadmap_row_to_dict(row)
            if viewer_user_id:
                voted = self._conn.execute(
                    """
                    SELECT 1 FROM roadmap_votes
                    WHERE user_id = ? AND item_id = ?
                    """,
                    (viewer_user_id, item_id),
                ).fetchone()
                item["has_voted"] = voted is not None
        return item

    # ── Voting ─────────────────────────────────────────────────────────

    def toggle_vote(
        self, *, item_id: int, user_id: str,
    ) -> VoteResult:
        """Oy ekle veya geri çek. Item yoksa ValueError.

        Single transaction:
          INSERT OR rollback to DELETE, sonra upvotes recompute.
        """
        now = int(time.time())
        with self._lock:
            # Item var mı?
            exists = self._conn.execute(
                "SELECT id FROM roadmap_items WHERE id = ?",
                (item_id,),
            ).fetchone()
            if not exists:
                raise ValueError(f"Roadmap item bulunamadı: {item_id}")

            # Vote var mı?
            existing = self._conn.execute(
                """
                SELECT id FROM roadmap_votes
                WHERE user_id = ? AND item_id = ?
                """,
                (user_id, item_id),
            ).fetchone()

            if existing:
                # Geri çek
                self._conn.execute(
                    "DELETE FROM roadmap_votes WHERE id = ?",
                    (int(existing["id"]),),
                )
                voted = False
            else:
                # Ekle
                self._conn.execute(
                    """
                    INSERT INTO roadmap_votes (user_id, item_id, voted_at)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, item_id, now),
                )
                voted = True

            # Denormalized upvotes recompute (deterministic)
            count_row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM roadmap_votes WHERE item_id = ?",
                (item_id,),
            ).fetchone()
            new_count = int(count_row["n"]) if count_row else 0
            self._conn.execute(
                """
                UPDATE roadmap_items
                SET upvotes = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_count, now, item_id),
            )
            self._conn.commit()
        return VoteResult(
            item_id=item_id, user_id=user_id,
            voted=voted, upvotes_after=new_count,
        )

    # ── Stats (landing için) ───────────────────────────────────────────

    def public_stats(self) -> dict[str, int]:
        """Landing page için: yayınlanan özellik sayısı + roadmap stats."""
        with self._lock:
            shipped = self._conn.execute(
                "SELECT COUNT(*) AS n FROM changelog_entries WHERE is_published = 1"
            ).fetchone()
            in_progress = self._conn.execute(
                "SELECT COUNT(*) AS n FROM roadmap_items WHERE status = 'in_progress'"
            ).fetchone()
            planned = self._conn.execute(
                "SELECT COUNT(*) AS n FROM roadmap_items WHERE status = 'planned'"
            ).fetchone()
            ideas = self._conn.execute(
                "SELECT COUNT(*) AS n FROM roadmap_items WHERE status = 'idea'"
            ).fetchone()
            total_votes = self._conn.execute(
                "SELECT COUNT(*) AS n FROM roadmap_votes"
            ).fetchone()
        return {
            "shipped_features": int(shipped["n"]) if shipped else 0,
            "in_progress": int(in_progress["n"]) if in_progress else 0,
            "planned": int(planned["n"]) if planned else 0,
            "open_ideas": int(ideas["n"]) if ideas else 0,
            "total_votes": int(total_votes["n"]) if total_votes else 0,
        }

    # ── Internal helpers ───────────────────────────────────────────────

    def _validate_title(self, title: str) -> None:
        title = title.strip() if title else ""
        if not title:
            raise ValueError("Başlık boş olamaz")
        if len(title) > self.MAX_TITLE_LENGTH:
            raise ValueError(
                f"Başlık {self.MAX_TITLE_LENGTH} karakteri geçemez"
            )

    @staticmethod
    def _changelog_row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        return {
            "id": int(row["id"]),
            "version": str(row["version"]),
            "title": str(row["title"]),
            "description": str(row["description"] or ""),
            "category": str(row["category"]),
            "released_at": int(row["released_at"]),
            "created_at": int(row["created_at"]),
            "created_by": row["created_by"],
        }

    @staticmethod
    def _roadmap_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "title": str(row["title"]),
            "description": str(row["description"] or ""),
            "category": str(row["category"]),
            "status": str(row["status"]),
            "upvotes": int(row["upvotes"]),
            "submitter": row["submitter"],
            "target_quarter": row["target_quarter"],
            "shipped_changelog_id": (
                int(row["shipped_changelog_id"])
                if row["shipped_changelog_id"] is not None else None
            ),
            "created_at": int(row["created_at"]),
            "updated_at": int(row["updated_at"]),
            "has_voted": False,  # caller overrides
        }
