"""S-341 — FX rate conversion for multi-currency invoice & cashflow analysis.

This module is intentionally simple and deterministic:
- Default rates ship with the codebase (representative TRY pairs as of 2026-05).
- Environment variables (AQ_FX_<CCY>_TRY) override per-currency rates.
- An optional `rates` dict at construction time overrides everything else
  (useful for tests, what-if scenarios, or wiring in a live rate provider).

Future extension point: pull live rates from MarketDataEngine.get_ohlcv()
on USDTRY=X / EURTRY=X / GBPTRY=X symbols. Kept out of the default path so
that offline & test runs stay deterministic.
"""
from __future__ import annotations

import os


# Conservative defaults, May 2026 vintage. Override via env or constructor.
DEFAULT_FX_RATES_TO_TRY: dict[str, float] = {
    "TRY": 1.0,
    "USD": 32.5,
    "EUR": 35.0,
    "GBP": 41.0,
    "CHF": 36.0,
    "JPY": 0.21,
    "AUD": 21.5,
    "CAD": 23.7,
    "RUB": 0.36,
    "AED": 8.85,
    "SAR": 8.66,
    "CNY": 4.5,
}


class CurrencyConverter:
    """Convert foreign-currency amounts to TRY using a deterministic rate table.

    Resolution order (most specific wins):
        1. `rates` argument passed to constructor
        2. AQ_FX_<CCY>_TRY environment variable
        3. DEFAULT_FX_RATES_TO_TRY
        4. 1.0 (unknown currency → identity, never raises)
    """

    def __init__(self, rates: dict[str, float] | None = None) -> None:
        self._rates: dict[str, float] = dict(DEFAULT_FX_RATES_TO_TRY)
        # Env var overrides
        for ccy in list(self._rates.keys()):
            env_value = os.getenv(f"AQ_FX_{ccy}_TRY")
            if env_value:
                try:
                    parsed = float(env_value)
                    if parsed > 0:
                        self._rates[ccy] = parsed
                except ValueError:
                    pass
        # Explicit overrides
        if rates:
            for ccy, rate in rates.items():
                if rate > 0:
                    self._rates[ccy.upper()] = float(rate)

    def rate(self, currency: str) -> float:
        """Return the conversion rate from `currency` → TRY. Unknown returns 1.0."""
        return self._rates.get(currency.upper(), 1.0)

    def to_try(self, amount: float, currency: str) -> float:
        """Convert `amount` in `currency` to TRY. Unknown currency = identity."""
        return amount * self.rate(currency)

    def supported_currencies(self) -> list[str]:
        return sorted(self._rates.keys())
