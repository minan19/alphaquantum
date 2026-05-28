from __future__ import annotations

from typing import Any


from datetime import datetime, timezone

from app.engines.market_data_engine import MarketDataEngine
from app.macro_data_provider import MacroDataProvider
from app.models import (
    CentralBankPanelResponse,
    CentralBankRateSnapshot,
    ProfessionalReportResponse,
    SeriesPoint,
    WorldBankIndicatorSnapshot,
    WorldBankPanelResponse,
)


class GlobalAnalysisEngine:
    def __init__(
        self,
        market_engine: MarketDataEngine,
        macro_provider: MacroDataProvider | None = None,
    ) -> None:
        self._market_engine = market_engine
        self._macro_provider = macro_provider or MacroDataProvider()

    def central_bank_panel(self, *, days: int = 720) -> CentralBankPanelResponse:
        items: list[CentralBankRateSnapshot] = []
        for row in self._macro_provider.central_bank_catalog():
            points, source = self._macro_provider.fetch_fred_series(
                series_id=row["series_id"],
                days=days,
            )
            items.append(
                self._build_central_bank_snapshot(
                    bank=row["bank"],
                    series_id=row["series_id"],
                    currency=row["currency"],
                    points=points,
                    source=source,
                )
            )

        return CentralBankPanelResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            items=items,
        )

    def world_bank_panel(
        self,
        *,
        countries: list[str],
        indicators: list[str],
        years: int = 20,
    ) -> WorldBankPanelResponse:
        safe_countries = _normalize_tokens(countries)
        safe_indicators = _normalize_tokens(indicators)
        if not safe_countries:
            safe_countries = ["USA", "TUR", "DEU"]
        if not safe_indicators:
            safe_indicators = ["FP.CPI.TOTL.ZG", "NY.GDP.MKTP.KD.ZG", "SL.UEM.TOTL.ZS"]

        items: list[WorldBankIndicatorSnapshot] = []
        for country in safe_countries:
            for indicator in safe_indicators:
                points, source = self._macro_provider.fetch_world_bank_indicator(
                    country=country,
                    indicator=indicator,
                    years=years,
                )
                items.append(
                    self._build_world_bank_snapshot(
                        country=country,
                        indicator=indicator,
                        points=points,
                        source=source,
                    )
                )

        return WorldBankPanelResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            items=items,
        )

    def build_professional_report(
        self,
        *,
        countries: list[str],
        indicators: list[str],
        bank_symbols: list[str],
        index_symbols: list[str],
        market_days: int = 260,
        macro_days: int = 720,
        macro_years: int = 20,
        refresh_market: bool = False,
    ) -> ProfessionalReportResponse:
        central_banks = self.central_bank_panel(days=macro_days).items
        world_bank = self.world_bank_panel(
            countries=countries,
            indicators=indicators,
            years=macro_years,
        ).items

        resolved_bank_symbols = _normalize_tokens(bank_symbols) or ["JPM", "BAC", "HSBC", "BNP.PA"]
        resolved_index_symbols = _normalize_tokens(index_symbols) or ["SPX", "NDX", "DAX", "XU100"]

        bank_signals = self._market_engine.analyze_symbols(
            symbols=resolved_bank_symbols,
            days=market_days,
            refresh=refresh_market,
        ).items
        index_signals = self._market_engine.analyze_symbols(
            symbols=resolved_index_symbols,
            days=market_days,
            refresh=refresh_market,
        ).items

        risk_level = self._compute_risk_level(
            central_banks=central_banks,
            world_bank=world_bank,
            bank_signals=bank_signals,
            index_signals=index_signals,
        )
        executive_summary = self._build_executive_summary(
            risk_level=risk_level,
            central_banks=central_banks,
            bank_signals=bank_signals,
            index_signals=index_signals,
        )
        report_markdown = self._build_markdown_report(
            risk_level=risk_level,
            executive_summary=executive_summary,
            central_banks=central_banks,
            world_bank=world_bank,
            bank_signals=bank_signals,
            index_signals=index_signals,
        )

        return ProfessionalReportResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            risk_level=risk_level,
            executive_summary=executive_summary,
            central_banks=central_banks,
            world_bank=world_bank,
            bank_signals=bank_signals,
            index_signals=index_signals,
            report_markdown=report_markdown,
        )

    @staticmethod
    def _build_central_bank_snapshot(
        *,
        bank: str,
        series_id: str,
        currency: str,
        points: list[dict[str, float | str]],
        source: str,
    ) -> CentralBankRateSnapshot:
        typed_points = [SeriesPoint(label=str(item["label"]), value=float(item["value"])) for item in points]
        latest_rate = typed_points[-1].value if typed_points else None
        change_90d = _change_from_lookback(typed_points, lookback=90)
        trend = "SIDEWAYS"
        if change_90d is not None:
            if change_90d > 0.25:
                trend = "UP"
            elif change_90d < -0.25:
                trend = "DOWN"

        return CentralBankRateSnapshot(
            bank=bank,
            series_id=series_id,
            currency=currency,
            latest_rate=latest_rate,
            trend=trend,
            change_90d=change_90d,
            points=typed_points,
            source=source,
        )

    def _build_world_bank_snapshot(
        self,
        *,
        country: str,
        indicator: str,
        points: list[dict[str, float | str]],
        source: str,
    ) -> WorldBankIndicatorSnapshot:
        typed_points = [SeriesPoint(label=str(item["label"]), value=float(item["value"])) for item in points]
        latest = typed_points[-1].value if typed_points else None
        previous = typed_points[-2].value if len(typed_points) >= 2 else None
        change = round(latest - previous, 3) if latest is not None and previous is not None else None
        return WorldBankIndicatorSnapshot(
            country=country,
            indicator=indicator,
            indicator_name=self._macro_provider.indicator_label(indicator),
            latest_value=latest,
            previous_value=previous,
            change=change,
            points=typed_points,
            source=source,
        )

    @staticmethod
    def _compute_risk_level(
        *,
        central_banks: list[CentralBankRateSnapshot],
        world_bank: list[WorldBankIndicatorSnapshot],
        bank_signals: list[Any],
        index_signals: list[Any],
    ) -> str:
        score = 0
        for item in bank_signals + index_signals:
            if item.signal == "SELL":
                score += 2
            elif item.signal == "BUY":
                score -= 1

        for item in central_banks:
            if item.trend == "UP" and item.latest_rate is not None and item.latest_rate >= 4.0:
                score += 1

        for item in world_bank:
            if item.indicator == "FP.CPI.TOTL.ZG" and item.latest_value is not None and item.latest_value >= 6.0:
                score += 1
            if item.indicator == "NY.GDP.MKTP.KD.ZG" and item.latest_value is not None and item.latest_value <= 1.0:
                score += 1

        if score >= 7:
            return "HIGH"
        if score >= 3:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _build_executive_summary(
        *,
        risk_level: str,
        central_banks: list[CentralBankRateSnapshot],
        bank_signals: list[Any],
        index_signals: list[Any],
    ) -> str:
        hawkish = sum(1 for item in central_banks if item.trend == "UP")
        sell_count = sum(1 for item in (bank_signals + index_signals) if item.signal == "SELL")
        buy_count = sum(1 for item in (bank_signals + index_signals) if item.signal == "BUY")

        return (
            f"Global macro-financial risk level is {risk_level}. "
            f"Central bank tightening signals: {hawkish}. "
            f"Market SELL signals: {sell_count}, BUY signals: {buy_count}. "
            "Recommendation: keep portfolio risk controls active, rebalance sector exposure "
            "based on signal concentration and policy-rate trend."
        )

    @staticmethod
    def _build_markdown_report(
        *,
        risk_level: str,
        executive_summary: str,
        central_banks: list[CentralBankRateSnapshot],
        world_bank: list[WorldBankIndicatorSnapshot],
        bank_signals: list[Any],
        index_signals: list[Any],
    ) -> str:
        lines: list[str] = []
        lines.append("# Global Financial Intelligence Report")
        lines.append("")
        lines.append(f"Risk Level: **{risk_level}**")
        lines.append("")
        lines.append("## Executive Summary")
        lines.append(executive_summary)
        lines.append("")
        lines.append("## Central Banks (Rate Regime)")
        lines.append("| Bank | Latest Rate | 90D Change | Trend | Source |")
        lines.append("|---|---:|---:|---|---|")
        for item in central_banks:
            latest = "-" if item.latest_rate is None else f"{item.latest_rate:.2f}"
            change = "-" if item.change_90d is None else f"{item.change_90d:+.2f}"
            lines.append(
                f"| {item.bank} | {latest} | {change} | {item.trend} | {item.source} |"
            )
        lines.append("")
        lines.append("## World Bank Indicators")
        lines.append("| Country | Indicator | Latest | Previous | Change | Source |")
        lines.append("|---|---|---:|---:|---:|---|")
        for item in world_bank:
            latest = "-" if item.latest_value is None else f"{item.latest_value:.2f}"
            previous = "-" if item.previous_value is None else f"{item.previous_value:.2f}"
            change = "-" if item.change is None else f"{item.change:+.2f}"
            lines.append(
                f"| {item.country} | {item.indicator_name} | {latest} | {previous} | {change} | {item.source} |"
            )
        lines.append("")
        lines.append("## Bank Equity Signals")
        lines.append("| Symbol | Signal | Trend | RSI14 | MACD Hist | Confidence |")
        lines.append("|---|---|---|---:|---:|---:|")
        for item in bank_signals:
            rsi = "-" if item.rsi_14 is None else f"{item.rsi_14:.2f}"
            macd = "-" if item.macd_histogram is None else f"{item.macd_histogram:.4f}"
            lines.append(
                f"| {item.symbol} | {item.signal} | {item.trend} | {rsi} | {macd} | {item.confidence:.2f} |"
            )
        lines.append("")
        lines.append("## Global Index Signals")
        lines.append("| Symbol | Signal | Trend | RSI14 | MACD Hist | Confidence |")
        lines.append("|---|---|---|---:|---:|---:|")
        for item in index_signals:
            rsi = "-" if item.rsi_14 is None else f"{item.rsi_14:.2f}"
            macd = "-" if item.macd_histogram is None else f"{item.macd_histogram:.4f}"
            lines.append(
                f"| {item.symbol} | {item.signal} | {item.trend} | {rsi} | {macd} | {item.confidence:.2f} |"
            )
        return "\n".join(lines)


def _normalize_tokens(raw_values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        token = value.strip().upper()
        if not token or token in seen:
            continue
        seen.add(token)
        cleaned.append(token)
    return cleaned


def _change_from_lookback(points: list[SeriesPoint], *, lookback: int) -> float | None:
    if len(points) < 2:
        return None
    idx = max(0, len(points) - lookback - 1)
    base = points[idx].value
    latest = points[-1].value
    return round(latest - base, 3)
