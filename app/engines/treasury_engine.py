"""T1: TreasuryEngine — multi-bank konsolide bakiye + trend.

## Felsefe

Holding CFO her sabah ilk soruyu sorar: "Toplam kasamda ne var?"
5 şirket × 8 hesap = 40 ekran → manuel toplama. Bu engine: tüm
hesaplar tek dashboard, currency-aware konsolidasyon, günlük trend.

## Currency conversion

Tüm hesapları tek currency'e (TRY default) çevirip toplam ver.
FX rate'leri G1.4 group_fx_engine'den alır; yoksa 1.0 fallback.

## CSV import

Banka extresi CSV upload → balance_history snapshot.
Minimal format: tarih (YYYY-MM-DD), bakiye (sayı). Genişletilebilir.
"""
from __future__ import annotations

import csv
import io
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any


VALID_ACCOUNT_TYPES = frozenset({
    "vadesiz", "vadeli", "kredi", "pos", "doviz", "diğer",
})

VALID_SNAPSHOT_SOURCES = frozenset({
    "manual", "csv_import", "mt940", "camt053", "open_banking",
})


@dataclass(frozen=True)
class TreasuryAccountView:
    id: int
    user_id: str
    company_name: str
    bank_name: str
    branch: str | None
    iban: str | None
    account_no: str | None
    account_type: str
    currency: str
    current_balance: float
    last_synced_at: int | None
    is_active: bool
    notes: str | None
    created_at: int
    updated_at: int


@dataclass(frozen=True)
class TreasurySummary:
    """Konsolide bakiye özeti."""

    total_in_try: float
    by_currency: dict[str, float] = field(default_factory=dict)
    by_bank: list[dict[str, Any]] = field(default_factory=list)
    by_company: list[dict[str, Any]] = field(default_factory=list)
    account_count: int = 0
    last_synced_at: int | None = None


class TreasuryEngine:
    """Multi-bank treasury account management."""

    def __init__(
        self,
        *,
        database_path: str,
        fx_rates: dict[str, float] | None = None,
    ) -> None:
        self._lock = Lock()
        self._database_path = database_path
        # FX: currency code → TRY rate. None = sadece TRY varsayım.
        self._fx_rates = fx_rates or {"TRY": 1.0}

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._database_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ── CRUD ───────────────────────────────────────────────────────────

    def add_account(
        self,
        *,
        user_id: str,
        company_name: str,
        bank_name: str,
        iban: str | None = None,
        account_no: str | None = None,
        branch: str | None = None,
        account_type: str = "vadesiz",
        currency: str = "TRY",
        current_balance: float = 0,
        notes: str | None = None,
    ) -> TreasuryAccountView:
        if account_type not in VALID_ACCOUNT_TYPES:
            raise ValueError(f"Geçersiz hesap tipi: {account_type!r}")
        if iban:
            iban = self._clean_iban(iban)
        currency = currency.upper().strip()
        if len(currency) != 3:
            raise ValueError(f"Geçersiz currency: {currency!r}")
        if not iban and not account_no:
            raise ValueError("IBAN veya account_no zorunlu")

        now = int(time.time())
        with self._lock:
            conn = self._connect()
            try:
                try:
                    cur = conn.execute(
                        """
                        INSERT INTO treasury_accounts
                            (user_id, company_name, bank_name, branch,
                             iban, account_no, account_type, currency,
                             current_balance, last_synced_at, is_active,
                             notes, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                        """,
                        (
                            user_id, company_name, bank_name, branch,
                            iban, account_no, account_type, currency,
                            float(current_balance), now if current_balance != 0 else None,
                            notes, now, now,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise ValueError(
                        f"Bu IBAN zaten kayıtlı: {iban!r}"
                    ) from exc
                conn.commit()
                account_id = int(cur.lastrowid or 0)
                # Initial balance snapshot
                if current_balance != 0:
                    today = datetime.now().strftime("%Y-%m-%d")
                    self._upsert_snapshot(
                        conn, account_id=account_id,
                        snapshot_date=today,
                        balance=float(current_balance),
                        source="manual",
                    )
                    conn.commit()
            finally:
                conn.close()
        view = self.get_account(user_id=user_id, account_id=account_id)
        assert view is not None
        return view

    def update_balance(
        self,
        *,
        user_id: str,
        account_id: int,
        new_balance: float,
        source: str = "manual",
        snapshot_date: str | None = None,
    ) -> TreasuryAccountView:
        if source not in VALID_SNAPSHOT_SOURCES:
            raise ValueError(f"Geçersiz source: {source!r}")
        if snapshot_date:
            try:
                datetime.strptime(snapshot_date, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError(
                    f"Geçersiz tarih: {snapshot_date!r}",
                ) from exc
        else:
            snapshot_date = datetime.now().strftime("%Y-%m-%d")

        now = int(time.time())
        with self._lock:
            conn = self._connect()
            try:
                # Ownership check
                owner = conn.execute(
                    "SELECT user_id FROM treasury_accounts WHERE id = ?",
                    (account_id,),
                ).fetchone()
                if not owner:
                    raise ValueError(f"Hesap bulunamadı: {account_id}")
                if owner["user_id"] != user_id:
                    raise PermissionError("Bu hesap sizin değil")

                conn.execute(
                    """
                    UPDATE treasury_accounts
                    SET current_balance = ?, last_synced_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (float(new_balance), now, now, account_id),
                )
                self._upsert_snapshot(
                    conn, account_id=account_id,
                    snapshot_date=snapshot_date,
                    balance=float(new_balance), source=source,
                )
                conn.commit()
            finally:
                conn.close()
        view = self.get_account(user_id=user_id, account_id=account_id)
        assert view is not None
        return view

    def get_account(
        self, *, user_id: str, account_id: int,
    ) -> TreasuryAccountView | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT id, user_id, company_name, bank_name, branch,
                           iban, account_no, account_type, currency,
                           current_balance, last_synced_at, is_active,
                           notes, created_at, updated_at
                    FROM treasury_accounts
                    WHERE id = ? AND user_id = ?
                    """,
                    (account_id, user_id),
                ).fetchone()
            finally:
                conn.close()
        return self._row_to_view(row) if row else None

    def list_accounts(
        self, *, user_id: str, active_only: bool = True,
    ) -> list[TreasuryAccountView]:
        query = """
            SELECT id, user_id, company_name, bank_name, branch,
                   iban, account_no, account_type, currency,
                   current_balance, last_synced_at, is_active,
                   notes, created_at, updated_at
            FROM treasury_accounts
            WHERE user_id = ?
        """
        params: list[Any] = [user_id]
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY current_balance DESC"
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(query, tuple(params)).fetchall()
            finally:
                conn.close()
        return [self._row_to_view(r) for r in rows]

    # ── Consolidated summary ───────────────────────────────────────────

    def summary(self, *, user_id: str) -> TreasurySummary:
        accounts = self.list_accounts(user_id=user_id)

        by_currency: dict[str, float] = {}
        by_bank: dict[str, float] = {}
        by_company: dict[str, float] = {}
        total_try = 0.0
        last_synced: int | None = None

        for a in accounts:
            by_currency[a.currency] = by_currency.get(a.currency, 0) + a.current_balance
            in_try = a.current_balance * self._fx_rates.get(a.currency, 1.0)
            total_try += in_try
            by_bank[a.bank_name] = by_bank.get(a.bank_name, 0) + in_try
            by_company[a.company_name] = by_company.get(a.company_name, 0) + in_try
            if a.last_synced_at:
                if last_synced is None or a.last_synced_at > last_synced:
                    last_synced = a.last_synced_at

        return TreasurySummary(
            total_in_try=round(total_try, 2),
            by_currency={k: round(v, 2) for k, v in by_currency.items()},
            by_bank=[
                {"bank_name": k, "total_try": round(v, 2)}
                for k, v in sorted(by_bank.items(), key=lambda kv: kv[1], reverse=True)
            ],
            by_company=[
                {"company_name": k, "total_try": round(v, 2)}
                for k, v in sorted(by_company.items(), key=lambda kv: kv[1], reverse=True)
            ],
            account_count=len(accounts),
            last_synced_at=last_synced,
        )

    # ── Balance history (trend) ────────────────────────────────────────

    def history(
        self, *, user_id: str, account_id: int, days: int = 30,
    ) -> list[dict[str, Any]]:
        # Ownership check
        owner = self.get_account(user_id=user_id, account_id=account_id)
        if not owner:
            raise ValueError(f"Hesap bulunamadı: {account_id}")
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT snapshot_date, balance, snapshot_source
                    FROM treasury_balance_history
                    WHERE account_id = ?
                    ORDER BY snapshot_date DESC
                    LIMIT ?
                    """,
                    (account_id, max(1, min(days, 365))),
                ).fetchall()
            finally:
                conn.close()
        return [dict(r) for r in rows]

    # ── CSV import ─────────────────────────────────────────────────────

    def import_csv(
        self,
        *,
        user_id: str,
        account_id: int,
        csv_content: str,
    ) -> dict[str, int]:
        """Banka extresi CSV → balance snapshot'lar.

        Beklenen format: 'date,balance' veya 'date;balance' (TR Excel).
        Header row otomatik tespit.
        """
        owner = self.get_account(user_id=user_id, account_id=account_id)
        if not owner:
            raise ValueError(f"Hesap bulunamadı: {account_id}")

        # Sniff delimiter
        sample = csv_content[:1024]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            class _D:
                delimiter = ","
            dialect = _D()

        reader = csv.reader(io.StringIO(csv_content), dialect)
        rows_in: list[tuple[str, float]] = []
        for i, row in enumerate(reader):
            if not row or len(row) < 2:
                continue
            date_raw = row[0].strip()
            balance_raw = row[1].strip()
            # Skip header
            if i == 0 and not re.match(r"\d", date_raw):
                continue
            date_clean = self._normalize_date(date_raw)
            if not date_clean:
                continue
            balance_clean = self._parse_amount(balance_raw)
            if balance_clean is None:
                continue
            rows_in.append((date_clean, balance_clean))

        if not rows_in:
            raise ValueError("CSV'den geçerli satır okunamadı")

        now = int(time.time())
        inserted = 0
        updated = 0
        with self._lock:
            conn = self._connect()
            try:
                for date, balance in rows_in:
                    res = self._upsert_snapshot(
                        conn, account_id=account_id,
                        snapshot_date=date, balance=balance,
                        source="csv_import",
                    )
                    if res == "insert":
                        inserted += 1
                    elif res == "update":
                        updated += 1
                # Update current_balance to latest snapshot
                rows_in.sort(reverse=True)
                latest_balance = rows_in[0][1]
                conn.execute(
                    """
                    UPDATE treasury_accounts
                    SET current_balance = ?, last_synced_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (latest_balance, now, now, account_id),
                )
                conn.commit()
            finally:
                conn.close()
        return {"inserted": inserted, "updated": updated, "total_rows": len(rows_in)}

    # ── Internal ───────────────────────────────────────────────────────

    @staticmethod
    def _upsert_snapshot(
        conn: sqlite3.Connection,
        *,
        account_id: int,
        snapshot_date: str,
        balance: float,
        source: str,
    ) -> str:
        now = int(time.time())
        # SQLite supports UPSERT
        existing = conn.execute(
            """
            SELECT id FROM treasury_balance_history
            WHERE account_id = ? AND snapshot_date = ?
            """,
            (account_id, snapshot_date),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE treasury_balance_history
                SET balance = ?, snapshot_source = ?
                WHERE id = ?
                """,
                (balance, source, int(existing["id"])),
            )
            return "update"
        conn.execute(
            """
            INSERT INTO treasury_balance_history
                (account_id, snapshot_date, balance, snapshot_source, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (account_id, snapshot_date, balance, source, now),
        )
        return "insert"

    @staticmethod
    def _clean_iban(raw: str) -> str:
        s = re.sub(r"\s+", "", raw).upper()
        return s

    @staticmethod
    def _normalize_date(raw: str) -> str | None:
        raw = raw.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            return raw
        for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_amount(raw: str) -> float | None:
        raw = raw.replace("₺", "").replace("TL", "").replace(" ", "").strip()
        # TR format: 1.234,56 → 1234.56
        if "," in raw and "." in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif "," in raw:
            raw = raw.replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            return None

    @staticmethod
    def _row_to_view(row: sqlite3.Row) -> TreasuryAccountView:
        return TreasuryAccountView(
            id=int(row["id"]),
            user_id=str(row["user_id"]),
            company_name=str(row["company_name"]),
            bank_name=str(row["bank_name"]),
            branch=row["branch"],
            iban=row["iban"],
            account_no=row["account_no"],
            account_type=str(row["account_type"]),
            currency=str(row["currency"]),
            current_balance=float(row["current_balance"]),
            last_synced_at=(
                int(row["last_synced_at"])
                if row["last_synced_at"] is not None else None
            ),
            is_active=bool(int(row["is_active"])),
            notes=row["notes"],
            created_at=int(row["created_at"]),
            updated_at=int(row["updated_at"]),
        )
