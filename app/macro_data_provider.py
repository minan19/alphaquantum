from __future__ import annotations

import csv
from datetime import date, timedelta
import hashlib
from io import StringIO
import math
import os
from urllib.parse import quote

import httpx


class MacroDataProvider:
    _CENTRAL_BANK_SERIES: list[dict[str, str]] = [
        {"bank": "FED", "series_id": "FEDFUNDS", "currency": "USD"},
        {"bank": "ECB", "series_id": "ECBDFR", "currency": "EUR"},
        {"bank": "BOE", "series_id": "IRSTCB01GBM156N", "currency": "GBP"},
        {"bank": "BOJ", "series_id": "IRSTCB01JPM156N", "currency": "JPY"},
        {"bank": "TCMB", "series_id": "IRSTCB01TRM156N", "currency": "TRY"},
    ]

    _WORLD_BANK_INDICATORS: dict[str, str] = {
        "FP.CPI.TOTL.ZG": "Inflation, consumer prices (annual %)",
        "NY.GDP.MKTP.KD.ZG": "GDP growth (annual %)",
        "SL.UEM.TOTL.ZS": "Unemployment, total (% of labor force)",
    }

    def central_bank_catalog(self) -> list[dict[str, str]]:
        return [dict(item) for item in self._CENTRAL_BANK_SERIES]

    def indicator_label(self, indicator_code: str) -> str:
        return self._WORLD_BANK_INDICATORS.get(indicator_code, indicator_code)

    def fetch_fred_series(
        self,
        *,
        series_id: str,
        days: int,
    ) -> tuple[list[dict[str, float | str]], str]:
        safe_days = max(30, min(days, 3650))
        if _is_truthy(os.getenv("AQ_MACRO_OFFLINE")):
            return self._synthetic_daily_series(key=series_id, days=safe_days), "synthetic"

        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={quote(series_id)}"
        try:
            with httpx.Client(timeout=6.0, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
            rows = self._parse_fred_csv(response.text)
            if rows:
                return rows[-safe_days:], "fred"
        except Exception:
            return self._synthetic_daily_series(key=series_id, days=safe_days), "synthetic"

        return self._synthetic_daily_series(key=series_id, days=safe_days), "synthetic"

    def fetch_world_bank_indicator(
        self,
        *,
        country: str,
        indicator: str,
        years: int,
    ) -> tuple[list[dict[str, float | str]], str]:
        safe_years = max(5, min(years, 60))
        normalized_country = country.strip().upper()
        normalized_indicator = indicator.strip().upper()
        if _is_truthy(os.getenv("AQ_MACRO_OFFLINE")):
            return (
                self._synthetic_yearly_series(
                    key=f"{normalized_country}:{normalized_indicator}",
                    years=safe_years,
                ),
                "synthetic",
            )

        url = (
            "https://api.worldbank.org/v2/country/"
            f"{quote(normalized_country)}/indicator/{quote(normalized_indicator)}"
            "?format=json&per_page=200"
        )
        try:
            with httpx.Client(timeout=8.0, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
            rows = self._parse_world_bank_json(response.json())
            if rows:
                return rows[-safe_years:], "world_bank"
        except Exception:
            return (
                self._synthetic_yearly_series(
                    key=f"{normalized_country}:{normalized_indicator}",
                    years=safe_years,
                ),
                "synthetic",
            )

        return (
            self._synthetic_yearly_series(
                key=f"{normalized_country}:{normalized_indicator}",
                years=safe_years,
            ),
            "synthetic",
        )

    @staticmethod
    def _parse_fred_csv(raw_csv: str) -> list[dict[str, float | str]]:
        reader = csv.DictReader(StringIO(raw_csv))
        rows: list[dict[str, float | str]] = []
        for row in reader:
            date_text = str(row.get("DATE", "")).strip()
            if not date_text:
                continue

            value_raw: str | None = None
            for key, value in row.items():
                if key == "DATE":
                    continue
                value_raw = value
                break

            if value_raw is None:
                continue

            value_text = str(value_raw).strip()
            if not value_text or value_text in {".", "NaN", "null"}:
                continue

            try:
                numeric = float(value_text)
            except ValueError:
                continue

            rows.append({"label": date_text, "value": numeric})

        rows.sort(key=lambda item: str(item["label"]))
        return rows

    @staticmethod
    def _parse_world_bank_json(payload: object) -> list[dict[str, float | str]]:
        if not isinstance(payload, list) or len(payload) < 2:
            return []

        entries = payload[1]
        if not isinstance(entries, list):
            return []

        rows: list[dict[str, float | str]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            year = str(entry.get("date", "")).strip()
            value = entry.get("value")
            if not year or value is None:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            rows.append({"label": year, "value": numeric})

        rows.sort(key=lambda item: int(str(item["label"])))
        return rows

    @staticmethod
    def _synthetic_daily_series(*, key: str, days: int) -> list[dict[str, float | str]]:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        seed = int(digest[:12], 16)
        base = 1.0 + (seed % 600) / 100.0
        trend = ((seed // 11) % 13 - 6) / 500.0
        amplitude = 0.2 + ((seed // 31) % 40) / 100.0
        phase = ((seed // 97) % 360) * math.pi / 180.0
        today = date.today()
        rows: list[dict[str, float | str]] = []

        for idx in range(days):
            step = idx + 1
            seasonal = math.sin(step / 16.0 + phase) * amplitude
            value = max(0.01, base + (trend * step) + seasonal)
            label = (today - timedelta(days=(days - step))).isoformat()
            rows.append({"label": label, "value": round(value, 4)})
        return rows

    @staticmethod
    def _synthetic_yearly_series(*, key: str, years: int) -> list[dict[str, float | str]]:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        seed = int(digest[:12], 16)
        base = -1.0 + (seed % 1200) / 100.0
        trend = ((seed // 7) % 15 - 7) / 20.0
        amplitude = 0.4 + ((seed // 53) % 90) / 100.0
        phase = ((seed // 79) % 360) * math.pi / 180.0
        current_year = date.today().year
        rows: list[dict[str, float | str]] = []

        for idx in range(years):
            year = current_year - (years - idx - 1)
            step = idx + 1
            value = base + (trend * step / max(years, 1)) + (math.sin(step / 3.0 + phase) * amplitude)
            rows.append({"label": str(year), "value": round(value, 3)})
        return rows


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
