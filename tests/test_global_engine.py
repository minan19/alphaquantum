import unittest

from app.engines.global_analysis_engine import GlobalAnalysisEngine
from app.models import MarketSignalCard, MarketSignalsResponse


class _StubMacroProvider:
    @staticmethod
    def central_bank_catalog():
        return [
            {"bank": "FED", "series_id": "FEDFUNDS", "currency": "USD"},
            {"bank": "TCMB", "series_id": "IRSTCB01TRM156N", "currency": "TRY"},
        ]

    @staticmethod
    def indicator_label(indicator_code: str) -> str:
        labels = {
            "FP.CPI.TOTL.ZG": "Inflation, consumer prices (annual %)",
            "NY.GDP.MKTP.KD.ZG": "GDP growth (annual %)",
        }
        return labels.get(indicator_code, indicator_code)

    @staticmethod
    def fetch_fred_series(*, series_id: str, days: int):
        points = []
        for idx in range(days):
            points.append(
                {
                    "label": f"2025-01-{(idx % 28) + 1:02d}",
                    "value": 3.0 + (idx * 0.01) + (0.2 if series_id == "IRSTCB01TRM156N" else 0.0),
                }
            )
        return points, "stub_fred"

    @staticmethod
    def fetch_world_bank_indicator(*, country: str, indicator: str, years: int):
        points = []
        for idx in range(years):
            year = 2026 - (years - idx - 1)
            value = 2.0 + (idx * 0.2)
            if indicator == "FP.CPI.TOTL.ZG":
                value += 3.5
            points.append({"label": str(year), "value": value})
        return points, "stub_world_bank"


class _StubMarketEngine:
    @staticmethod
    def analyze_symbols(*, symbols, timeframe="1d", days=180, refresh=False):
        items = []
        for symbol in symbols:
            signal = "SELL" if symbol in {"SPX", "JPM"} else "BUY"
            trend = "DOWN" if signal == "SELL" else "UP"
            items.append(
                MarketSignalCard(
                    symbol=symbol,
                    signal=signal,
                    trend=trend,
                    rsi_14=62.3,
                    macd_histogram=-0.12 if signal == "SELL" else 0.08,
                    confidence=0.77,
                    last_close=100.0,
                    rationale="stub",
                )
            )
        return MarketSignalsResponse(
            timeframe=timeframe,
            generated_at="2026-03-20T00:00:00+00:00",
            items=items,
        )


class GlobalAnalysisEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = GlobalAnalysisEngine(
            market_engine=_StubMarketEngine(),
            macro_provider=_StubMacroProvider(),
        )

    def test_central_bank_panel(self) -> None:
        panel = self.engine.central_bank_panel(days=120)
        self.assertEqual(len(panel.items), 2)
        self.assertEqual(panel.items[0].bank, "FED")
        self.assertIn(panel.items[0].trend, {"UP", "DOWN", "SIDEWAYS"})
        self.assertGreaterEqual(len(panel.items[0].points), 100)

    def test_professional_report(self) -> None:
        report = self.engine.build_professional_report(
            countries=["USA", "TUR"],
            indicators=["FP.CPI.TOTL.ZG", "NY.GDP.MKTP.KD.ZG"],
            bank_symbols=["JPM", "BAC"],
            index_symbols=["SPX", "NDX"],
            market_days=120,
            macro_days=120,
            macro_years=12,
            refresh_market=False,
        )
        self.assertIn(report.risk_level, {"LOW", "MEDIUM", "HIGH"})
        self.assertIn("Global Financial Intelligence Report", report.report_markdown)
        self.assertGreaterEqual(len(report.central_banks), 2)
        self.assertGreaterEqual(len(report.world_bank), 2)
        self.assertGreaterEqual(len(report.bank_signals), 2)
        self.assertGreaterEqual(len(report.index_signals), 2)


if __name__ == "__main__":
    unittest.main()
