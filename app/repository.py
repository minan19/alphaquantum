from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from threading import Lock
import random
import sqlite3

from app._sqlite_helpers import new_row_id

from app.models import Company, InventoryItem


class CompanyRepository:
    def __init__(self, database_path: str, seed_companies: list[Company]) -> None:
        self._database_path = database_path
        self._lock = Lock()
        self._conn = self._connect(database_path)
        self._ensure_schema()
        self._seed_if_empty(seed_companies)

    def list_companies(self) -> list[Company]:
        with self._lock:
            return self._list_companies_internal()

    def update_random(
        self,
        balance_delta_range: tuple[int, int] = (-10_000, 10_000),
        stock_delta_range: tuple[int, int] = (-5, 5),
    ) -> list[Company]:
        with self._lock:
            company_rows = self._conn.execute(
                "SELECT id, balance FROM companies"
            ).fetchall()
            for row in company_rows:
                new_balance = float(row["balance"]) + random.randint(*balance_delta_range)
                self._conn.execute(
                    "UPDATE companies SET balance = ? WHERE id = ?",
                    (new_balance, row["id"]),
                )

            inventory_rows = self._conn.execute(
                "SELECT id, quantity FROM inventory"
            ).fetchall()
            for row in inventory_rows:
                new_quantity = max(
                    0,
                    int(row["quantity"]) + random.randint(*stock_delta_range),
                )
                self._conn.execute(
                    "UPDATE inventory SET quantity = ? WHERE id = ?",
                    (new_quantity, row["id"]),
                )

            self._conn.commit()
            return self._list_companies_internal()

    def company_count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS count FROM companies").fetchone()
            return int(row["count"])

    def has_company(self, company_name: str) -> bool:
        normalized = company_name.strip()
        if not normalized:
            return False

        with self._lock:
            row = self._conn.execute(
                "SELECT 1 AS found FROM companies WHERE name = ? LIMIT 1",
                (normalized,),
            ).fetchone()
            return row is not None

    def ensure_company(
        self,
        company_name: str,
        *,
        initial_balance: float = 0.0,
        inventory_items: list[InventoryItem] | None = None,
    ) -> Company:
        normalized = company_name.strip()
        if not normalized:
            raise ValueError("company_name is required")

        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM companies WHERE name = ?",
                (normalized,),
            ).fetchone()

            if row is None:
                cursor = self._conn.execute(
                    "INSERT INTO companies(name, balance) VALUES(?, ?)",
                    (normalized, float(initial_balance)),
                )
                company_id = new_row_id(cursor)
            else:
                company_id = int(row["id"])

            for item in inventory_items or []:
                self._conn.execute(
                    """
                    INSERT INTO inventory(company_id, name, quantity, min_level)
                    VALUES(?, ?, ?, ?)
                    ON CONFLICT(company_id, name)
                    DO UPDATE SET quantity = excluded.quantity, min_level = excluded.min_level
                    """,
                    (company_id, item.name, item.quantity, item.min_level),
                )

            self._conn.commit()
            company = self._get_company_by_name_internal(normalized)
            if company is None:
                raise RuntimeError("Company upsert failed")
            return company

    def close(self) -> None:
        with suppress(Exception):
            self._conn.close()

    def __del__(self) -> None:
        self.close()

    @staticmethod
    def _connect(database_path: str) -> sqlite3.Connection:
        path = Path(database_path)
        if path.parent and str(path.parent) != ".":
            path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                balance REAL NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                min_level INTEGER NOT NULL,
                UNIQUE(company_id, name),
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
            )
            """
        )
        self._conn.commit()

    def _seed_if_empty(self, seed_companies: list[Company]) -> None:
        row = self._conn.execute("SELECT COUNT(*) AS count FROM companies").fetchone()
        if int(row["count"]) > 0:
            return

        for company in seed_companies:
            company_cursor = self._conn.execute(
                "INSERT INTO companies(name, balance) VALUES(?, ?)",
                (company.name, company.balance),
            )
            company_id = new_row_id(company_cursor)

            for item in company.inventory:
                self._conn.execute(
                    """
                    INSERT INTO inventory(company_id, name, quantity, min_level)
                    VALUES(?, ?, ?, ?)
                    """,
                    (company_id, item.name, item.quantity, item.min_level),
                )

        self._conn.commit()

    def _list_companies_internal(self) -> list[Company]:
        rows = self._conn.execute(
            """
            SELECT
                c.id AS company_id,
                c.name AS company_name,
                c.balance AS company_balance,
                i.name AS item_name,
                i.quantity AS item_quantity,
                i.min_level AS item_min_level
            FROM companies c
            LEFT JOIN inventory i ON i.company_id = c.id
            ORDER BY c.id ASC, i.id ASC
            """
        ).fetchall()

        companies_by_id: dict[int, Company] = {}
        for row in rows:
            company_id = int(row["company_id"])
            company = companies_by_id.get(company_id)
            if company is None:
                company = Company(
                    name=str(row["company_name"]),
                    balance=float(row["company_balance"]),
                    inventory=[],
                )
                companies_by_id[company_id] = company

            if row["item_name"] is not None:
                company.inventory.append(
                    InventoryItem(
                        name=str(row["item_name"]),
                        quantity=int(row["item_quantity"]),
                        min_level=int(row["item_min_level"]),
                    )
                )

        return list(companies_by_id.values())

    def _get_company_by_name_internal(self, company_name: str) -> Company | None:
        rows = self._conn.execute(
            """
            SELECT
                c.id AS company_id,
                c.name AS company_name,
                c.balance AS company_balance,
                i.name AS item_name,
                i.quantity AS item_quantity,
                i.min_level AS item_min_level
            FROM companies c
            LEFT JOIN inventory i ON i.company_id = c.id
            WHERE c.name = ?
            ORDER BY c.id ASC, i.id ASC
            """,
            (company_name,),
        ).fetchall()
        if not rows:
            return None

        company = Company(
            name=str(rows[0]["company_name"]),
            balance=float(rows[0]["company_balance"]),
            inventory=[],
        )
        for row in rows:
            if row["item_name"] is None:
                continue
            company.inventory.append(
                InventoryItem(
                    name=str(row["item_name"]),
                    quantity=int(row["item_quantity"]),
                    min_level=int(row["item_min_level"]),
                )
            )
        return company


def default_companies() -> list[Company]:
    return [
        Company(
            name="ABC Holding",
            balance=50000,
            inventory=[
                InventoryItem(name="Kablo", quantity=5, min_level=10),
                InventoryItem(name="Trafo", quantity=20, min_level=5),
            ],
        )
    ]
