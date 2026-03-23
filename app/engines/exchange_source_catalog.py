from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class ExchangeSourceProfile:
    region: str
    exchange: str
    url: str
    focus_terms: tuple[str, ...]
    seed_symbols: tuple[str, ...]


_DEFAULT_REGIONS = ("TR", "EU", "GLOBAL")

_CATALOG: tuple[ExchangeSourceProfile, ...] = (
    ExchangeSourceProfile(
        region="TR",
        exchange="Borsa Istanbul",
        url="https://www.borsaistanbul.com/en",
        focus_terms=("bist", "index", "equity", "volume", "hisse", "islem"),
        seed_symbols=("XU100.IS", "XU030.IS", "THYAO.IS", "GARAN.IS", "AKBNK.IS", "SISE.IS"),
    ),
    ExchangeSourceProfile(
        region="TR",
        exchange="Investing TR BIST",
        url="https://tr.investing.com/indices/ise-100",
        focus_terms=("bist", "xu100", "hacim", "fiyat", "degisim"),
        seed_symbols=("XU100.IS", "XU030.IS", "KCHOL.IS", "TUPRS.IS"),
    ),
    ExchangeSourceProfile(
        region="EU",
        exchange="Euronext",
        url="https://live.euronext.com/en/markets/equity-indices",
        focus_terms=("index", "equity", "market cap", "turnover"),
        seed_symbols=("PX1.PA", "AEX.NL", "BFX.BR", "PSI20.PT"),
    ),
    ExchangeSourceProfile(
        region="EU",
        exchange="London Stock Exchange",
        url="https://www.londonstockexchange.com/indices",
        focus_terms=("ftse", "index", "market activity", "turnover"),
        seed_symbols=("UKX", "FTSE.UK", "HSBA.UK", "BARC.UK"),
    ),
    ExchangeSourceProfile(
        region="EU",
        exchange="Deutsche Boerse",
        url="https://www.deutsche-boerse.com/dbg-en/markets-indices",
        focus_terms=("dax", "xetra", "index", "trading volume"),
        seed_symbols=("DAX.DE", "MDAX.DE", "SX5E.EU", "SAP.DE"),
    ),
    ExchangeSourceProfile(
        region="EU",
        exchange="SIX Swiss Exchange",
        url="https://www.six-group.com/en/market-data/indices.html",
        focus_terms=("smi", "index", "quote", "volume"),
        seed_symbols=("SMI.SW", "NOVN.SW", "NESN.SW"),
    ),
    ExchangeSourceProfile(
        region="EU",
        exchange="Borsa Italiana",
        url="https://www.borsaitaliana.it/borsa/indici/listino.html",
        focus_terms=("ftse mib", "indice", "azioni", "volumi"),
        seed_symbols=("FTMIB.MI", "ENEL.MI", "UCG.MI"),
    ),
    ExchangeSourceProfile(
        region="EU",
        exchange="BME Spain",
        url="https://www.bolsasymercados.es/esp/Indices/Resumen",
        focus_terms=("ibex", "indice", "mercado", "volumen"),
        seed_symbols=("IBEX.MC", "SAN.MC", "ITX.MC"),
    ),
    ExchangeSourceProfile(
        region="GLOBAL",
        exchange="NASDAQ",
        url="https://www.nasdaq.com/market-activity/stocks",
        focus_terms=("stocks", "gainers", "losers", "volume"),
        seed_symbols=("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"),
    ),
    ExchangeSourceProfile(
        region="GLOBAL",
        exchange="NYSE",
        url="https://www.nyse.com/index",
        focus_terms=("index", "market activity", "equities", "volume"),
        seed_symbols=("SPY", "DIA", "JPM", "BAC"),
    ),
    ExchangeSourceProfile(
        region="GLOBAL",
        exchange="S&P Dow Jones Indices",
        url="https://www.spglobal.com/spdji/en/",
        focus_terms=("spx", "index", "benchmark", "returns"),
        seed_symbols=("SPX", "DJI", "NDX"),
    ),
    ExchangeSourceProfile(
        region="GLOBAL",
        exchange="CME Group",
        url="https://www.cmegroup.com/markets.html",
        focus_terms=("futures", "open interest", "volume", "contracts"),
        seed_symbols=("ES.F", "NQ.F", "CL.F", "GC.F"),
    ),
    ExchangeSourceProfile(
        region="GLOBAL",
        exchange="Japan Exchange Group",
        url="https://www.jpx.co.jp/english/markets/indices/",
        focus_terms=("nikkei", "topix", "index", "turnover"),
        seed_symbols=("N225.JP", "TOPX.JP", "7203.JP"),
    ),
    ExchangeSourceProfile(
        region="GLOBAL",
        exchange="Hong Kong Exchange",
        url="https://www.hkex.com.hk/Market-Data/Securities-Prices/Equities",
        focus_terms=("hang seng", "equities", "volume", "market data"),
        seed_symbols=("HSI.HK", "0700.HK", "9988.HK"),
    ),
    ExchangeSourceProfile(
        region="GLOBAL",
        exchange="Shanghai Stock Exchange",
        url="https://english.sse.com.cn/markets/indices/",
        focus_terms=("sse", "index", "market", "trading"),
        seed_symbols=("SSEI.CN", "600519.CN", "601318.CN"),
    ),
    ExchangeSourceProfile(
        region="GLOBAL",
        exchange="TMX Group",
        url="https://www.tmx.com/",
        focus_terms=("tsx", "indices", "equities", "market data"),
        seed_symbols=("TSX.CA", "SHOP.CA", "RY.CA"),
    ),
    ExchangeSourceProfile(
        region="GLOBAL",
        exchange="ASX",
        url="https://www.asx.com.au/markets/trade-our-cash-market",
        focus_terms=("asx", "market", "shares", "indices"),
        seed_symbols=("XJO.AU", "BHP.AX", "CBA.AX"),
    ),
    ExchangeSourceProfile(
        region="GLOBAL",
        exchange="B3 Brazil",
        url="https://www.b3.com.br/en_us/market-data-and-indices/indices/",
        focus_terms=("ibovespa", "indices", "acoes", "volume"),
        seed_symbols=("IBOV.BR", "PETR4.BR", "VALE3.BR"),
    ),
    ExchangeSourceProfile(
        region="GLOBAL",
        exchange="NSE India",
        url="https://www.nseindia.com/market-data/live-equity-market",
        focus_terms=("nifty", "equity", "volume", "index"),
        seed_symbols=("NIFTY.IN", "RELIANCE.IN", "HDFCBANK.IN"),
    ),
)


def list_exchange_sources(*, regions: list[str] | None = None, limit: int = 20) -> list[ExchangeSourceProfile]:
    normalized_regions = _normalize_regions(regions)
    safe_limit = max(1, min(limit, 50))
    output: list[ExchangeSourceProfile] = []
    for region in normalized_regions:
        for profile in _CATALOG:
            if profile.region != region:
                continue
            output.append(profile)
            if len(output) >= safe_limit:
                return output
    return output


def build_default_market_pages(*, regions: list[str] | None = None, limit: int = 20) -> list[dict[str, object]]:
    return [
        {
            "url": profile.url,
            "focus_terms": list(profile.focus_terms),
        }
        for profile in list_exchange_sources(regions=regions, limit=limit)
    ]


def profile_for_domain(domain: str) -> ExchangeSourceProfile | None:
    normalized = _normalize_domain(domain)
    if not normalized:
        return None

    for profile in _CATALOG:
        profile_domain = _normalize_domain(urlparse(profile.url).hostname or "")
        if not profile_domain:
            continue
        if normalized == profile_domain or normalized.endswith(f".{profile_domain}"):
            return profile
    return None


def seed_symbols_for_domain(domain: str) -> list[str]:
    profile = profile_for_domain(domain)
    if profile is None:
        return []
    return list(profile.seed_symbols)


def _normalize_regions(regions: list[str] | None) -> list[str]:
    if not regions:
        return list(_DEFAULT_REGIONS)

    seen: set[str] = set()
    normalized: list[str] = []
    for item in regions:
        value = item.strip().upper()
        if not value or value in seen:
            continue
        if value not in _DEFAULT_REGIONS:
            continue
        seen.add(value)
        normalized.append(value)

    return normalized or list(_DEFAULT_REGIONS)


def _normalize_domain(domain: str) -> str:
    lowered = domain.strip().lower()
    if lowered.startswith("www."):
        return lowered[4:]
    return lowered
