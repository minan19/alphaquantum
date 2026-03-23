from __future__ import annotations

from datetime import datetime, timezone
import time

from app.market_data_provider import MarketDataProvider
from app.market_repository import MarketDataRepository
from app.models import (
    MarketAnalysisResponse,
    MarketBacktestResponse,
    MarketIndicatorSet,
    MarketOHLCVBar,
    MarketOHLCVResponse,
    MarketSignalCard,
    MarketSignalsResponse,
)


class MarketDataEngine:
    def __init__(
        self,
        repo: MarketDataRepository,
        provider: MarketDataProvider | None = None,
    ) -> None:
        self._repo = repo
        self._provider = provider or MarketDataProvider()

    def get_ohlcv(
        self,
        *,
        symbol: str,
        timeframe: str = "1d",
        days: int = 180,
        refresh: bool = False,
    ) -> MarketOHLCVResponse:
        normalized_symbol = self._provider.normalize_symbol(symbol)
        safe_days = max(20, min(days, 3650))
        self._refresh_if_needed(
            symbol=normalized_symbol,
            timeframe=timeframe,
            days=safe_days,
            force=refresh,
        )

        rows = self._repo.list_ohlcv(
            symbol=normalized_symbol,
            timeframe=timeframe,
            limit=safe_days,
        )
        source = str(rows[-1]["source"]) if rows else "unknown"
        bars = [
            MarketOHLCVBar(
                date=str(row["bar_date"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
            for row in rows
        ]
        return MarketOHLCVResponse(
            symbol=normalized_symbol,
            timeframe=timeframe,
            source=source,
            generated_at=datetime.now(timezone.utc).isoformat(),
            bars=bars,
        )

    def analyze_symbol(
        self,
        *,
        symbol: str,
        timeframe: str = "1d",
        days: int = 180,
        refresh: bool = False,
    ) -> MarketAnalysisResponse:
        ohlcv = self.get_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            days=days,
            refresh=refresh,
        )
        close_prices = [bar.close for bar in ohlcv.bars]
        indicators = self._calculate_indicators(close_prices)
        signal, confidence, rationale = self._signal_from_indicators(indicators)

        return MarketAnalysisResponse(
            symbol=ohlcv.symbol,
            timeframe=ohlcv.timeframe,
            source=ohlcv.source,
            as_of=ohlcv.bars[-1].date if ohlcv.bars else None,
            last_close=ohlcv.bars[-1].close if ohlcv.bars else None,
            indicators=indicators,
            signal=signal,
            confidence=confidence,
            rationale=rationale,
        )

    def analyze_symbols(
        self,
        *,
        symbols: list[str],
        timeframe: str = "1d",
        days: int = 180,
        refresh: bool = False,
    ) -> MarketSignalsResponse:
        cards: list[MarketSignalCard] = []
        for raw_symbol in symbols:
            symbol = raw_symbol.strip()
            if not symbol:
                continue
            analysis = self.analyze_symbol(
                symbol=symbol,
                timeframe=timeframe,
                days=days,
                refresh=refresh,
            )
            cards.append(
                MarketSignalCard(
                    symbol=analysis.symbol,
                    signal=analysis.signal,
                    trend=analysis.indicators.trend,
                    rsi_14=analysis.indicators.rsi_14,
                    macd_histogram=analysis.indicators.macd_histogram,
                    confidence=analysis.confidence,
                    last_close=analysis.last_close,
                    rationale=analysis.rationale,
                )
            )

        cards.sort(
            key=lambda card: (
                _signal_priority(card.signal),
                card.confidence,
            ),
            reverse=True,
        )
        return MarketSignalsResponse(
            timeframe=timeframe,
            generated_at=datetime.now(timezone.utc).isoformat(),
            items=cards,
        )

    def refresh_symbols(
        self,
        *,
        symbols: list[str],
        timeframe: str = "1d",
        days: int = 180,
    ) -> list[str]:
        refreshed: list[str] = []
        for raw_symbol in symbols:
            symbol = raw_symbol.strip()
            if not symbol:
                continue
            normalized = self._provider.normalize_symbol(symbol)
            bars, source = self._provider.fetch_ohlcv(
                symbol=normalized,
                timeframe=timeframe,
                days=max(20, min(days, 3650)),
            )
            self._repo.upsert_ohlcv(
                symbol=normalized,
                timeframe=timeframe,
                bars=bars,
                source=source,
            )
            refreshed.append(normalized)
        return refreshed

    def backtest_signal_strategy(
        self,
        *,
        symbol: str,
        timeframe: str = "1d",
        days: int = 360,
        lookahead_days: int = 5,
        hold_band: float = 0.01,
        refresh: bool = False,
    ) -> MarketBacktestResponse:
        safe_days = max(80, min(days, 3650))
        safe_lookahead = max(1, min(lookahead_days, 30))
        safe_hold_band = max(0.0, min(hold_band, 0.2))
        ohlcv = self.get_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            days=safe_days,
            refresh=refresh,
        )

        close_prices = [bar.close for bar in ohlcv.bars]
        min_history = 60
        if len(close_prices) <= (min_history + safe_lookahead):
            return MarketBacktestResponse(
                symbol=ohlcv.symbol,
                timeframe=ohlcv.timeframe,
                source=ohlcv.source,
                generated_at=datetime.now(timezone.utc).isoformat(),
                lookback_days=safe_days,
                lookahead_days=safe_lookahead,
                hold_band=safe_hold_band,
                sample_size=0,
                buy_signals=0,
                sell_signals=0,
                hold_signals=0,
                win_rate=0.0,
                average_signal_return=0.0,
                cumulative_return=0.0,
                benchmark_return=0.0,
                strategy_edge=0.0,
                max_drawdown=0.0,
                notes="Not enough data to run backtest window.",
            )

        buy_signals = 0
        sell_signals = 0
        hold_signals = 0
        wins = 0
        strategy_returns: list[float] = []
        equity_curve: list[float] = [1.0]

        for idx in range(min_history, len(close_prices) - safe_lookahead):
            history = close_prices[: idx + 1]
            indicators = self._calculate_indicators(history)
            signal, _, _ = self._signal_from_indicators(indicators)
            entry = close_prices[idx]
            exit_price = close_prices[idx + safe_lookahead]
            if entry <= 0:
                continue

            future_return = (exit_price - entry) / entry
            if signal == "BUY":
                buy_signals += 1
                strategy_return = future_return
                success = future_return > 0
            elif signal == "SELL":
                sell_signals += 1
                strategy_return = -future_return
                success = future_return < 0
            else:
                hold_signals += 1
                strategy_return = 0.0
                success = abs(future_return) <= safe_hold_band

            wins += 1 if success else 0
            clipped_return = max(-0.95, min(strategy_return, 2.0))
            strategy_returns.append(clipped_return)
            equity_curve.append(equity_curve[-1] * (1 + clipped_return))

        sample_size = len(strategy_returns)
        if sample_size == 0:
            benchmark_return = 0.0
            average_signal_return = 0.0
            cumulative_return = 0.0
            strategy_edge = 0.0
            win_rate = 0.0
            max_drawdown = 0.0
        else:
            first_close = close_prices[min_history]
            last_close = close_prices[-1]
            benchmark_return = ((last_close - first_close) / first_close) if first_close > 0 else 0.0
            average_signal_return = sum(strategy_returns) / sample_size
            cumulative_return = equity_curve[-1] - 1
            strategy_edge = cumulative_return - benchmark_return
            win_rate = wins / sample_size
            max_drawdown = _max_drawdown(equity_curve)

        return MarketBacktestResponse(
            symbol=ohlcv.symbol,
            timeframe=ohlcv.timeframe,
            source=ohlcv.source,
            generated_at=datetime.now(timezone.utc).isoformat(),
            lookback_days=safe_days,
            lookahead_days=safe_lookahead,
            hold_band=safe_hold_band,
            sample_size=sample_size,
            buy_signals=buy_signals,
            sell_signals=sell_signals,
            hold_signals=hold_signals,
            win_rate=round(win_rate, 4),
            average_signal_return=round(average_signal_return, 6),
            cumulative_return=round(cumulative_return, 6),
            benchmark_return=round(benchmark_return, 6),
            strategy_edge=round(strategy_edge, 6),
            max_drawdown=round(max_drawdown, 6),
            notes=(
                "Rule-based walk-forward backtest using current trend/RSI/MACD signal model. "
                "Not investment advice."
            ),
        )

    def _refresh_if_needed(
        self,
        *,
        symbol: str,
        timeframe: str,
        days: int,
        force: bool,
    ) -> None:
        cached = self._repo.list_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            limit=days,
        )
        latest_fetch_at = self._repo.latest_fetch_at(symbol=symbol, timeframe=timeframe)
        cache_ttl_seconds = 900
        cache_fresh = latest_fetch_at is not None and (int(time.time()) - latest_fetch_at) <= cache_ttl_seconds
        enough_depth = len(cached) >= min(days, 60)
        if not force and cache_fresh and enough_depth:
            return

        bars, source = self._provider.fetch_ohlcv(symbol=symbol, timeframe=timeframe, days=days)
        self._repo.upsert_ohlcv(symbol=symbol, timeframe=timeframe, bars=bars, source=source)

    def _calculate_indicators(self, close_prices: list[float]) -> MarketIndicatorSet:
        if not close_prices:
            return MarketIndicatorSet(
                trend="NO_DATA",
                rsi_14=None,
                macd=None,
                macd_signal=None,
                macd_histogram=None,
            )

        trend = self._trend_label(close_prices)
        rsi_value = self._rsi(close_prices, period=14)
        macd_value, macd_signal, macd_hist = self._macd(close_prices)
        return MarketIndicatorSet(
            trend=trend,
            rsi_14=rsi_value,
            macd=macd_value,
            macd_signal=macd_signal,
            macd_histogram=macd_hist,
        )

    @staticmethod
    def _signal_from_indicators(indicators: MarketIndicatorSet) -> tuple[str, float, str]:
        score = 0
        reasons: list[str] = []

        if indicators.trend in {"UP", "STRONG_UP"}:
            score += 1
            reasons.append("trend_up")
        elif indicators.trend in {"DOWN", "STRONG_DOWN"}:
            score -= 1
            reasons.append("trend_down")

        if indicators.rsi_14 is not None:
            if indicators.rsi_14 < 35:
                score += 1
                reasons.append("rsi_oversold")
            elif indicators.rsi_14 > 68:
                score -= 1
                reasons.append("rsi_overbought")

        if indicators.macd_histogram is not None:
            if indicators.macd_histogram > 0:
                score += 1
                reasons.append("macd_positive")
            elif indicators.macd_histogram < 0:
                score -= 1
                reasons.append("macd_negative")

        if score >= 2:
            signal = "BUY"
        elif score <= -2:
            signal = "SELL"
        else:
            signal = "HOLD"

        confidence = min(
            0.95,
            0.45
            + (abs(score) * 0.16)
            + (0.08 if indicators.trend in {"STRONG_UP", "STRONG_DOWN"} else 0.0),
        )
        rationale = ",".join(reasons) if reasons else "mixed_signals"
        return signal, round(confidence, 2), rationale

    @staticmethod
    def _trend_label(close_prices: list[float]) -> str:
        if len(close_prices) < 20:
            return "SIDEWAYS"

        sma20 = sum(close_prices[-20:]) / 20
        sma50_window = close_prices[-50:] if len(close_prices) >= 50 else close_prices[-20:]
        sma50 = sum(sma50_window) / len(sma50_window)
        last_close = close_prices[-1]
        reference = close_prices[-10] if len(close_prices) >= 10 else close_prices[0]
        if reference <= 0:
            return "SIDEWAYS"

        momentum_10 = ((last_close - reference) / reference) * 100
        if last_close > sma20 > sma50 and momentum_10 > 1.8:
            return "STRONG_UP"
        if last_close > sma20 and momentum_10 > 0.3:
            return "UP"
        if last_close < sma20 < sma50 and momentum_10 < -1.8:
            return "STRONG_DOWN"
        if last_close < sma20 and momentum_10 < -0.3:
            return "DOWN"
        return "SIDEWAYS"

    @staticmethod
    def _rsi(close_prices: list[float], period: int = 14) -> float | None:
        if len(close_prices) < period + 1:
            return None

        deltas = [close_prices[idx] - close_prices[idx - 1] for idx in range(1, len(close_prices))]
        window = deltas[-period:]
        gains = [delta for delta in window if delta > 0]
        losses = [-delta for delta in window if delta < 0]
        average_gain = sum(gains) / period
        average_loss = sum(losses) / period

        if average_loss == 0 and average_gain == 0:
            return 50.0
        if average_loss == 0:
            return 100.0

        rs = average_gain / average_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)

    def _macd(self, close_prices: list[float]) -> tuple[float | None, float | None, float | None]:
        ema12 = self._ema(close_prices, period=12)
        ema26 = self._ema(close_prices, period=26)
        if ema12 is None or ema26 is None:
            return None, None, None

        macd_values = [short - long for short, long in zip(ema12, ema26)]
        signal_values = self._ema(macd_values, period=9)
        if signal_values is None:
            return round(macd_values[-1], 4), None, None

        macd = macd_values[-1]
        signal = signal_values[-1]
        hist = macd - signal
        return round(macd, 4), round(signal, 4), round(hist, 4)

    @staticmethod
    def _ema(values: list[float], period: int) -> list[float] | None:
        if len(values) < period:
            return None

        multiplier = 2 / (period + 1)
        seed = sum(values[:period]) / period
        ema_values: list[float] = [seed]
        current = seed
        for value in values[period:]:
            current = ((value - current) * multiplier) + current
            ema_values.append(current)

        # Align to the source length by prepending the seed.
        padding = [seed] * (len(values) - len(ema_values))
        return padding + ema_values


def _signal_priority(signal: str) -> int:
    if signal == "BUY":
        return 3
    if signal == "SELL":
        return 2
    return 1


def _max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0

    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        if peak <= 0:
            continue
        drawdown = (peak - value) / peak
        if drawdown > max_dd:
            max_dd = drawdown
    return max_dd
