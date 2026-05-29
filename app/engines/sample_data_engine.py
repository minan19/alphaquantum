"""OBS1: SampleDataEngine — yeni kullanıcı için canlı örnek veri.

## Felsefe — empty state'in karanlığını kır

Yeni kullanıcı dashboard'a girdiğinde:
  * Bakiye 0
  * Anomali 0
  * Forecast yetersiz veri
  * Fatura listesi boş

Bu deneyim "platform ne işe yarıyor" sorusunu yaratır → drop-off.
Çözüm: tek tıkla **gerçekçi sample data** seed et. Kullanıcı sistemin
nasıl göründüğünü canlı yaşar; gerçek verisini girince sample'ı temizler.

## Üretilen veri

  * 3 örnek şirket (CorpOS holding senaryosu için)
  * 8 cari (4 müşteri + 4 tedarikçi)
  * 12 fatura (son 90 gün, mixed direction)
  * 90 günlük ledger entries (haftalık seasonality + trend)
  * 2 örnek anomali sinyali (kritik + yüksek)
  * Cashflow forecast model state'i

## Isolation

Tüm sample kayıtlar `_sample=true` tag'i ile işaretlenir.
clear_sample_data() bu kayıtları siler — gerçek user data'sına dokunmaz.

## Determinism

Aynı user_id'ye 2× seed çağrısı → 2. çağrı duplicate yaratmaz
(idempotency via tag check).
"""
from __future__ import annotations

import json
import math
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


# Sample data tag — gerçek user data'sından ayırt etmek için
SAMPLE_TAG = "_sample_seed"


@dataclass(frozen=True)
class SeedSummary:
    customers_created: int
    invoices_created: int
    ledger_entries_created: int
    anomaly_signals_created: int
    already_seeded: bool


class SampleDataEngine:
    """Empty state'i kıran demo veri seeder."""

    DEFAULT_COMPANY = "Demo Holding A.Ş."

    def __init__(self, *, database_path: str) -> None:
        self._database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._database_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ── Public API ─────────────────────────────────────────────────────

    def has_sample_data(self, *, user_id: str) -> bool:
        """User için seed yapılmış mı?"""
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n FROM customers
                WHERE tags LIKE ?
                """,
                (f"%{SAMPLE_TAG}%",),
            ).fetchone()
            return bool(row and int(row["n"]) > 0)
        finally:
            conn.close()

    def seed(
        self, *, user_id: str, company_name: str | None = None,
    ) -> SeedSummary:
        """Yeni kullanıcı için sample data oluştur.

        Idempotent: zaten varsa yeni kayıt eklenmez.
        """
        if self.has_sample_data(user_id=user_id):
            return SeedSummary(
                customers_created=0, invoices_created=0,
                ledger_entries_created=0, anomaly_signals_created=0,
                already_seeded=True,
            )

        company = company_name or self.DEFAULT_COMPANY
        now = int(time.time())
        conn = self._connect()

        try:
            customers_n = self._seed_customers(conn, company, now)
            invoices_n, customer_ids = self._seed_invoices(conn, company, now)
            ledger_n = self._seed_ledger(conn, company, now)
            anomaly_n = self._seed_anomalies(conn, now)
            conn.commit()
            return SeedSummary(
                customers_created=customers_n,
                invoices_created=invoices_n,
                ledger_entries_created=ledger_n,
                anomaly_signals_created=anomaly_n,
                already_seeded=False,
            )
        finally:
            conn.close()

    def clear(self, *, user_id: str) -> dict[str, int]:
        """Sample data'yı sil. Gerçek user data'sına dokunmaz."""
        now = int(time.time())
        _ = now  # reserved for future audit log
        conn = self._connect()
        try:
            # Customers tagged with sample
            cust = conn.execute(
                "DELETE FROM customers WHERE tags LIKE ?",
                (f"%{SAMPLE_TAG}%",),
            )
            inv = conn.execute(
                """
                DELETE FROM invoices
                WHERE description LIKE ?
                """,
                (f"%[{SAMPLE_TAG}]%",),
            )
            ledger = conn.execute(
                """
                DELETE FROM finance_ledger_entries
                WHERE category = 'sample_seed'
                """
            )
            anomalies = conn.execute(
                """
                DELETE FROM anomaly_signals
                WHERE signature_hash LIKE ?
                """,
                (f"sample_%",),
            )
            conn.commit()
            return {
                "customers_deleted": int(cust.rowcount or 0),
                "invoices_deleted": int(inv.rowcount or 0),
                "ledger_entries_deleted": int(ledger.rowcount or 0),
                "anomalies_deleted": int(anomalies.rowcount or 0),
            }
        finally:
            conn.close()

    # ── Internal: customers ────────────────────────────────────────────

    def _seed_customers(
        self, conn: sqlite3.Connection, company: str, now: int,
    ) -> int:
        customers = [
            ("CR-S-001", "Yıldız Tekstil A.Ş.", "1111111111", "info@yildiztekstil.com.tr", "musteri"),
            ("CR-S-002", "Mavi Lojistik Ltd.", "2222222222", "muhasebe@mavilojistik.com", "musteri"),
            ("CR-S-003", "Atlas Pazarlama", "3333333333", "info@atlas.com", "musteri"),
            ("CR-S-004", "Bereket İnşaat A.Ş.", "4444444444", "info@bereketinsaat.com", "musteri"),
            ("CR-S-005", "Aksoy Tedarik Ltd.", "5555555555", "satis@aksoyt.com", "tedarikci"),
            ("CR-S-006", "Star Ofis Malzemeleri", "6666666666", "info@starofis.com", "tedarikci"),
            ("CR-S-007", "Mega Bilişim A.Ş.", "7777777777", "satis@megabilisim.com", "tedarikci"),
            ("CR-S-008", "Güneş Enerji Hizmetleri", "8888888888", "info@gunesenerji.com", "tedarikci"),
        ]
        tags = json.dumps(["logo_import", SAMPLE_TAG], ensure_ascii=False)
        n = 0
        for code, name, vkn, email, sector in customers:
            try:
                conn.execute(
                    """
                    INSERT INTO customers
                        (company_name, full_name, email, phone, sector,
                         tags, notes, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, '', ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        company, name, email, sector, tags,
                        f"VKN:{vkn} | LogoKod:{code} | {SAMPLE_TAG}",
                        now, now,
                    ),
                )
                n += 1
            except sqlite3.IntegrityError:
                continue
        return n

    # ── Internal: invoices ─────────────────────────────────────────────

    def _seed_invoices(
        self, conn: sqlite3.Connection, company: str, now: int,
    ) -> tuple[int, dict[str, int]]:
        # Get sample customer IDs by note prefix
        sample_rows = conn.execute(
            """
            SELECT id, notes FROM customers
            WHERE company_name = ? AND tags LIKE ?
            """,
            (company, f"%{SAMPLE_TAG}%"),
        ).fetchall()
        customer_id_by_code: dict[str, int] = {}
        for row in sample_rows:
            notes = str(row["notes"] or "")
            # Extract LogoKod:XXX from notes
            for token in notes.split(" | "):
                if token.startswith("LogoKod:"):
                    code = token.split(":", 1)[1]
                    customer_id_by_code[code] = int(row["id"])
                    break

        today = datetime.now()
        # 12 fatura: son 90 gün, mixed customers
        invoice_specs = [
            ("CR-S-001", 12500, 22, "outgoing"),  # 22 gün önce
            ("CR-S-002", 8500, 18, "outgoing"),
            ("CR-S-003", 15000, 15, "outgoing"),
            ("CR-S-001", 9300, 10, "outgoing"),
            ("CR-S-004", 22000, 7, "outgoing"),
            ("CR-S-002", 6700, 3, "outgoing"),
            ("CR-S-005", 4500, 45, "incoming"),
            ("CR-S-006", 1800, 35, "incoming"),
            ("CR-S-007", 12000, 30, "incoming"),
            ("CR-S-005", 5200, 25, "incoming"),
            ("CR-S-008", 8900, 12, "incoming"),
            ("CR-S-007", 3400, 5, "incoming"),
        ]
        n = 0
        for code, amount, days_ago, direction in invoice_specs:
            customer_id = customer_id_by_code.get(code)
            issue_date = (today - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            due_date = (today - timedelta(days=days_ago - 30)).strftime("%Y-%m-%d")
            inv_no = f"S-FAT-{code[-3:]}-{days_ago:02d}"
            try:
                conn.execute(
                    """
                    INSERT INTO invoices
                        (company_name, customer_id, proposal_id, invoice_number,
                         title, amount, paid_amount, currency, status,
                         issue_date, due_date, paid_date, description,
                         created_at, updated_at)
                    VALUES (?, ?, NULL, ?, ?, ?, 0, 'TRY', 'pending',
                            ?, ?, NULL, ?, ?, ?)
                    """,
                    (
                        company, customer_id, inv_no,
                        f"Demo Fatura {inv_no}",
                        float(amount),
                        issue_date, due_date,
                        f"[{SAMPLE_TAG}] [{direction}] Demo seed",
                        now, now,
                    ),
                )
                n += 1
            except sqlite3.IntegrityError:
                continue
        return n, customer_id_by_code

    # ── Internal: ledger ───────────────────────────────────────────────

    def _seed_ledger(
        self, conn: sqlite3.Connection, company: str, now: int,
    ) -> int:
        """90 günlük ledger entries — weekly seasonality + slight upward trend.

        A3 forecast'ın anlamlı sonuç vermesi için minimum veri.
        """
        today = datetime.now()
        n = 0
        for d in range(90):
            day = today - timedelta(days=d)
            seasonal = 800 * math.sin(2 * math.pi * d / 7)
            trend = (90 - d) * 5  # daha güncel = daha yüksek
            base_income = 5000 + trend + max(0, seasonal)
            base_expense = 3500 + trend / 2 + max(0, -seasonal)

            for entry_type, amount in (
                ("income", base_income),
                ("expense", base_expense),
            ):
                try:
                    conn.execute(
                        """
                        INSERT INTO finance_ledger_entries
                            (company_name, entry_type, amount, category,
                             description, entry_date, created_at,
                             intercompany_flag)
                        VALUES (?, ?, ?, 'sample_seed', ?, ?, ?, 0)
                        """,
                        (
                            company, entry_type, float(amount),
                            f"Demo seed gün {d}",
                            day.strftime("%Y-%m-%d"), now,
                        ),
                    )
                    n += 1
                except sqlite3.IntegrityError:
                    continue
        return n

    # ── Internal: anomalies ────────────────────────────────────────────

    def _seed_anomalies(
        self, conn: sqlite3.Connection, now: int,
    ) -> int:
        """2 örnek anomali — A2 dedektörünü canlı göster."""
        samples = [
            {
                "signal_type": "intercompany_leakage",
                "severity": "critical",
                "confidence_pct": 99.5,
                "modified_z": 4.2,
                "title": "Demo: Mega Bilişim 2 şirketten ödendi",
                "description": (
                    "Mega Bilişim, son 7 günde Demo Holding'in 2 yan "
                    "şirketinden ödendi (toplam ₺18.500). Geçen 12 ayda "
                    "bu tedarikçi sadece 1 şirketle çalışıyordu. "
                    "Olası çift faturalama → incele."
                ),
                "baseline": {"historical_company_count": 1, "window_days": 7},
                "payload": {
                    "counterparty": "Mega Bilişim A.Ş.",
                    "current_companies": ["Demo CO A.Ş.", "Demo Logistics"],
                    "total_amount": 18500,
                },
                "signature_hash": "sample_intercompany_leakage_001",
            },
            {
                "signal_type": "duplicate_payment",
                "severity": "critical",
                "confidence_pct": 99.9,
                "modified_z": 6.0,
                "title": "Demo: Mükerrer ödeme — Aksoy Tedarik ₺5.200",
                "description": (
                    "Aksoy Tedarik Ltd. adresine 5.200 TL tutarında 2 "
                    "fatura aynı hafta kesildi. Çift kayıt olabilir — "
                    "muhasebe ekibine doğrulattırın."
                ),
                "baseline": {"detection_window_days": 7},
                "payload": {
                    "counterparty": "Aksoy Tedarik Ltd.",
                    "amount": 5200,
                    "occurrence_count": 2,
                },
                "signature_hash": "sample_duplicate_payment_001",
            },
        ]
        n = 0
        for s in samples:
            try:
                conn.execute(
                    """
                    INSERT INTO anomaly_signals
                        (holding_id, signal_type, severity, confidence_pct,
                         modified_z, title, description,
                         baseline_json, payload_json,
                         signature_hash, detected_at, status)
                    VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
                    """,
                    (
                        s["signal_type"], s["severity"], s["confidence_pct"],
                        s["modified_z"], s["title"], s["description"],
                        json.dumps(s["baseline"], ensure_ascii=False),
                        json.dumps(s["payload"], ensure_ascii=False),
                        s["signature_hash"], now,
                    ),
                )
                n += 1
            except sqlite3.IntegrityError:
                continue
        return n
