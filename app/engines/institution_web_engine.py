from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser
import ipaddress
import os
import re
import socket
from urllib.parse import urlparse, urlunparse

import httpx

from app.models import (
    InstitutionPageFinding,
    InstitutionPageRequest,
    InstitutionReportRequest,
    InstitutionReportResponse,
)

_WHITESPACE_RE = re.compile(r"\s+")
_BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "::1",
}


class InstitutionWebEngine:
    def __init__(self) -> None:
        self._timeout = httpx.Timeout(10.0, connect=4.0, read=8.0)
        self._max_body_chars = 180_000

    def build_report(self, payload: InstitutionReportRequest) -> InstitutionReportResponse:
        global_terms = _dedupe_terms(payload.global_focus_terms)
        findings: list[InstitutionPageFinding] = []

        for page in payload.pages:
            finding = self._inspect_page(page=page, global_terms=global_terms)
            findings.append(finding)

        return InstitutionReportResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            page_count=len(findings),
            requested_terms=global_terms,
            executive_summary=self._build_executive_summary(findings=findings, requested_terms=global_terms),
            pages=findings,
        )

    def _inspect_page(
        self,
        *,
        page: InstitutionPageRequest,
        global_terms: list[str],
    ) -> InstitutionPageFinding:
        requested_terms = _dedupe_terms(global_terms + page.focus_terms)
        raw_url = page.url.strip()
        domain_hint = _domain_from_url(raw_url)

        try:
            normalized_url = self._validate_url(raw_url)
            source_domain = _domain_from_url(normalized_url)
            html_text, fetched_at = self._fetch_html(url=normalized_url, requested_terms=requested_terms)
            title, text_content, table_rows = self._extract_content(html_text)
            matched_terms, matched_snippets = self._match_terms(
                text_content=text_content,
                title=title,
                terms=requested_terms,
            )

            summary = self._build_page_summary(
                word_count=len(text_content.split()),
                table_rows_count=len(table_rows),
                matched_terms=matched_terms,
            )
            return InstitutionPageFinding(
                url=normalized_url,
                source_domain=source_domain,
                status="ok",
                title=title or None,
                summary=summary,
                matched_terms=matched_terms,
                matched_snippets=matched_snippets,
                extracted_table_rows=table_rows,
                fetched_at=fetched_at,
            )
        except Exception as exc:
            return InstitutionPageFinding(
                url=raw_url,
                source_domain=domain_hint,
                status="error",
                summary="Page could not be analyzed; verify URL accessibility and format.",
                error=_compact_text(str(exc), max_chars=220),
            )

    def _fetch_html(self, *, url: str, requested_terms: list[str]) -> tuple[str, str]:
        fetched_at = datetime.now(timezone.utc).isoformat()
        if _is_truthy(os.getenv("AQ_WEB_OFFLINE")):
            return self._synthetic_html(url=url, requested_terms=requested_terms), fetched_at

        with httpx.Client(
            timeout=self._timeout,
            follow_redirects=True,
            headers={"User-Agent": "AlphaQuantum/1.0 (+public-source-intel)"},
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            body = response.text

        if len(body) > self._max_body_chars:
            body = body[: self._max_body_chars]
        return body, fetched_at

    def _validate_url(self, raw_url: str) -> str:
        candidate = raw_url.strip()
        if not candidate:
            raise ValueError("URL is empty")

        if "://" not in candidate:
            candidate = f"https://{candidate}"

        parsed = urlparse(candidate)
        if parsed.scheme.lower() not in {"http", "https"}:
            raise ValueError("Only HTTP/HTTPS URLs are allowed")

        host = (parsed.hostname or "").strip().lower()
        if not host:
            raise ValueError("URL host is missing")

        self._validate_host(host)

        clean_path = parsed.path or "/"
        return urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc,
                clean_path,
                parsed.params,
                parsed.query,
                "",
            )
        )

    def _validate_host(self, host: str) -> None:
        if host in _BLOCKED_HOSTNAMES or host.endswith(".local") or host.endswith(".internal"):
            raise ValueError("Private or local hosts are not allowed")

        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = None

        if ip is not None:
            if not _is_public_ip(ip):
                raise ValueError("Private or local hosts are not allowed")
            return

        try:
            addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except socket.gaierror:
            return

        for item in addresses:
            resolved = item[4][0]
            try:
                ip = ipaddress.ip_address(resolved)
            except ValueError:
                continue
            if not _is_public_ip(ip):
                raise ValueError("Private or local hosts are not allowed")

    def _extract_content(self, html_text: str) -> tuple[str, str, list[list[str]]]:
        parser = _HTMLExtractor(max_chars=self._max_body_chars)
        parser.feed(html_text)
        parser.close()
        return parser.title, parser.text_content, parser.table_rows

    @staticmethod
    def _match_terms(*, text_content: str, title: str, terms: list[str]) -> tuple[list[str], list[str]]:
        if not terms:
            return [], []

        haystack = f"{title}\n{text_content}".lower()
        matched_terms: list[str] = []
        for term in terms:
            if term.lower() in haystack:
                matched_terms.append(term)

        snippets = _find_snippets(text=text_content, terms=matched_terms, limit=8)
        return matched_terms, snippets

    @staticmethod
    def _build_page_summary(
        *,
        word_count: int,
        table_rows_count: int,
        matched_terms: list[str],
    ) -> str:
        if matched_terms:
            return (
                f"Matched {len(matched_terms)} focus term(s): "
                f"{', '.join(matched_terms[:6])}. "
                f"Parsed {word_count} words and {table_rows_count} table row(s)."
            )

        return (
            f"Page parsed successfully with {word_count} words and "
            f"{table_rows_count} table row(s); no focus-term match detected."
        )

    @staticmethod
    def _build_executive_summary(
        *,
        findings: list[InstitutionPageFinding],
        requested_terms: list[str],
    ) -> str:
        total = len(findings)
        success = sum(1 for item in findings if item.status == "ok")
        failed = total - success
        matched = sum(1 for item in findings if item.matched_terms)
        domains = sorted({item.source_domain for item in findings if item.source_domain})
        domain_text = ", ".join(domains[:6]) if domains else "n/a"
        terms_text = ", ".join(requested_terms[:8]) if requested_terms else "none"

        return (
            f"Scanned {total} page(s) across {len(domains)} domain(s) [{domain_text}]. "
            f"Successful analyses: {success}, failed: {failed}. "
            f"Focus terms: {terms_text}. "
            f"Matched pages: {matched}/{success if success else total}."
        )

    @staticmethod
    def _synthetic_html(*, url: str, requested_terms: list[str]) -> str:
        domain = _domain_from_url(url)
        joined_terms = ", ".join(requested_terms) if requested_terms else "policy, inflation, budget"
        return (
            "<html><head><title>Offline Public Bulletin</title></head><body>"
            f"<h1>{escape(domain)} Official Bulletin</h1>"
            "<p>This offline snapshot contains policy rate updates, inflation guidance, "
            f"fiscal reports, and transparency notes. Requested focus terms: {escape(joined_terms)}.</p>"
            "<table>"
            "<tr><th>Indicator</th><th>Latest</th></tr>"
            "<tr><td>Policy Rate</td><td>42.50</td></tr>"
            "<tr><td>Inflation</td><td>8.20</td></tr>"
            "<tr><td>Budget Balance</td><td>-1.40</td></tr>"
            "</table>"
            "</body></html>"
        )


class _HTMLExtractor(HTMLParser):
    def __init__(self, *, max_chars: int) -> None:
        super().__init__(convert_charrefs=True)
        self._max_chars = max_chars
        self._text_chars = 0
        self._ignored_depth = 0
        self._in_title = False
        self._current_cell_parts: list[str] | None = None
        self._current_row: list[str] | None = None

        self._title_parts: list[str] = []
        self._text_parts: list[str] = []
        self._table_rows: list[list[str]] = []

    @property
    def title(self) -> str:
        return _compact_text(" ".join(self._title_parts), max_chars=240)

    @property
    def text_content(self) -> str:
        return _compact_text(" ".join(self._text_parts), max_chars=self._max_chars)

    @property
    def table_rows(self) -> list[list[str]]:
        return [row[:] for row in self._table_rows]

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"}:
            self._ignored_depth += 1
            return

        if lowered == "title":
            self._in_title = True
            return

        if lowered == "tr":
            self._current_row = []
            return

        if lowered in {"td", "th"}:
            self._current_cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)
            return

        if lowered == "title":
            self._in_title = False
            return

        if lowered in {"td", "th"}:
            if self._current_row is not None and self._current_cell_parts is not None:
                text = _compact_text(" ".join(self._current_cell_parts), max_chars=120)
                if text:
                    self._current_row.append(text)
            self._current_cell_parts = None
            return

        if lowered == "tr":
            if self._current_row and len(self._table_rows) < 15:
                self._table_rows.append(self._current_row[:8])
            self._current_row = None

    def handle_data(self, data: str) -> None:
        if self._ignored_depth > 0:
            return
        text = _compact_text(data, max_chars=500)
        if not text:
            return

        if self._in_title:
            self._title_parts.append(text)

        if self._current_cell_parts is not None:
            self._current_cell_parts.append(text)

        if self._text_chars >= self._max_chars:
            return
        self._text_parts.append(text)
        self._text_chars += len(text)


def _find_snippets(*, text: str, terms: list[str], limit: int) -> list[str]:
    snippets: list[str] = []
    lowered = text.lower()
    seen: set[str] = set()

    for term in terms:
        if len(snippets) >= limit:
            break
        token = term.lower()
        index = lowered.find(token)
        if index < 0:
            continue
        start = max(0, index - 80)
        end = min(len(text), index + len(token) + 120)
        snippet = _compact_text(text[start:end], max_chars=220)
        if snippet and snippet not in seen:
            seen.add(snippet)
            snippets.append(snippet)

    return snippets


def _compact_text(raw_text: str, *, max_chars: int) -> str:
    compact = _WHITESPACE_RE.sub(" ", raw_text).strip()
    if len(compact) <= max_chars:
        return compact
    return f"{compact[: max_chars - 1]}…"


def _dedupe_terms(terms: list[str]) -> list[str]:
    resolved: list[str] = []
    seen: set[str] = set()
    for item in terms:
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        resolved.append(normalized)
    return resolved


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return (parsed.hostname or parsed.netloc or "unknown").lower() or "unknown"


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.is_private:
        return False
    if ip.is_loopback:
        return False
    if ip.is_link_local:
        return False
    if ip.is_multicast:
        return False
    if ip.is_reserved:
        return False
    if ip.is_unspecified:
        return False
    return True
