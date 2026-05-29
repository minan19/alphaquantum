"""G1.2: ConsolidationEngine — Holding seviyesi konsolide P&L.

Karma sektörlü Türk holding'in en kritik raporlama yeteneği. Her şirketin
gelir/gider'i iki bileşene ayrılır:
  - external: üçüncü taraf (gerçek müşteri/tedarikçi)
  - intercompany: grup içi alışveriş (örn. lojistik şirketi gıda şirketine
    nakliye hizmeti faturalandırıyor)

Konsolide P&L = sum(external). Intercompany kalemler ELİMİNE EDİLİR çünkü:
  - Lojistik AŞ'nin gıda AŞ'ye sattığı hizmet → grup için "iç ciro"
  - Gıda AŞ'nin lojistik AŞ'ye ödediği fatura → grup için "iç gider"
  - Net: sıfır. Konsolide gelirde gösterilirse YANLIŞ büyük rakam çıkar.

Critical: G1.1 migration 023'te intercompany_flag eklendi. Bu engine ondan
sonra anlamlı çalışır. G1.3'te IntercompanyTransferEngine atomic write ile
flag'i set eder.

Mimari notlar:
  - Tek aggregate SQL sorgu (finance_repository.aggregate_pl_for_companies) —
    Python loop yapılmaz, büyük ledger'da O(N) yerine O(1) round-trip.
  - Eliminasyon "balance check" yapar: intercompany_income ≈ intercompany_expense
    olmalı. Aksi halde veri tutarsızlığı raporlanır (legacy/manuel entry).
  - Health status consolidated_net'e göre 4 kademe (strong/stable/watch/risk).
"""
from __future__ import annotations

from typing import Any

from app.decimal_utils import sum_money, to_decimal, to_float_for_storage
from app.finance_repository import FinanceRepository
from app.holding_repository import HoldingRepository
from app.models import (
    ConsolidatedPLElimination,
    ConsolidatedPLLine,
    ConsolidatedPLResponse,
)


# Eliminasyon balans toleransı (kuruş seviyesi)
_BALANCE_EPSILON = 0.01

# Health status eşikleri (consolidated_net'in absolute büyüklüğüne göre)
_HEALTH_THRESHOLDS = {
    "strong": 1_000_000.0,   # ≥ 1M TL net pozitif
    "stable": 100_000.0,     # ≥ 100K TL net pozitif
    "watch": 0.0,            # 0 ≤ net < 100K
}


class ConsolidationEngine:
    """Holding için konsolide P&L hesaplar (intercompany eliminasyonlu)."""

    def __init__(
        self,
        *,
        finance_repo: FinanceRepository,
        holding_repo: HoldingRepository,
    ) -> None:
        self._finance_repo = finance_repo
        self._holding_repo = holding_repo

    def consolidated_pl(
        self,
        *,
        holding_id: int,
        start_date: str,
        end_date: str,
    ) -> ConsolidatedPLResponse:
        """Compute the consolidated P&L for a holding within the given period.

        Args:
            holding_id: Target holding (HoldingRepository.get_holding)
            start_date: ISO YYYY-MM-DD inclusive
            end_date: ISO YYYY-MM-DD inclusive (must be ≥ start_date)

        Raises:
            ValueError: holding not found, or date range invalid.
        """
        if start_date > end_date:
            raise ValueError("start_date must be <= end_date")

        holding_row = self._holding_repo.get_holding(holding_id)
        if holding_row is None:
            raise ValueError(f"Holding {holding_id} not found")

        # Tüm bağlı şirketler (registered_in_platform fark etmez —
        # ledger'da entry'si olan herhangi bir şirket dahil)
        company_rows = self._holding_repo.list_holding_companies(
            holding_id=holding_id, limit=1000
        )
        company_names = [str(row["company_name"]) for row in company_rows]

        # Tek aggregate SQL sorgu
        agg_rows = self._finance_repo.aggregate_pl_for_companies(
            company_names=company_names,
            start_date=start_date,
            end_date=end_date,
        )

        # Per-company breakdown
        lines = _build_lines(company_names, agg_rows)
        lines.sort(key=lambda line: line.gross_income, reverse=True)

        # G+3: Holding seviyesi toplamlar Decimal-aware — kuruş kaybı sıfır.
        # Eski kod `sum(...) + round(..., 2)` float toplama yapıyordu; karma
        # holding'in 4-10 şirketinden gelen milyonluk değerler toplandığında
        # binary IEEE 754 artifact'ı kuruş hatasına dönüşebilirdi.
        gross_total_income_d = sum_money(line.gross_income for line in lines)
        gross_total_expense_d = sum_money(line.gross_expense for line in lines)
        gross_net_d = gross_total_income_d - gross_total_expense_d

        consolidated_income_d = sum_money(line.external_income for line in lines)
        consolidated_expense_d = sum_money(line.external_expense for line in lines)
        consolidated_net_d = consolidated_income_d - consolidated_expense_d

        # Eliminasyon detayı + balans kontrolü (Decimal)
        total_intercompany_income_d = sum_money(line.intercompany_income for line in lines)
        total_intercompany_expense_d = sum_money(line.intercompany_expense for line in lines)
        elimination_amount_d = total_intercompany_income_d + total_intercompany_expense_d
        elimination_imbalance_d = abs(
            total_intercompany_income_d - total_intercompany_expense_d
        )
        is_balanced = elimination_imbalance_d <= to_decimal(_BALANCE_EPSILON)

        elimination = ConsolidatedPLElimination(
            total_intercompany_income=to_float_for_storage(total_intercompany_income_d),
            total_intercompany_expense=to_float_for_storage(total_intercompany_expense_d),
            elimination_amount=to_float_for_storage(elimination_amount_d),
            is_balanced=is_balanced,
        )

        consolidated_net_float = to_float_for_storage(consolidated_net_d)

        return ConsolidatedPLResponse(
            holding_id=holding_id,
            holding_name=str(holding_row["name"]),
            period_start=start_date,
            period_end=end_date,
            lines=lines,
            gross_total_income=to_float_for_storage(gross_total_income_d),
            gross_total_expense=to_float_for_storage(gross_total_expense_d),
            gross_net=to_float_for_storage(gross_net_d),
            consolidated_income=to_float_for_storage(consolidated_income_d),
            consolidated_expense=to_float_for_storage(consolidated_expense_d),
            consolidated_net=consolidated_net_float,
            elimination=elimination,
            health_status=_classify_health(consolidated_net_float),
        )


def _build_lines(
    company_names: list[str],
    agg_rows: list[dict[str, Any]],
) -> list[ConsolidatedPLLine]:
    """Aggregate SQL rows → ConsolidatedPLLine per company.

    Aggregate query döner: (company_name, entry_type, external_total,
    intercompany_total). Tek şirket için potansiyel 2 row (income + expense).
    Hiç entry olmayan şirket için sıfır-dolu line üretir.
    """
    by_company: dict[str, dict[str, float]] = {}
    for company in company_names:
        by_company[company] = {
            "external_income": 0.0,
            "intercompany_income": 0.0,
            "external_expense": 0.0,
            "intercompany_expense": 0.0,
        }

    for row in agg_rows:
        company = str(row["company_name"])
        entry_type = str(row["entry_type"])
        external = float(row["external_total"])
        intercompany = float(row["intercompany_total"])

        if company not in by_company:
            # Edge: ledger'da olup holding_companies'te olmayan şirket — atla
            continue
        if entry_type == "income":
            by_company[company]["external_income"] = external
            by_company[company]["intercompany_income"] = intercompany
        elif entry_type == "expense":
            by_company[company]["external_expense"] = external
            by_company[company]["intercompany_expense"] = intercompany
        # entry_type CHECK'i schema'da var, başka değer gelmez

    lines: list[ConsolidatedPLLine] = []
    for company, sums in by_company.items():
        gross_income = sums["external_income"] + sums["intercompany_income"]
        gross_expense = sums["external_expense"] + sums["intercompany_expense"]
        net_total = gross_income - gross_expense
        net_external = sums["external_income"] - sums["external_expense"]

        lines.append(
            ConsolidatedPLLine(
                company=company,
                gross_income=round(gross_income, 2),
                intercompany_income=round(sums["intercompany_income"], 2),
                external_income=round(sums["external_income"], 2),
                gross_expense=round(gross_expense, 2),
                intercompany_expense=round(sums["intercompany_expense"], 2),
                external_expense=round(sums["external_expense"], 2),
                net_total=round(net_total, 2),
                net_external=round(net_external, 2),
            )
        )
    return lines


def _classify_health(consolidated_net: float) -> str:
    """4-kademeli mali sağlık göstergesi (consolidated_net'e göre)."""
    if consolidated_net < 0:
        return "risk"
    if consolidated_net >= _HEALTH_THRESHOLDS["strong"]:
        return "strong"
    if consolidated_net >= _HEALTH_THRESHOLDS["stable"]:
        return "stable"
    return "watch"
