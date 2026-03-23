from __future__ import annotations

import csv
from datetime import date, timedelta
import hashlib
from io import StringIO
import math
import os

import httpx


class MarketDataProvider:
    def fetch_ohlcv(
        self,
        *,
        symbol: str,
        timeframe: str,
        days: int,
    ) -> tuple[list[dict[str, float | str]], str]:
        if timeframe != "1d":
            raise ValueError("Only 1d timeframe is currently supported")

        normalized = self.normalize_symbol(symbol)
        if _is_truthy(os.getenv("AQ_MARKET_OFFLINE")):
            return self._build_synthetic_series(normalized, days), "synthetic"

        stooq_symbol = self._to_stooq_symbol(normalized)
        url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"

        try:
            with httpx.Client(timeout=6.0, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()

            rows = self._parse_stooq_csv(response.text)
            if rows:
                return rows[-days:], "stooq"
        except Exception:
            # Hard fallback keeps API functional when external data source is unavailable.
            return self._build_synthetic_series(normalized, days), "synthetic"

        return self._build_synthetic_series(normalized, days), "synthetic"

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        cleaned = symbol.strip().upper()
        if not cleaned:
            raise ValueError("symbol is required")

        if ":" in cleaned:
            _, _, cleaned = cleaned.rpartition(":")
            cleaned = cleaned.strip().upper()

        return cleaned

    @staticmethod
    def _to_stooq_symbol(symbol: str) -> str:
        if "." in symbol:
            return symbol.lower()
        if symbol.isalpha() and len(symbol) <= 6:
            return f"{symbol}.us".lower()
        return symbol.lower()

    @staticmethod
    def _parse_stooq_csv(raw_csv: str) -> list[dict[str, float | str]]:
        reader = csv.DictReader(StringIO(raw_csv))
        rows: list[dict[str, float | str]] = []
        for row in reader:
            try:
                bar_date = str(row["Date"]).strip()
                open_price = float(row["Open"])
                high_price = float(row["High"])
                low_price = float(row["Low"])
                close_price = float(row["Close"])
                volume_raw = str(row.get("Volume", "0")).strip()
                volume = float(volume_raw) if volume_raw not in {"", "null", "None"} else 0.0
            except (KeyError, TypeError, ValueError):
                continue

            if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
                continue

            rows.append(
                {
                    "date": bar_date,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,
                }
            )

        rows.sort(key=lambda item: str(item["date"]))
        return rows

    @staticmethod
    def _build_synthetic_series(symbol: str, days: int) -> list[dict[str, float | str]]:
        digest = hashlib.sha256(symbol.encode("utf-8")).hexdigest()
        seed = int(digest[:12], 16)
        base_price = 40.0 + (seed % 220)
        trend_bias = ((seed // 11) % 21 - 10) / 10.0
        amplitude = 1.5 + ((seed // 37) % 60) / 10.0
        phase = ((seed // 101) % 360) * math.pi / 180.0

        today = date.today()
        rows: list[dict[str, float | str]] = []

        for idx in range(days):
            step = idx + 1
            daily_trend = trend_bias * step / max(days, 1)
            oscillation = math.sin((step / 7.0) + phase) * amplitude
            close_price = max(1.0, base_price + daily_trend + oscillation)
            open_price = max(1.0, close_price * (1 + math.sin(step / 5.0 + phase) * 0.006))
            high_price = max(open_price, close_price) * 1.004
            low_price = min(open_price, close_price) * 0.996
            volume = 500_000 + ((seed + step * 13_579) % 6_000_000)
            bar_date = (today - timedelta(days=(days - step))).isoformat()
            rows.append(
                {
                    "date": bar_date,
                    "open": round(open_price, 4),
                    "high": round(high_price, 4),
                    "low": round(low_price, 4),
                    "close": round(close_price, 4),
                    "volume": float(volume),
                }
            )

        return rows


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
