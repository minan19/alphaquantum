"""G1.4: GroupFXEngine — Holding-wide multi-currency net pozisyon.

Karma sektörlü holding'in en kritik finansal risk göstergesi: hangi para
biriminde net long (alacak fazlası), hangisinde short (borç fazlası).

Gerçek dünya örneği — Atlas Holding:
  - Atlas Gıda A.Ş.: USD ithalat ödemesi (open invoices), USD short
  - Atlas İnşaat A.Ş.: EUR ihracat geliri (open receivables), EUR long
  - Atlas Lojistik A.Ş.: TRY operations (FX exposure yok)
  → Holding net: USD short -$200K, EUR long +€150K
  → TL %10 değer kaybederse: USD pozisyon kötüleşir, EUR pozisyon iyileşir
    → Sensitivity scenario analizi kritik karar girdisi

Veri kaynakları:
  1. invoices tablosu (S-323 schema): open_amount per currency per company
  2. intercompany_transfers (G1.1): completed cross-currency transfer'lar
  3. FX rates: CurrencyConverter (TCMB feed'e Elite Foundation'da bağlanacak)

Mimari notlar:
  - Tek aggregate SQL — Python loop yok (büyük invoice tablo için kritik)
  - Sensitivity 3 standart senaryo (5/10/20 pct devalüasyon) — risk komitesi
    için anlaşılır threshold
  - Risk level kural-tabanlı (balanced/moderate/concentrated/critical)
  - PostgreSQL-friendly: parametrized IN, standart SQL
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.currency_converter import CurrencyConverter
from app.holding_repository import HoldingRepository
from app.intercompany_transfer_repository import IntercompanyTransferRepository
from app.invoice_repository import InvoiceRepository
from app.models import (
    FXCurrencyExposure,
    FXSensitivityScenario,
    GroupFXPositionResponse,
)


# Standart sensitivity senaryoları (Türkiye için anlamlı eşikler)
_SENSITIVITY_SCENARIOS = [
    ("TL %5 değer kaybı", 0.05),
    ("TL %10 değer kaybı", 0.10),
    ("TL %20 değer kaybı (kriz senaryosu)", 0.20),
]


class GroupFXEngine:
    """Holding-wide multi-currency net position + sensitivity analysis."""

    def __init__(
        self,
        *,
        holding_repo: HoldingRepository,
        invoice_repo: InvoiceRepository,
        transfer_repo: IntercompanyTransferRepository,
        fx_converter: CurrencyConverter | None = None,
    ) -> None:
        self._holding_repo = holding_repo
        self._invoice_repo = invoice_repo
        self._transfer_repo = transfer_repo
        self._fx = fx_converter or CurrencyConverter()

    def group_fx_position(
        self,
        *,
        holding_id: int,
        as_of_date: str | None = None,
    ) -> GroupFXPositionResponse:
        """Compute holding-wide FX net position with sensitivity scenarios.

        Args:
            holding_id: target holding
            as_of_date: ISO YYYY-MM-DD; defaults to today
        """
        holding_row = self._holding_repo.get_holding(holding_id)
        if holding_row is None:
            raise ValueError(f"Holding {holding_id} not found")

        report_date = as_of_date or date.today().isoformat()

        # Holding'in tüm şirketleri
        company_rows = self._holding_repo.list_holding_companies(
            holding_id=holding_id, limit=1000
        )
        company_names = [str(row["company_name"]) for row in company_rows]

        # 1. Invoice AR pozisyon (open + overdue per currency)
        ar_by_currency = self._aggregate_ar_by_currency(
            company_names=company_names, as_of_date=report_date
        )

        # 2. Intercompany transfer pozisyon (completed cross-currency)
        ic_by_currency = self._aggregate_intercompany_by_currency(
            holding_id=holding_id
        )

        # 3. Per-currency net pozisyon birleştir
        exposures = self._build_exposures(ar_by_currency, ic_by_currency)
        exposures.sort(key=lambda e: abs(e.net_position_try), reverse=True)

        # 4. Holding-wide özet
        total_long = sum(e.net_position_try for e in exposures if e.net_position_try > 0)
        total_short = sum(
            abs(e.net_position_try) for e in exposures if e.net_position_try < 0
        )
        net_exposure = total_long - total_short

        # 5. Sensitivity analizi
        sensitivity = self._compute_sensitivity(exposures)

        # 6. Risk seviyesi + öneriler
        risk_level = _classify_risk(total_long=total_long, total_short=total_short)
        recommendations = _build_recommendations(
            exposures=exposures,
            risk_level=risk_level,
            net_exposure=net_exposure,
        )

        return GroupFXPositionResponse(
            holding_id=holding_id,
            holding_name=str(holding_row["name"]),
            as_of_date=report_date,
            exposures=exposures,
            total_long_try=round(total_long, 2),
            total_short_try=round(total_short, 2),
            net_exposure_try=round(net_exposure, 2),
            sensitivity_scenarios=sensitivity,
            risk_level=risk_level,
            recommendations=recommendations,
        )

    # ── Aggregators ────────────────────────────────────────────────────

    def _aggregate_ar_by_currency(
        self,
        *,
        company_names: list[str],
        as_of_date: str,
    ) -> dict[str, dict[str, float]]:
        """Per-currency AR (receivables) breakdown from invoices.

        Returns: {currency: {"open": float, "overdue": float}}
        """
        if not company_names:
            return {}

        placeholders = ",".join("?" * len(company_names))
        query = f"""
            SELECT
                currency,
                COALESCE(SUM(amount - paid_amount), 0) AS open_total,
                COALESCE(SUM(
                    CASE
                        WHEN due_date < ? AND status IN ('pending', 'partial', 'overdue')
                        THEN amount - paid_amount
                        ELSE 0
                    END
                ), 0) AS overdue_total
            FROM invoices
            WHERE company_name IN ({placeholders})
              AND status IN ('pending', 'partial', 'overdue')
            GROUP BY currency
        """
        params: list[Any] = [as_of_date, *company_names]

        result: dict[str, dict[str, float]] = {}
        with self._invoice_repo._lock:  # invoice_repo public API yok, internal lock
            rows = self._invoice_repo._conn.execute(query, params).fetchall()

        for row in rows:
            currency = str(row["currency"] or "TRY").upper()
            result[currency] = {
                "open": float(row["open_total"]),
                "overdue": float(row["overdue_total"]),
            }
        return result

    def _aggregate_intercompany_by_currency(
        self, *, holding_id: int
    ) -> dict[str, dict[str, float]]:
        """Per-currency intercompany flow breakdown.

        Returns: {currency: {"inflow": float, "outflow": float}}
        Inflow = to_company perspective (incoming FX)
        Outflow = from_company perspective (outgoing FX)
        """
        # Sadece completed status — pending/rejected/approved pozisyon değil
        with self._transfer_repo._lock:
            rows = self._transfer_repo._conn.execute(
                """
                SELECT currency, from_company, to_company, amount, target_amount
                FROM intercompany_transfers
                WHERE holding_id = ? AND approval_status = 'completed'
                """,
                (holding_id,),
            ).fetchall()

        result: dict[str, dict[str, float]] = {}
        for row in rows:
            currency = str(row["currency"] or "TRY").upper()
            amount = float(row["amount"])
            bucket = result.setdefault(
                currency, {"inflow": 0.0, "outflow": 0.0}
            )
            # Holding seviyesinden bakınca: from = outflow, to = inflow
            # (her ikisi de aynı holding içinde olduğu için net=0 ama
            # currency'lere ayrıştırma faydalı — özellikle cross-currency)
            bucket["outflow"] += amount
            bucket["inflow"] += amount
        return result

    # ── Builders ───────────────────────────────────────────────────────

    def _build_exposures(
        self,
        ar_by_currency: dict[str, dict[str, float]],
        ic_by_currency: dict[str, dict[str, float]],
    ) -> list[FXCurrencyExposure]:
        """Combine AR + intercompany breakdown into per-currency exposures."""
        all_currencies = set(ar_by_currency.keys()) | set(ic_by_currency.keys())

        exposures: list[FXCurrencyExposure] = []
        for currency in all_currencies:
            ar = ar_by_currency.get(currency, {"open": 0.0, "overdue": 0.0})
            ic = ic_by_currency.get(currency, {"inflow": 0.0, "outflow": 0.0})

            # Net position FX cinsinden: receivable_open + inflow - outflow
            # (TRY için: TRY exposure metriği AR fokuslu)
            net_fx = ar["open"] + ic["inflow"] - ic["outflow"]
            rate = self._fx.rate(currency)
            net_try = net_fx * rate

            if abs(net_fx) < 0.01:
                position_type = "flat"
            elif net_fx > 0:
                position_type = "long"
            else:
                position_type = "short"

            exposures.append(
                FXCurrencyExposure(
                    currency=currency,
                    fx_rate_to_try=rate,
                    receivable_open=round(ar["open"], 2),
                    receivable_overdue=round(ar["overdue"], 2),
                    intercompany_inflow=round(ic["inflow"], 2),
                    intercompany_outflow=round(ic["outflow"], 2),
                    net_position_fx=round(net_fx, 2),
                    net_position_try=round(net_try, 2),
                    position_type=position_type,
                )
            )
        return exposures

    def _compute_sensitivity(
        self, exposures: list[FXCurrencyExposure]
    ) -> list[FXSensitivityScenario]:
        """3 standart TL devalüasyon senaryosu için holding-wide impact."""
        scenarios: list[FXSensitivityScenario] = []
        for name, pct in _SENSITIVITY_SCENARIOS:
            # TL devalüe olursa: FX cinsinden long pozisyon TRY karşılığında
            # artar (kazanç), short pozisyon TRY karşılığında büyür (kayıp).
            # Sadece non-TRY pozisyonlar etkilenir.
            impact = 0.0
            for exp in exposures:
                if exp.currency == "TRY":
                    continue
                # net_position_try * devaluation_pct = senaryo etkisi
                # Long (+) → pozitif (gain), Short (-) → negatif (loss)
                impact += exp.net_position_try * pct
            scenarios.append(
                FXSensitivityScenario(
                    scenario_name=name,
                    devaluation_pct=pct,
                    total_impact_try=round(impact, 2),
                )
            )
        return scenarios


def _classify_risk(*, total_long: float, total_short: float) -> str:
    """Risk level: long ve short'un dengesine göre 4 kademe."""
    gross = total_long + total_short
    if gross < 1.0:
        return "balanced"  # Hiç FX exposure yok
    net_abs = abs(total_long - total_short)
    concentration = net_abs / gross  # 0..1

    if concentration < 0.20:
        return "balanced"      # Long ≈ short, doğal hedge
    if concentration < 0.50:
        return "moderate"      # Bir taraf baskın
    if concentration < 0.80:
        return "concentrated"  # Tek yön ağır
    return "critical"          # Tamamen tek tarafa konsantre


def _build_recommendations(
    *,
    exposures: list[FXCurrencyExposure],
    risk_level: str,
    net_exposure: float,
) -> list[str]:
    """Kural-tabanlı FX risk önerileri. Elite Foundation'da AI ile zenginleştirilecek."""
    notes: list[str] = []

    if risk_level == "critical":
        notes.append(
            "🔴 KRİTİK: FX pozisyonu tek yönde aşırı konsantre. "
            "Hedging stratejisi (forward/swap) zorunlu."
        )
    elif risk_level == "concentrated":
        notes.append(
            "🟠 Yüksek konsantrasyon. Doğal hedge fırsatlarını "
            "(ihracat geliri vs ithalat gider eşleşmesi) gözden geçirin."
        )
    elif risk_level == "moderate":
        notes.append(
            "🟡 Orta seviye exposure. Aylık review uygun."
        )
    else:
        notes.append(
            "🟢 FX pozisyonu dengeli. Mevcut hedging stratejisi sürdürülebilir."
        )

    # Para birimi-spesifik öneriler
    for exp in exposures[:3]:  # Top 3 by impact
        if exp.currency == "TRY":
            continue
        if exp.position_type == "short" and abs(exp.net_position_try) > 100_000:
            notes.append(
                f"• {exp.currency} short pozisyonu ₺{abs(exp.net_position_try):,.0f} "
                f"— TL değer kaybında risk. Forward alımı değerlendirin."
            )
        elif exp.position_type == "long" and abs(exp.net_position_try) > 100_000:
            notes.append(
                f"• {exp.currency} long pozisyonu ₺{exp.net_position_try:,.0f} "
                f"— TL değer kazanırsa azalır. Forward satım koruyucu olabilir."
            )
        if exp.receivable_overdue > 0.5 * exp.receivable_open and exp.receivable_open > 0:
            notes.append(
                f"• {exp.currency} alacaklarının yarısından fazlası overdue "
                f"— tahsilat hızlandırma öncelikli."
            )

    return notes
