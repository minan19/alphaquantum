"""A5.9: Market intelligence router (extracted from app/api.py).

11 endpoint covering 4 related "market & macro intelligence" domains:

Market core (5, tags=["market"]):
- GET  /api/v1/market/ohlcv              (single symbol time series)
- GET  /api/v1/market/analysis           (single symbol signal)
- GET  /api/v1/market/signals            (multi-symbol comparator)
- POST /api/v1/market/refresh            (force-refresh symbol cache)
- POST /api/v1/market/intelligence       (composite intelligence report)

Market sources + backtest (2, tags=["market"]):
- GET  /api/v1/market/sources            (curated source catalog)
- GET  /api/v1/market/backtest           (signal strategy backtest)

Global macro intel (3, tags=["global_intel"]):
- GET  /api/v1/global/central-banks      (CB rate panels)
- GET  /api/v1/global/world-bank         (WB indicator panels)
- GET  /api/v1/global/report             (professional macro report)

Public institutions (1, tags=["public_intel"]):
- POST /api/v1/public-institutions/report

RBAC:
- read_market, refresh_market         — market endpoints
- read_global_intel                    — global endpoints
- read_public_sources                  — public_intel + market/intelligence composite

`_parse_symbols_csv` helper (CSV → deduped uppercase list) bu router'a özel,
api.py'dan alındı — kullanım yalnızca market/global tarafında.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.models import (
    CentralBankPanelResponse,
    InstitutionReportRequest,
    InstitutionReportResponse,
    MarketAnalysisResponse,
    MarketBacktestResponse,
    MarketIntelligenceRequest,
    MarketIntelligenceResponse,
    MarketOHLCVResponse,
    MarketRefreshRequest,
    MarketRefreshResponse,
    MarketSignalsResponse,
    MarketSourceCatalogResponse,
    ProfessionalReportResponse,
    UserProfile,
    WorldBankPanelResponse,
)
from app.routers._deps import (
    _global_engine,
    _institution_engine,
    _market_engine,
    _market_intelligence_engine,
    _value_error_to_http,
)
from app.security import require_permissions


router = APIRouter()


# ── Helper: CSV symbols/codes parse + dedupe ─────────────────────────────────


def _parse_symbols_csv(raw: str) -> list[str]:
    """Convert a CSV string into a deduped list of uppercased non-empty items.

    Used for symbol lists, country codes, indicator codes — anywhere clients
    submit a comma-separated value. Empty/whitespace items are skipped.
    """
    symbols: list[str] = []
    seen: set[str] = set()
    for item in raw.split(","):
        normalized = item.strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        symbols.append(normalized)
    return symbols


# ── Market core ──────────────────────────────────────────────────────────────


@router.get(
    "/api/v1/market/ohlcv",
    response_model=MarketOHLCVResponse,
    tags=["market"],
)
def market_ohlcv(
    request: Request,
    symbol: str = Query(default="AAPL", min_length=1),
    timeframe: str = Query(default="1d"),
    days: int = Query(default=180, ge=20, le=3650),
    refresh: bool = Query(default=False),
    user: UserProfile = Depends(require_permissions("read_market")),
) -> MarketOHLCVResponse:
    del user
    try:
        return _market_engine(request).get_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            days=days,
            refresh=refresh,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get(
    "/api/v1/market/analysis",
    response_model=MarketAnalysisResponse,
    tags=["market"],
)
def market_analysis(
    request: Request,
    symbol: str = Query(default="AAPL", min_length=1),
    timeframe: str = Query(default="1d"),
    days: int = Query(default=180, ge=20, le=3650),
    refresh: bool = Query(default=False),
    user: UserProfile = Depends(require_permissions("read_market")),
) -> MarketAnalysisResponse:
    del user
    try:
        return _market_engine(request).analyze_symbol(
            symbol=symbol,
            timeframe=timeframe,
            days=days,
            refresh=refresh,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.get(
    "/api/v1/market/signals",
    response_model=MarketSignalsResponse,
    tags=["market"],
)
def market_signals(
    request: Request,
    symbols: str = Query(default="AAPL,MSFT,NVDA,TSLA"),
    timeframe: str = Query(default="1d"),
    days: int = Query(default=180, ge=20, le=3650),
    refresh: bool = Query(default=False),
    user: UserProfile = Depends(require_permissions("read_market")),
) -> MarketSignalsResponse:
    del user
    parsed_symbols = _parse_symbols_csv(symbols)
    if not parsed_symbols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="symbols parameter is empty",
        )
    try:
        return _market_engine(request).analyze_symbols(
            symbols=parsed_symbols,
            timeframe=timeframe,
            days=days,
            refresh=refresh,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


@router.post(
    "/api/v1/market/refresh",
    response_model=MarketRefreshResponse,
    tags=["market"],
)
def market_refresh(
    payload: MarketRefreshRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("refresh_market")),
) -> MarketRefreshResponse:
    del user
    symbols = payload.symbols or ["AAPL", "MSFT", "NVDA", "TSLA"]
    try:
        refreshed = _market_engine(request).refresh_symbols(
            symbols=symbols,
            timeframe=payload.timeframe,
            days=payload.days,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc

    return MarketRefreshResponse(
        refreshed_count=len(refreshed),
        symbols=refreshed,
    )


@router.post(
    "/api/v1/market/intelligence",
    response_model=MarketIntelligenceResponse,
    tags=["market"],
)
def market_intelligence_report(
    payload: MarketIntelligenceRequest,
    request: Request,
    user: UserProfile = Depends(
        require_permissions("read_market", "read_public_sources")
    ),
) -> MarketIntelligenceResponse:
    del user
    try:
        return _market_intelligence_engine(request).build_report(payload)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


# ── Market sources + backtest ────────────────────────────────────────────────


@router.get(
    "/api/v1/market/sources",
    response_model=MarketSourceCatalogResponse,
    tags=["market"],
)
def market_sources(
    request: Request,
    regions: str = Query(default="TR,EU,GLOBAL"),
    limit: int = Query(default=20, ge=1, le=50),
    user: UserProfile = Depends(require_permissions("read_market")),
) -> MarketSourceCatalogResponse:
    del user
    return _market_intelligence_engine(request).list_sources(
        regions=_parse_symbols_csv(regions),
        limit=limit,
    )


@router.get(
    "/api/v1/market/backtest",
    response_model=MarketBacktestResponse,
    tags=["market"],
)
def market_backtest(
    request: Request,
    symbol: str = Query(default="AAPL", min_length=1),
    timeframe: str = Query(default="1d"),
    days: int = Query(default=360, ge=80, le=3650),
    lookahead_days: int = Query(default=5, ge=1, le=30),
    hold_band: float = Query(default=0.01, ge=0, le=0.2),
    refresh: bool = Query(default=False),
    user: UserProfile = Depends(require_permissions("read_market")),
) -> MarketBacktestResponse:
    del user
    try:
        return _market_engine(request).backtest_signal_strategy(
            symbol=symbol,
            timeframe=timeframe,
            days=days,
            lookahead_days=lookahead_days,
            hold_band=hold_band,
            refresh=refresh,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc


# ── Global macro intelligence ────────────────────────────────────────────────


@router.get(
    "/api/v1/global/central-banks",
    response_model=CentralBankPanelResponse,
    tags=["global_intel"],
)
def global_central_banks(
    request: Request,
    days: int = Query(default=720, ge=90, le=3650),
    user: UserProfile = Depends(require_permissions("read_global_intel")),
) -> CentralBankPanelResponse:
    del user
    return _global_engine(request).central_bank_panel(days=days)


@router.get(
    "/api/v1/global/world-bank",
    response_model=WorldBankPanelResponse,
    tags=["global_intel"],
)
def global_world_bank(
    request: Request,
    countries: str = Query(default="USA,TUR,DEU"),
    indicators: str = Query(
        default="FP.CPI.TOTL.ZG,NY.GDP.MKTP.KD.ZG,SL.UEM.TOTL.ZS"
    ),
    years: int = Query(default=20, ge=5, le=60),
    user: UserProfile = Depends(require_permissions("read_global_intel")),
) -> WorldBankPanelResponse:
    del user
    return _global_engine(request).world_bank_panel(
        countries=_parse_symbols_csv(countries),
        indicators=_parse_symbols_csv(indicators),
        years=years,
    )


@router.get(
    "/api/v1/global/report",
    response_model=ProfessionalReportResponse,
    tags=["global_intel"],
)
def global_professional_report(
    request: Request,
    countries: str = Query(default="USA,TUR,DEU"),
    indicators: str = Query(
        default="FP.CPI.TOTL.ZG,NY.GDP.MKTP.KD.ZG,SL.UEM.TOTL.ZS"
    ),
    bank_symbols: str = Query(default="JPM,BAC,HSBC,BNP.PA"),
    index_symbols: str = Query(default="SPX,NDX,DAX,XU100"),
    market_days: int = Query(default=260, ge=60, le=3650),
    macro_days: int = Query(default=720, ge=90, le=3650),
    macro_years: int = Query(default=20, ge=5, le=60),
    refresh_market: bool = Query(default=False),
    user: UserProfile = Depends(require_permissions("read_global_intel")),
) -> ProfessionalReportResponse:
    del user
    return _global_engine(request).build_professional_report(
        countries=_parse_symbols_csv(countries),
        indicators=_parse_symbols_csv(indicators),
        bank_symbols=_parse_symbols_csv(bank_symbols),
        index_symbols=_parse_symbols_csv(index_symbols),
        market_days=market_days,
        macro_days=macro_days,
        macro_years=macro_years,
        refresh_market=refresh_market,
    )


# ── Public institutions ──────────────────────────────────────────────────────


@router.post(
    "/api/v1/public-institutions/report",
    response_model=InstitutionReportResponse,
    tags=["public_intel"],
)
def public_institutions_report(
    payload: InstitutionReportRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_public_sources")),
) -> InstitutionReportResponse:
    del user
    return _institution_engine(request).build_report(payload)
