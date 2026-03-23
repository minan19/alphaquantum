import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.engines.market_data_engine import MarketDataEngine
from app.identity_repository import IdentityRepository
from app.market_repository import MarketDataRepository
from app.migration_manager import MigrationManager


class _StubProvider:
    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        return symbol.strip().upper()

    @staticmethod
    def fetch_ohlcv(*, symbol: str, timeframe: str, days: int):
        base = 100.0
        today = date.today()
        bars = []
        for idx in range(days):
            close = base + (idx * 0.8)
            open_price = close - 0.3
            high = close + 0.5
            low = close - 0.8
            volume = 1_000_000 + idx
            bars.append(
                {
                    "date": (today - timedelta(days=(days - idx - 1))).isoformat(),
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": float(volume),
                }
            )
        return bars, "stub"


class MarketDataEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._temp_dir.name) / "market_engine_test.db"

        identity_repo = IdentityRepository(str(self._db_path))
        identity_repo.close()
        migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
        self.migrations = MigrationManager(str(self._db_path), str(migrations_dir))
        self.migrations.apply_all()

        self.market_repo = MarketDataRepository(str(self._db_path))
        self.engine = MarketDataEngine(self.market_repo, provider=_StubProvider())

    def tearDown(self) -> None:
        self.market_repo.close()
        self.migrations.close()
        self._temp_dir.cleanup()

    def test_get_ohlcv_populates_cache(self) -> None:
        response = self.engine.get_ohlcv(symbol="AAPL", days=90, refresh=True)
        self.assertEqual(response.symbol, "AAPL")
        self.assertEqual(response.timeframe, "1d")
        self.assertEqual(response.source, "stub")
        self.assertEqual(len(response.bars), 90)

        cached_again = self.engine.get_ohlcv(symbol="AAPL", days=90, refresh=False)
        self.assertEqual(len(cached_again.bars), 90)

    def test_analysis_returns_indicators_and_signal(self) -> None:
        analysis = self.engine.analyze_symbol(symbol="AAPL", days=120, refresh=True)
        self.assertEqual(analysis.symbol, "AAPL")
        self.assertIn(analysis.signal, {"BUY", "HOLD", "SELL"})
        self.assertIn(analysis.indicators.trend, {"UP", "STRONG_UP", "DOWN", "STRONG_DOWN", "SIDEWAYS", "NO_DATA"})
        self.assertGreaterEqual(analysis.confidence, 0.0)
        self.assertLessEqual(analysis.confidence, 1.0)
        self.assertIsNotNone(analysis.indicators.rsi_14)
        self.assertIsNotNone(analysis.indicators.macd)

    def test_backtest_returns_metrics(self) -> None:
        result = self.engine.backtest_signal_strategy(
            symbol="AAPL",
            days=240,
            lookahead_days=5,
            hold_band=0.01,
            refresh=True,
        )
        self.assertEqual(result.symbol, "AAPL")
        self.assertGreater(result.sample_size, 0)
        self.assertGreaterEqual(result.win_rate, 0.0)
        self.assertLessEqual(result.win_rate, 1.0)
        self.assertGreaterEqual(result.max_drawdown, 0.0)
        self.assertLessEqual(result.max_drawdown, 1.0)
        self.assertGreaterEqual(result.buy_signals + result.sell_signals + result.hold_signals, result.sample_size)


if __name__ == "__main__":
    unittest.main()
