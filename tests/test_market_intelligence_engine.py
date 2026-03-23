import unittest

from app.engines.market_intelligence_engine import MarketIntelligenceEngine
from app.models import (
    InstitutionPageFinding,
    InstitutionReportResponse,
    MarketAnalysisResponse,
    MarketIndicatorSet,
    MarketIntelligenceRequest,
    MarketPageRequest,
)


class _StubInstitutionEngine:
    def __init__(self) -> None:
        self.last_payload = None

    def build_report(self, payload) -> InstitutionReportResponse:
        self.last_payload = payload
        return InstitutionReportResponse(
            generated_at="2026-03-21T00:00:00+00:00",
            page_count=2,
            requested_terms=["market"],
            executive_summary="stub",
            pages=[
                InstitutionPageFinding(
                    url="https://example.com/market",
                    source_domain="example.com",
                    status="ok",
                    title="AAPL and MSFT market bulletin",
                    summary="AAPL increased 2.5 percent while SPX decreased 1.1 percent.",
                    matched_terms=["market"],
                    matched_snippets=[
                        "AAPL momentum remains positive at 2.5%",
                        "MSFT near resistance with 410.1 close",
                    ],
                    extracted_table_rows=[
                        ["Symbol", "Close"],
                        ["AAPL", "190.40"],
                        ["MSFT", "410.10"],
                    ],
                    fetched_at="2026-03-21T00:00:00+00:00",
                    error=None,
                ),
                InstitutionPageFinding(
                    url="https://example.com/fail",
                    source_domain="example.com",
                    status="error",
                    summary="error",
                    error="fetch failure",
                ),
            ],
        )


class _StubMarketEngine:
    @staticmethod
    def analyze_symbol(*, symbol: str, timeframe: str, days: int, refresh: bool) -> MarketAnalysisResponse:
        del timeframe, days, refresh
        signal_map = {
            "AAPL": ("BUY", 0.91, "trend_up,macd_positive"),
            "MSFT": ("HOLD", 0.53, "mixed_signals"),
            "NVDA": ("SELL", 0.87, "trend_down,macd_negative"),
        }
        signal, confidence, rationale = signal_map.get(symbol, ("HOLD", 0.5, "mixed_signals"))
        return MarketAnalysisResponse(
            symbol=symbol,
            timeframe="1d",
            source="stub",
            as_of="2026-03-21",
            last_close=123.45,
            indicators=MarketIndicatorSet(
                trend="UP",
                rsi_14=55.0,
                macd=0.5,
                macd_signal=0.3,
                macd_histogram=0.2,
            ),
            signal=signal,
            confidence=confidence,
            rationale=rationale,
        )


class MarketIntelligenceEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.institution_engine = _StubInstitutionEngine()
        self.engine = MarketIntelligenceEngine(
            market_engine=_StubMarketEngine(),
            institution_engine=self.institution_engine,
        )

    def test_build_report_extracts_symbols_and_generates_recommendations(self) -> None:
        payload = MarketIntelligenceRequest(
            pages=[
                MarketPageRequest(
                    url="https://example.com/market",
                    focus_terms=["market", "index"],
                )
            ],
            focus_symbols=["NVDA"],
            days=120,
            max_symbols=3,
        )

        report = self.engine.build_report(payload)
        self.assertEqual(len(report.pages), 2)
        self.assertEqual(report.pages[0].status, "ok")
        self.assertEqual(report.pages[1].status, "error")
        self.assertGreaterEqual(len(report.pages[0].extracted_symbols), 2)
        self.assertGreaterEqual(len(report.pages[0].extracted_numbers), 1)
        self.assertIn("NVDA", report.analyzed_symbols)
        self.assertGreaterEqual(len(report.recommendations), 1)
        self.assertTrue(report.executive_summary.startswith("Analyzed"))
        self.assertIn("does not guarantee profit", report.disclaimer)

        recommendation_symbols = {item.symbol for item in report.recommendations}
        self.assertIn("AAPL", recommendation_symbols)
        self.assertIn("NVDA", recommendation_symbols)

    def test_default_exchange_sources_are_appended(self) -> None:
        payload = MarketIntelligenceRequest(
            pages=[MarketPageRequest(url="https://example.com/market")],
            include_default_exchange_pages=True,
            regions=["TR", "EU"],
            max_pages=5,
        )
        self.engine.build_report(payload)
        self.assertIsNotNone(self.institution_engine.last_payload)
        page_urls = [item.url for item in self.institution_engine.last_payload.pages]
        self.assertGreaterEqual(len(page_urls), 2)
        self.assertIn("https://example.com/market", page_urls)


if __name__ == "__main__":
    unittest.main()
