"""G1.5: BalanceService — ledger'dan türetilmiş tek source of truth.

## Critical Finding #2 (Gap Analizi)

`Company.balance` field'ı şu an iki yerden geliyor:
  1. `companies` tablosunda saklı statik değer (legacy)
  2. `finance_ledger_entries`'ten hesaplanabilecek "gerçek" değer

Çift kaynak → veri tutarsızlığı riski. Konsolide raporlamada iki yöntem
farklı sonuç döndürür. Müşteri "rapor neden farklı?" diye sorduğunda
güven kaybı yaşanır.

## Bu service'in çözümü

`BalanceService` ledger'dan türetilmiş **kesin** balance hesaplar:

    balance = initial_balance (companies.balance, baseline)
            + Σ income (finance_ledger_entries)
            − Σ expense (finance_ledger_entries)

Bu hesaplama Engine'lere (FinanceEngine, ComparisonEngine) inject edilir,
böylece eski kod yolu bozulmadan tek source'a geçilir.

## Geriye dönük uyum

Mevcut `Company.balance` field'ı **legacy baseline** olarak kalır
(ilk şirket onboarding'inde "company.balance = 1.000.000" gibi initial
yatırım girilebilir). Ledger entry'leri buna eklenir/çıkarılır.

Bu yaklaşım sayesinde:
  - Hiçbir mevcut test bozulmaz
  - Mevcut API çıktıları aynı kalır (anlam aynı, kaynak temiz)
  - G1.6'da storytelling sahne 1 (sabah bakiyesi) ledger-derived olur
  - Elite Foundation Decimal migration'ında REAL → NUMERIC geçişi
    tek noktada yapılır

## Mimari

BalanceService stateless — repository'lere bağımlı:
  - CompanyRepository: initial baseline (company.balance)
  - FinanceRepository: ledger entries (income/expense aggregations)

Tek aggregate SQL — Python loop yok, büyük ledger'da performans korunur.
"""
from __future__ import annotations

from typing import Any

from app.decimal_utils import sum_money, to_decimal, to_float_for_storage
from app.finance_repository import FinanceRepository
from app.models import Company
from app.repository import CompanyRepository


class BalanceService:
    """Ledger-derived authoritative balance computation."""

    def __init__(
        self,
        *,
        company_repo: CompanyRepository,
        finance_repo: FinanceRepository,
    ) -> None:
        self._company_repo = company_repo
        self._finance_repo = finance_repo

    def compute_company_balance(self, company_name: str) -> float:
        """Single company: initial baseline + ledger net.

        G+3: Decimal arithmetic — kuruş kaybı sıfır. Eski kod
        `round(baseline + ledger_net, 2)` float toplama yapıyordu;
        binary IEEE 754 artifact riski vardı. Yeni: Decimal toplama
        + ROUND_HALF_UP banking standard.

        Returns 0.0 if company not found (consistent with comparison_engine
        defensive behavior).
        """
        baseline = self._get_baseline(company_name)
        ledger_net = self._aggregate_ledger_net(
            company_names=[company_name]
        ).get(company_name, 0.0)
        return to_float_for_storage(sum_money([baseline, ledger_net]))

    def compute_companies_with_ledger_balance(
        self, companies: list[Company]
    ) -> list[Company]:
        """Return new Company list where `balance` is ledger-derived.

        Mevcut Engine kodu `company.balance` field'ını okuyor —
        bu helper o field'ı ledger-derived değerle güncellenmiş
        kopyalarla değiştirir. Engine'leri minimum invaziv değiştirir.

        Aggregate SQL: tek query, holding-wide aggregation.
        """
        if not companies:
            return []

        names = [c.name for c in companies]
        ledger_net_by_company = self._aggregate_ledger_net(company_names=names)

        # Pydantic model_copy ile immutable update.
        # G+3: float toplama → Decimal sum + ROUND_HALF_UP.
        result: list[Company] = []
        for company in companies:
            ledger_net = ledger_net_by_company.get(company.name, 0.0)
            new_balance = to_float_for_storage(
                sum_money([company.balance, ledger_net])
            )
            updated = company.model_copy(update={"balance": new_balance})
            result.append(updated)
        return result

    # ── Internals ──────────────────────────────────────────────────────

    def _get_baseline(self, company_name: str) -> float:
        """Companies tablosundaki initial balance (baseline)."""
        if not self._company_repo.has_company(company_name):
            return 0.0
        # CompanyRepository public API'sini kullan
        companies = self._company_repo.list_companies()
        for company in companies:
            if company.name == company_name:
                return float(company.balance)
        return 0.0

    def _aggregate_ledger_net(
        self, *, company_names: list[str]
    ) -> dict[str, float]:
        """Per-company net = SUM(income) - SUM(expense) from ledger.

        Single SQL, parameterized IN clause.
        Returns {company_name: net_amount}. Empty list → empty dict.
        """
        if not company_names:
            return {}

        placeholders = ",".join("?" * len(company_names))
        query = f"""
            SELECT
                company_name,
                COALESCE(SUM(CASE WHEN entry_type = 'income' THEN amount ELSE 0 END), 0) AS income_total,
                COALESCE(SUM(CASE WHEN entry_type = 'expense' THEN amount ELSE 0 END), 0) AS expense_total
            FROM finance_ledger_entries
            WHERE company_name IN ({placeholders})
            GROUP BY company_name
        """
        params: list[Any] = list(company_names)
        with self._finance_repo._lock:
            rows = self._finance_repo._conn.execute(query, params).fetchall()

        # G+3: SQL SUM(...) sonuçları Decimal-aware — income - expense
        # kuruş-doğru. Float subtraction artifact'ından kaçınılır.
        result: dict[str, float] = {}
        for row in rows:
            company = str(row["company_name"])
            net = to_decimal(row["income_total"]) - to_decimal(row["expense_total"])
            result[company] = to_float_for_storage(net)
        return result
