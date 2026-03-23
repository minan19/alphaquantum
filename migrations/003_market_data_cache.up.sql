CREATE TABLE IF NOT EXISTS market_ohlcv_cache (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    bar_date TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    source TEXT NOT NULL DEFAULT 'unknown',
    fetched_at INTEGER NOT NULL,
    PRIMARY KEY(symbol, timeframe, bar_date)
);

CREATE INDEX IF NOT EXISTS idx_market_ohlcv_symbol_timeframe_date
    ON market_ohlcv_cache(symbol, timeframe, bar_date DESC);

CREATE INDEX IF NOT EXISTS idx_market_ohlcv_fetched_at
    ON market_ohlcv_cache(fetched_at DESC);
