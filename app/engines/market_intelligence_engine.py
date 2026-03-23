from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import re

from app.engines.exchange_source_catalog import (
    build_default_market_pages,
    list_exchange_sources,
    profile_for_domain,
    seed_symbols_for_domain,
)
from app.engines.institution_web_engine import InstitutionWebEngine
from app.engines.market_data_engine import MarketDataEngine
from app.models import (
    InstitutionPageRequest,
    InstitutionReportRequest,
    MarketAnalysisResponse,
    MarketIntelligenceRequest,
    MarketIntelligenceResponse,
    MarketPageInsight,
    MarketPageRequest,
    MarketRecommendation,
    MarketSourceCatalogResponse,
    MarketSourceProfile,
)

_SYMBOL_RE = re.compile(r"\b[A-Z]{2,6}(?:\.[A-Z]{1,4})?\b")
_NUMBER_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?%?")
_NOISE_SYMBOLS = {
    "HTTP",
    "HTTPS",
    "HTML",
    "USD",
    "EUR",
    "TRY",
    "DATE",
    "OPEN",
    "HIGH",
    "LOW",
    "CLOSE",
    "VOLUME",
    "THE",
    "AND",
    "FOR",
    "WITH",
    "FROM",
}
_TABLE_HEADER_HINTS = {
    "symbol",
    "ticker",
    "code",
    "kod",
    "hisse",
    "instrument",
    "share",
    "stock",
    "isin",
}


class MarketIntelligenceEngine:
    def __init__(
        self,
        market_engine: MarketDataEngine,
        institution_engine: InstitutionWebEngine,
    ) -> None:
        self._market_engine = market_engine
        self._institution_engine = institution_engine

    def build_report(self, payload: MarketIntelligenceRequest) -> MarketIntelligenceResponse:
        resolved_pages = self._resolve_pages(payload)
        if not resolved_pages:
            raise ValueError(
                "At least one page is required. Provide pages[] or enable include_default_exchange_pages."
            )

        institution_payload = InstitutionReportRequest(
            pages=[
                InstitutionPageRequest(url=item.url, focus_terms=item.focus_terms)
                for item in resolved_pages
            ],
            global_focus_terms=["price", "index", "market", "volume"],
        )
        inspected = self._institution_engine.build_report(institution_payload)

        symbol_counter: Counter[str] = Counter()
        page_insights: list[MarketPageInsight] = []
        for page in inspected.pages:
            if page.status != "ok":
                page_insights.append(
                    MarketPageInsight(
                        url=page.url,
                        source_domain=page.source_domain,
                        region=None,
                        exchange=None,
                        status="error",
                        title=page.title,
                        table_rows_count=0,
                        extracted_symbols=[],
                        extracted_numbers=[],
                        highlights=[],
                        error=page.error,
                    )
                )
                continue

            source_profile = profile_for_domain(page.source_domain)
            extracted_symbols = self._extract_symbols_from_page(page)
            default_symbols = seed_symbols_for_domain(page.source_domain)
            extracted_symbols = sorted(set(extracted_symbols + default_symbols))
            extracted_numbers = self._extract_numbers_from_page(page)
            for symbol in extracted_symbols:
                symbol_counter[symbol] += 1
            for symbol in default_symbols:
                symbol_counter[symbol] += 2

            page_insights.append(
                MarketPageInsight(
                    url=page.url,
                    source_domain=page.source_domain,
                    region=source_profile.region if source_profile else None,
                    exchange=source_profile.exchange if source_profile else None,
                    status="ok",
                    title=page.title,
                    table_rows_count=len(page.extracted_table_rows),
                    extracted_symbols=extracted_symbols,
                    extracted_numbers=extracted_numbers,
                    highlights=page.matched_snippets[:6],
                )
            )

        for symbol in payload.focus_symbols:
            normalized = _normalize_symbol(symbol)
            if normalized:
                symbol_counter[normalized] += 10

        selected_symbols = [item for item, _ in symbol_counter.most_common(payload.max_symbols)]
        analyses: list[MarketAnalysisResponse] = []
        for symbol in selected_symbols:
            analyses.append(
                self._market_engine.analyze_symbol(
                    symbol=symbol,
                    timeframe=payload.timeframe,
                    days=payload.days,
                    refresh=payload.refresh,
                )
            )

        recommendations = [self._to_recommendation(analysis) for analysis in analyses]
        recommendations.sort(key=lambda item: (_recommendation_priority(item.signal), item.confidence), reverse=True)
        executive_summary = self._build_summary(
            page_count=len(page_insights),
            analyzed_symbol_count=len(selected_symbols),
            recommendations=recommendations,
        )

        return MarketIntelligenceResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            executive_summary=executive_summary,
            pages=page_insights,
            analyzed_symbols=selected_symbols,
            recommendations=recommendations,
            disclaimer=(
                "This output is a decision-support artifact and does not guarantee profit. "
                "Use risk limits and obtain professional financial advice before acting."
            ),
        )

    def list_sources(self, *, regions: list[str], limit: int = 20) -> MarketSourceCatalogResponse:
        sources = list_exchange_sources(regions=regions, limit=limit)
        normalized_regions = sorted({item.region for item in sources})
        return MarketSourceCatalogResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_sources=len(sources),
            regions=normalized_regions,
            sources=[
                MarketSourceProfile(
                    region=item.region,
                    exchange=item.exchange,
                    url=item.url,
                    focus_terms=list(item.focus_terms),
                    seed_symbols=list(item.seed_symbols),
                )
                for item in sources
            ],
        )

    @staticmethod
    def _resolve_pages(payload: MarketIntelligenceRequest) -> list[MarketPageRequest]:
        max_pages = max(1, min(payload.max_pages, 20))
        merged_pages: list[MarketPageRequest] = []
        seen_urls: set[str] = set()

        def _append_page(page: MarketPageRequest) -> None:
            normalized_url = page.url.strip().lower()
            if not normalized_url or normalized_url in seen_urls:
                return
            if len(merged_pages) >= max_pages:
                return
            seen_urls.add(normalized_url)
            merged_pages.append(page)

        for page in payload.pages:
            _append_page(page)

        if payload.include_default_exchange_pages:
            for item in build_default_market_pages(regions=payload.regions, limit=max_pages):
                _append_page(
                    MarketPageRequest(
                        url=str(item["url"]),
                        focus_terms=[str(term) for term in item["focus_terms"]],
                    )
                )

        return merged_pages

    @staticmethod
    def _extract_symbols_from_page(page) -> list[str]:
        pool: list[str] = []
        if page.title:
            pool.append(page.title)
        pool.append(page.summary)
        pool.extend(page.matched_snippets)
        for row in page.extracted_table_rows:
            pool.append(" ".join(row))

        candidates: set[str] = set()
        candidates.update(_extract_symbols_from_rows(page.extracted_table_rows))
        for blob in pool:
            for token in _SYMBOL_RE.findall(blob.upper()):
                normalized = _normalize_symbol(token)
                if not normalized or normalized in _NOISE_SYMBOLS:
                    continue
                candidates.add(normalized)
        return sorted(candidates)

    @staticmethod
    def _extract_numbers_from_page(page) -> list[str]:
        pool: list[str] = []
        pool.append(page.summary)
        pool.extend(page.matched_snippets)
        for row in page.extracted_table_rows:
            pool.append(" ".join(row))
        values: list[str] = []
        seen: set[str] = set()
        for blob in pool:
            for item in _NUMBER_RE.findall(blob):
                normalized = item.replace(",", ".")
                if normalized in seen:
                    continue
                seen.add(normalized)
                values.append(normalized)
                if len(values) >= 15:
                    return values
        return values

    @staticmethod
    def _to_recommendation(analysis: MarketAnalysisResponse) -> MarketRecommendation:
        risk_level = "MEDIUM"
        action = "Monitor position and wait for stronger confirmation."
        if analysis.signal == "SELL":
            action = "Reduce exposure, review hedge options, and protect downside with strict risk limits."
            risk_level = "HIGH"
        elif analysis.signal == "BUY":
            action = "Consider staged entry with stop-loss policy and position sizing discipline."
            risk_level = "MEDIUM"
        elif analysis.signal == "HOLD":
            action = "Keep position neutral and watch breakout / breakdown levels."
            risk_level = "LOW" if analysis.confidence < 0.6 else "MEDIUM"

        if analysis.confidence >= 0.85 and analysis.signal in {"BUY", "SELL"}:
            risk_level = "HIGH"

        return MarketRecommendation(
            symbol=analysis.symbol,
            signal=analysis.signal,
            confidence=analysis.confidence,
            risk_level=risk_level,
            rationale=analysis.rationale,
            suggested_action=action,
        )

    @staticmethod
    def _build_summary(
        *,
        page_count: int,
        analyzed_symbol_count: int,
        recommendations: list[MarketRecommendation],
    ) -> str:
        buy_count = sum(1 for item in recommendations if item.signal == "BUY")
        sell_count = sum(1 for item in recommendations if item.signal == "SELL")
        hold_count = sum(1 for item in recommendations if item.signal == "HOLD")
        return (
            f"Analyzed {page_count} market page(s) and produced signals for {analyzed_symbol_count} symbol(s). "
            f"Signal distribution: BUY={buy_count}, SELL={sell_count}, HOLD={hold_count}. "
            "Use these insights with portfolio risk controls and institution-specific compliance checks."
        )


def _normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not normalized:
        return ""
    return normalized


def _recommendation_priority(signal: str) -> int:
    if signal == "SELL":
        return 3
    if signal == "BUY":
        return 2
    return 1


def _extract_symbols_from_rows(rows: list[list[str]]) -> set[str]:
    if not rows:
        return set()

    header = [cell.strip().lower() for cell in rows[0]]
    symbol_indexes = [
        idx
        for idx, column in enumerate(header)
        if any(hint in column for hint in _TABLE_HEADER_HINTS)
    ]
    if not symbol_indexes:
        symbol_indexes = [0]

    candidates: set[str] = set()
    for row in rows[1:40]:
        for idx in symbol_indexes:
            if idx >= len(row):
                continue
            cell = row[idx]
            for token in _SYMBOL_RE.findall(cell.upper()):
                normalized = _normalize_symbol(token)
                if not normalized or normalized in _NOISE_SYMBOLS:
                    continue
                candidates.add(normalized)
    return candidates
