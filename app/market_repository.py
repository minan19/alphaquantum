from __future__ import annotations

from threading import Lock
from typing import Any
import sqlite3
import time


class MarketDataRepository:
    def __init__(self, database_path: str) -> None:
        self._lock = Lock()
        self._conn = self._connect(database_path)

    @staticmethod
    def _connect(database_path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(database_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def close(self) -> None:
        self._conn.close()

    def upsert_ohlcv(
        self,
        *,
        symbol: str,
        timeframe: str,
        bars: list[dict[str, Any]],
        source: str,
    ) -> None:
        if not bars:
            return

        fetched_at = int(time.time())
        with self._lock:
            for bar in bars:
                self._conn.execute(
                    """
                    INSERT INTO market_ohlcv_cache(
                        symbol,
                        timeframe,
                        bar_date,
                        open,
                        high,
                        low,
                        close,
                        volume,
                        source,
                        fetched_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, timeframe, bar_date) DO UPDATE SET
                        open = excluded.open,
                        high = excluded.high,
                        low = excluded.low,
                        close = excluded.close,
                        volume = excluded.volume,
                        source = excluded.source,
                        fetched_at = excluded.fetched_at
                    """,
                    (
                        symbol,
                        timeframe,
                        str(bar["date"]),
                        float(bar["open"]),
                        float(bar["high"]),
                        float(bar["low"]),
                        float(bar["close"]),
                        float(bar["volume"]),
                        source,
                        fetched_at,
                    ),
                )
            self._conn.commit()

    def list_ohlcv(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 5000))

        if start_date and end_date:
            query = """
                SELECT
                    symbol,
                    timeframe,
                    bar_date,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    source,
                    fetched_at
                FROM market_ohlcv_cache
                WHERE symbol = ? AND timeframe = ? AND bar_date >= ? AND bar_date <= ?
                ORDER BY bar_date DESC
                LIMIT ?
            """
            params: list[Any] = [symbol, timeframe, start_date, end_date, safe_limit]
        elif start_date:
            query = """
                SELECT
                    symbol,
                    timeframe,
                    bar_date,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    source,
                    fetched_at
                FROM market_ohlcv_cache
                WHERE symbol = ? AND timeframe = ? AND bar_date >= ?
                ORDER BY bar_date DESC
                LIMIT ?
            """
            params = [symbol, timeframe, start_date, safe_limit]
        elif end_date:
            query = """
                SELECT
                    symbol,
                    timeframe,
                    bar_date,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    source,
                    fetched_at
                FROM market_ohlcv_cache
                WHERE symbol = ? AND timeframe = ? AND bar_date <= ?
                ORDER BY bar_date DESC
                LIMIT ?
            """
            params = [symbol, timeframe, end_date, safe_limit]
        else:
            query = """
                SELECT
                    symbol,
                    timeframe,
                    bar_date,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    source,
                    fetched_at
                FROM market_ohlcv_cache
                WHERE symbol = ? AND timeframe = ?
                ORDER BY bar_date DESC
                LIMIT ?
            """
            params = [symbol, timeframe, safe_limit]

        with self._lock:
            rows = self._conn.execute(query, params).fetchall()

        # External consumers expect chronological order.
        ordered = [dict(row) for row in rows]
        ordered.reverse()
        return ordered

    def latest_fetch_at(self, *, symbol: str, timeframe: str) -> int | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT MAX(fetched_at) AS fetched_at
                FROM market_ohlcv_cache
                WHERE symbol = ? AND timeframe = ?
                """,
                (symbol, timeframe),
            ).fetchone()
        if row is None or row["fetched_at"] is None:
            return None
        return int(row["fetched_at"])
