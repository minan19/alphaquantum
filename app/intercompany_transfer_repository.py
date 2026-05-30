"""G1.3: IntercompanyTransferRepository — atomic double-entry kalbi.

Karma sektörlü holding'in en kritik operasyonel feature'ı: grup içi transfer.
Bu repository, intercompany_transfers tablosu (migration 023) + atomic
write'la finance_ledger_entries'e 2 entry oluşturma mantığını yönetir.

Mimari kararlar:
  - Transaction atomicity: approve_atomic() tek transaction içinde
    UPDATE transfer status + 2 INSERT ledger entry + UPDATE ledger refs yapar.
    Herhangi bir adım fail olursa TÜM değişiklikler rollback edilir.
  - Optimistic locking: approve sırasında WHERE approval_status = 'pending'
    koşulu ile çakışma engellenir (eski state ile yazılırsa 0 row update,
    ValueError fırlatılır).
  - PostgreSQL-friendly: standart BEGIN, no SQLite-specific syntax.
    SQLite'da `conn` context manager auto-commit/rollback yapar.

4-eyes onay engine seviyesinde enforce edilir (repository sadece veri).
"""
from __future__ import annotations

from threading import Lock
from typing import Any
import sqlite3
import time

from app._sqlite_helpers import new_row_id


class IntercompanyTransferRepository:
    """Intercompany transfer state + atomic ledger writes."""

    def __init__(self, database_path: str) -> None:
        self._lock = Lock()
        self._conn = self._connect(database_path)

    @staticmethod
    def _connect(database_path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(database_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def close(self) -> None:
        self._conn.close()

    # ── CREATE ─────────────────────────────────────────────────────────

    def request_transfer(
        self,
        *,
        holding_id: int,
        from_company: str,
        to_company: str,
        amount: float,
        currency: str,
        description: str,
        requested_by: str,
        target_amount: float | None = None,
        fx_rate: float | None = None,
    ) -> dict[str, Any]:
        """Create a pending transfer (no ledger entries yet)."""
        now = int(time.time())
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO intercompany_transfers(
                    holding_id, from_company, to_company,
                    amount, currency, target_amount, fx_rate,
                    description, requested_by, requested_at,
                    approval_status
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    holding_id, from_company, to_company,
                    amount, currency, target_amount, fx_rate,
                    description, requested_by, now,
                ),
            )
            transfer_id = new_row_id(cursor)
            self._conn.commit()
        row = self.get_transfer(transfer_id)
        assert row is not None  # just inserted, must exist
        return row

    # ── READ ───────────────────────────────────────────────────────────

    def get_transfer(self, transfer_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM intercompany_transfers WHERE id = ?",
                (transfer_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_pending(self, *, holding_id: int) -> list[dict[str, Any]]:
        """Approval queue — onay bekleyenler (eskiden yeniye)."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM intercompany_transfers
                WHERE holding_id = ? AND approval_status = 'pending'
                ORDER BY requested_at ASC, id ASC
                """,
                (holding_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_by_holding(
        self, *, holding_id: int, limit: int = 200
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 1000))
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM intercompany_transfers
                WHERE holding_id = ?
                ORDER BY requested_at DESC, id DESC
                LIMIT ?
                """,
                (holding_id, safe_limit),
            ).fetchall()
        return [dict(row) for row in rows]

    # ── REJECT (basit state transition) ────────────────────────────────

    def reject(
        self,
        *,
        transfer_id: int,
        approver_user_id: str,
        reject_reason: str,
    ) -> dict[str, Any]:
        """Mark transfer as rejected. Optimistic lock on status='pending'."""
        now = int(time.time())
        with self._lock:
            cursor = self._conn.execute(
                """
                UPDATE intercompany_transfers
                SET approval_status = 'rejected',
                    approved_by = ?,
                    approved_at = ?,
                    reject_reason = ?
                WHERE id = ? AND approval_status = 'pending'
                """,
                (approver_user_id, now, reject_reason, transfer_id),
            )
            if cursor.rowcount == 0:
                self._conn.rollback()
                raise ValueError(
                    "Transfer not found or no longer pending — cannot reject"
                )
            self._conn.commit()
        result = self.get_transfer(transfer_id)
        if result is None:
            raise RuntimeError("Transfer disappeared after reject")
        return result

    # ── APPROVE (ATOMIC — kalbi) ───────────────────────────────────────

    def approve_atomic(
        self,
        *,
        transfer_id: int,
        approver_user_id: str,
    ) -> dict[str, Any]:
        """Atomic approve: pending → completed + 2 ledger entries.

        Tek transaction içinde:
          1. UPDATE intercompany_transfers status='approved' (optimistic lock)
          2. INSERT ledger entry (from_company, expense, intercompany_flag=1)
          3. INSERT ledger entry (to_company, income, intercompany_flag=1)
          4. UPDATE intercompany_transfers ledger_*_id refs + status='completed'

        Herhangi bir adım fail olursa TÜM transaction rollback edilir.
        SQLite'da `with conn:` block transaction yönetir — exception olursa
        otomatik rollback, success'te commit.

        Returns: tamamlanmış transfer state (ledger ref'ler dahil).
        """
        with self._lock:
            try:
                # Adım 0: Mevcut transfer'i oku
                row = self._conn.execute(
                    "SELECT * FROM intercompany_transfers WHERE id = ?",
                    (transfer_id,),
                ).fetchone()
                if row is None:
                    raise ValueError(f"Transfer {transfer_id} not found")
                if row["approval_status"] != "pending":
                    raise ValueError(
                        f"Transfer {transfer_id} not in pending state "
                        f"(current: {row['approval_status']})"
                    )

                # Atomic block — herhangi exception → rollback
                self._conn.execute("BEGIN IMMEDIATE")

                now = int(time.time())
                today = time.strftime("%Y-%m-%d", time.gmtime(now))

                # Adım 1: Optimistic update (yarış koşulu için)
                cursor = self._conn.execute(
                    """
                    UPDATE intercompany_transfers
                    SET approval_status = 'approved',
                        approved_by = ?,
                        approved_at = ?
                    WHERE id = ? AND approval_status = 'pending'
                    """,
                    (approver_user_id, now, transfer_id),
                )
                if cursor.rowcount == 0:
                    raise ValueError(
                        f"Transfer {transfer_id} state changed during approval "
                        f"— optimistic lock conflict"
                    )

                # Hedef tutar (cross-currency desteği)
                source_amount = float(row["amount"])
                target_amount = (
                    float(row["target_amount"])
                    if row["target_amount"] is not None
                    else source_amount
                )
                description = str(row["description"] or "intercompany transfer")

                # Adım 2: Ledger entry — kaynak şirket (expense)
                from_cursor = self._conn.execute(
                    """
                    INSERT INTO finance_ledger_entries(
                        company_name, entry_type, amount, category,
                        description, entry_date, created_at,
                        counterparty_company, transfer_id, intercompany_flag
                    ) VALUES(?, 'expense', ?, 'intercompany_transfer',
                              ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        row["from_company"], source_amount,
                        description, today, now,
                        row["to_company"], transfer_id,
                    ),
                )
                ledger_from_id = new_row_id(from_cursor)

                # Adım 3: Ledger entry — hedef şirket (income)
                to_cursor = self._conn.execute(
                    """
                    INSERT INTO finance_ledger_entries(
                        company_name, entry_type, amount, category,
                        description, entry_date, created_at,
                        counterparty_company, transfer_id, intercompany_flag
                    ) VALUES(?, 'income', ?, 'intercompany_transfer',
                              ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        row["to_company"], target_amount,
                        description, today, now,
                        row["from_company"], transfer_id,
                    ),
                )
                ledger_to_id = new_row_id(to_cursor)

                # Adım 4: Final state — completed + ref'ler
                self._conn.execute(
                    """
                    UPDATE intercompany_transfers
                    SET approval_status = 'completed',
                        completed_at = ?,
                        ledger_entry_from_id = ?,
                        ledger_entry_to_id = ?
                    WHERE id = ?
                    """,
                    (now, ledger_from_id, ledger_to_id, transfer_id),
                )

                self._conn.commit()

            except Exception:
                self._conn.rollback()
                raise

        result = self.get_transfer(transfer_id)
        if result is None:
            raise RuntimeError("Transfer disappeared after approve")
        return result
