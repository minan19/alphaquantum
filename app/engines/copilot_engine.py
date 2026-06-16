"""AC1 + M3 + M4.2: CopilotEngine — intent → whitelisted SQL → safe query.

Tenant otoritesi M4.2'de **company_id**'ye taşındı (M3'te company_name idi).
Engine `user.company_scopes` name listesini sunucuda registry'den id listesine
çevirir ve `WHERE company_id IN (...)` enjekte eder. Yazma yolları DB
trigger'ları ile çift-yazma; copilot SELECT-only olduğu için yazma yok.

Katmanlar:
- Tenant izolasyonu: `WHERE company_id IN (...)` (M4.2; M3'teki `company_name`
  yerine). Scope'lar registry üstünden çözülür → bilinmeyen isim hiçbir
  kayıt eşleştirmez (boş scope ile aynı davranış).
- Onay kapısı: `execute=False` → SQL + params döner, çalıştırılmaz.
- Read-only assert: çalıştırma öncesi `sql_guard.assert_select_only`.
- Anomaly scope: anomaly_signals tablosu `company_id`/`company_name`
  taşımaz; scope'lu kullanıcı için reddedilir.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from app.copilot_intent_parser import (
    CopilotIntent,
    CopilotResponse,
    OfflineCopilotParser,
)
from app.engines.sql_guard import ReadOnlyViolation, assert_select_only


# Wildcard scope = full access (holding/admin).
_WILDCARD = "*"


def _is_wildcard(scopes: list[str]) -> bool:
    return _WILDCARD in scopes


def _scope_clause(company_ids: list[int]) -> tuple[str, list[Any]]:
    """`WHERE company_id IN (?, ?, ...)` parçası (clause, params).

    M4.2 otoritesi: id ile filtre. Boş liste → hiçbir kayıt eşleşmez
    (`company_id IN ()` sözdizimi yok — `1=0` döner). Wildcard kontrolü
    çağrı yerinde yapılır; bu fonksiyona wildcard geçmez.
    """
    if not company_ids:
        return "1=0", []
    placeholders = ",".join("?" for _ in company_ids)
    return f"company_id IN ({placeholders})", list(company_ids)


class CopilotEngine:
    """Whitelist-based query execution with tenant scope + consent gate."""

    def __init__(
        self,
        *,
        database_path: str,
        parser: OfflineCopilotParser | None = None,
    ) -> None:
        self._database_path = database_path
        self._parser = parser or OfflineCopilotParser()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._database_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def ask(
        self,
        *,
        query: str,
        company_scopes: list[str] | None = None,
        execute: bool = True,
    ) -> CopilotResponse:
        """Doğal dil sorgu → intent → SQL → (opsiyonel) çalıştırma.

        company_scopes: kullanıcının yetkili olduğu şirket **isimleri**.
        Engine sunucuda registry'den `company_id`'ye çevirir (M4.2 otoritesi).
        `None` veya `["*"]` → wildcard (filtre yok). Aksi → id'lere çözüm.
        Client'tan kabul edilmez. execute=False → onay öncesi preview.
        """
        scopes = company_scopes if company_scopes is not None else [_WILDCARD]
        intent = self._parser.parse(query)
        is_wild = _is_wildcard(scopes)
        # M4.2: name → id sunucuda çözülür. Bilinmeyen isim sessizce
        # düşer (kayıt eşleşmez) — sızıntı imkansız.
        company_ids: list[int] = (
            [] if is_wild else self._resolve_company_ids(scopes)
        )
        return self._dispatch(
            intent, company_ids, is_wildcard=is_wild, execute=execute,
        )

    def _resolve_company_ids(self, scope_names: list[str]) -> list[int]:
        """Scope name listesini companies registry üstünden id listesine
        çevirir. Bilinmeyen isim atlanır (None döndürmez)."""
        names = [n for n in scope_names if n and n != _WILDCARD]
        if not names:
            return []
        placeholders = ",".join("?" for _ in names)
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT id FROM companies WHERE name IN ({placeholders})",
                tuple(names),
            ).fetchall()
            return [int(r["id"]) for r in rows]
        finally:
            conn.close()

    def _dispatch(
        self,
        intent: CopilotIntent,
        company_ids: list[int],
        *,
        is_wildcard: bool,
        execute: bool,
    ) -> CopilotResponse:
        if intent.intent == "unknown":
            return CopilotResponse(
                intent=intent,
                summary_text=(
                    "Soruyu anlayamadım. Örnek: "
                    "'Geçen ay AcmeCo'ya kaç fatura kestik?'"
                ),
                explanation="Intent classification: unknown",
                executed=False,
            )

        builder = _BUILDERS.get(intent.intent)
        if builder is None:
            return CopilotResponse(
                intent=intent,
                summary_text="Bu intent için sorgu hazırlanamadı.",
                explanation=f"Intent: {intent.intent} (no builder)",
                executed=False,
            )

        plan = builder(intent, company_ids, is_wildcard)
        if plan.rejected_reason is not None:
            return CopilotResponse(
                intent=intent,
                summary_text=plan.rejected_reason,
                explanation=f"Intent: {intent.intent} — scope reddi",
                sql_template_used=intent.intent,
                executed=False,
            )

        # Defense-in-depth: çalıştırma öncesi her SQL salt-okunur olmalı.
        assert_select_only(plan.sql)

        sql_template = intent.intent
        explanation = self._explain_intent(intent)

        if not execute:
            # Onay kapısı: yalnız SQL + params göster, çalıştırma.
            return CopilotResponse(
                intent=intent,
                sql_template_used=sql_template,
                sql=plan.sql,
                params=list(plan.params),
                summary_text=(
                    "Aşağıdaki sorgu çalıştırılacak. Onaylamadan "
                    "veri getirilmez."
                ),
                explanation=explanation,
                executed=False,
            )

        results, summary = self._execute_plan(plan, intent)
        return CopilotResponse(
            intent=intent,
            results=results,
            summary_text=summary,
            explanation=explanation,
            sql_template_used=sql_template,
            sql=plan.sql,
            params=list(plan.params),
            executed=True,
        )

    def _execute_plan(
        self,
        plan: "_QueryPlan",
        intent: CopilotIntent,
    ) -> tuple[list[dict[str, Any]], str]:
        if plan.runner == "select":
            rows = self._run_select(plan.sql, plan.params)
            return rows, plan.summary_fmt(len(rows), None)
        if plan.runner == "count":
            row = self._run_scalar(plan.sql, plan.params)
            n = int(row["n"]) if row else 0
            return [{"count": n}], plan.summary_fmt(n, intent)
        if plan.runner == "sum":
            row = self._run_scalar(plan.sql, plan.params)
            total = float(row["total"] or 0) if row else 0.0
            return [{"total": total}], plan.summary_fmt(total, intent)
        if plan.runner == "balance":
            row = self._run_scalar(plan.sql, plan.params)
            if not row:
                return [{"balance": 0}], "Kayıt yok."
            income = float(row["income"] or 0)
            expense = float(row["expense"] or 0)
            balance = income - expense
            return (
                [{"income": income, "expense": expense, "balance": balance}],
                f"Net bakiye: ₺{balance:,.2f} "
                f"(gelir ₺{income:,.0f}, gider ₺{expense:,.0f}).",
            )
        # Unreachable; coverage for static checker.
        return [], ""

    def _run_select(
        self, sql: str, params: list[Any],
    ) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _run_scalar(
        self, sql: str, params: list[Any],
    ) -> sqlite3.Row | None:
        conn = self._connect()
        try:
            row: sqlite3.Row | None = conn.execute(
                sql, tuple(params),
            ).fetchone()
            return row
        finally:
            conn.close()

    @staticmethod
    def _explain_intent(intent: CopilotIntent) -> str:
        parts: list[str] = [f"Intent: {intent.intent}"]
        if intent.entity_name:
            parts.append(f"entity={intent.entity_name}")
        if intent.time_window_days:
            parts.append(f"window={intent.time_window_days}g")
        if intent.direction:
            parts.append(f"direction={intent.direction}")
        return " | ".join(parts)


# ── Query plans ────────────────────────────────────────────────────────


class _QueryPlan:
    """Tek bir copilot intent'in çalıştırma planı."""

    __slots__ = ("sql", "params", "runner", "_summary_fn", "rejected_reason")

    def __init__(
        self,
        *,
        sql: str = "",
        params: list[Any] | None = None,
        runner: str = "select",
        summary_fn: Any = None,
        rejected_reason: str | None = None,
    ) -> None:
        self.sql = sql
        self.params = list(params or [])
        self.runner = runner
        self._summary_fn = summary_fn
        self.rejected_reason = rejected_reason

    def summary_fmt(self, count_or_total: Any, intent: CopilotIntent | None) -> str:
        if self._summary_fn is None:
            return ""
        result: str = self._summary_fn(count_or_total, intent)
        return result


def _where_with_scope(
    extra_clauses: list[str],
    extra_params: list[Any],
    company_ids: list[int],
    is_wildcard: bool,
) -> tuple[str, list[Any]]:
    clauses = list(extra_clauses)
    params = list(extra_params)
    if not is_wildcard:
        scope_clause, scope_params = _scope_clause(company_ids)
        clauses.append(scope_clause)
        params.extend(scope_params)
    if not clauses:
        return "", params
    return " WHERE " + " AND ".join(clauses), params


def _build_count_invoices(
    intent: CopilotIntent, company_ids: list[int], is_wildcard: bool,
) -> _QueryPlan:
    extra_clauses: list[str] = []
    extra_params: list[Any] = []
    if intent.time_window_days is not None:
        extra_clauses.append(
            "issue_date >= date('now', '-' || ? || ' days')",
        )
        extra_params.append(intent.time_window_days)
    if intent.entity_name:
        extra_clauses.append(
            "EXISTS (SELECT 1 FROM customers c "
            "WHERE c.id = invoices.customer_id "
            "AND c.full_name LIKE '%' || ? || '%')",
        )
        extra_params.append(intent.entity_name)
    where, params = _where_with_scope(extra_clauses, extra_params, company_ids, is_wildcard)
    sql = f"SELECT COUNT(*) AS n FROM invoices{where}"

    def summary(n: Any, intent_: CopilotIntent | None) -> str:
        parts = [f"{int(n)} fatura"]
        if intent_ and intent_.entity_name:
            parts.insert(0, intent_.entity_name + "'ya")
        if intent_ and intent_.time_window_days:
            parts.insert(0, f"Son {intent_.time_window_days} günde")
        return " ".join(parts) + "."

    return _QueryPlan(sql=sql, params=params, runner="count", summary_fn=summary)


def _build_list_invoices(
    intent: CopilotIntent, company_ids: list[int], is_wildcard: bool,
) -> _QueryPlan:
    extra_clauses: list[str] = []
    extra_params: list[Any] = []
    if intent.time_window_days is not None:
        extra_clauses.append(
            "issue_date >= date('now', '-' || ? || ' days')",
        )
        extra_params.append(intent.time_window_days)
    if intent.entity_name:
        extra_clauses.append(
            "EXISTS (SELECT 1 FROM customers c "
            "WHERE c.id = invoices.customer_id "
            "AND c.full_name LIKE '%' || ? || '%')",
        )
        extra_params.append(intent.entity_name)
    where, params = _where_with_scope(extra_clauses, extra_params, company_ids, is_wildcard)
    sql = (
        "SELECT id, invoice_number, title, amount, currency, "
        "status, issue_date, due_date "
        f"FROM invoices{where} ORDER BY issue_date DESC LIMIT 50"
    )

    def summary(n: Any, _intent: CopilotIntent | None) -> str:
        return f"{int(n)} fatura listelendi."

    return _QueryPlan(sql=sql, params=params, runner="select", summary_fn=summary)


def _build_sum_amount(
    intent: CopilotIntent, company_ids: list[int], is_wildcard: bool,
) -> _QueryPlan:
    extra_clauses: list[str] = []
    extra_params: list[Any] = []
    if intent.time_window_days is not None:
        extra_clauses.append(
            "entry_date >= date('now', '-' || ? || ' days')",
        )
        extra_params.append(intent.time_window_days)
    if intent.direction == "outgoing":
        extra_clauses.append("entry_type = 'income'")
    elif intent.direction == "incoming":
        extra_clauses.append("entry_type = 'expense'")
    if intent.entity_name:
        extra_clauses.append("counterparty_company LIKE '%' || ? || '%'")
        extra_params.append(intent.entity_name)
    where, params = _where_with_scope(extra_clauses, extra_params, company_ids, is_wildcard)
    sql = f"SELECT SUM(amount) AS total FROM finance_ledger_entries{where}"

    def summary(total: Any, intent_: CopilotIntent | None) -> str:
        parts = [f"₺{float(total):,.2f}"]
        if intent_ and intent_.direction == "outgoing":
            parts.append("toplam gelir")
        elif intent_ and intent_.direction == "incoming":
            parts.append("toplam gider")
        if intent_ and intent_.entity_name:
            parts.append(f"({intent_.entity_name})")
        return " ".join(parts) + "."

    return _QueryPlan(sql=sql, params=params, runner="sum", summary_fn=summary)


def _build_list_customers(
    intent: CopilotIntent, company_ids: list[int], is_wildcard: bool,
) -> _QueryPlan:
    extra_clauses = ["is_active = 1"]
    where, params = _where_with_scope(extra_clauses, [], company_ids, is_wildcard)
    sql = (
        "SELECT id, full_name, email, sector "
        f"FROM customers{where} ORDER BY full_name LIMIT 50"
    )

    def summary(n: Any, _intent: CopilotIntent | None) -> str:
        return f"{int(n)} cari (müşteri/tedarikçi)."

    return _QueryPlan(sql=sql, params=params, runner="select", summary_fn=summary)


def _build_list_anomalies(
    intent: CopilotIntent, company_ids: list[int], is_wildcard: bool,
) -> _QueryPlan:
    # anomaly_signals tablosunda `company_name` yok (`holding_id` var).
    # Scope'lu kullanıcılar için güvenli izolasyon haritası kurulana kadar
    # reddedilir. Wildcard scope (holding/admin) erişebilir.
    if not is_wildcard:
        return _QueryPlan(
            rejected_reason=(
                "Anomaly sinyalleri için holding/admin scope gerekiyor."
            ),
        )
    sql = (
        "SELECT id, signal_type, severity, confidence_pct, title "
        "FROM anomaly_signals WHERE status = 'open' "
        "ORDER BY "
        "CASE severity "
        "WHEN 'critical' THEN 0 WHEN 'high' THEN 1 "
        "WHEN 'medium' THEN 2 ELSE 3 END, "
        "detected_at DESC LIMIT 20"
    )

    def summary(n: Any, _intent: CopilotIntent | None) -> str:
        return f"{int(n)} açık anomali sinyali."

    return _QueryPlan(sql=sql, params=[], runner="select", summary_fn=summary)


def _build_balance(
    intent: CopilotIntent, company_ids: list[int], is_wildcard: bool,
) -> _QueryPlan:
    where, params = _where_with_scope([], [], company_ids, is_wildcard)
    sql = (
        "SELECT "
        "SUM(CASE WHEN entry_type = 'income' THEN amount ELSE 0 END) "
        "AS income, "
        "SUM(CASE WHEN entry_type = 'expense' THEN amount ELSE 0 END) "
        "AS expense "
        f"FROM finance_ledger_entries{where}"
    )
    return _QueryPlan(sql=sql, params=params, runner="balance")


def _build_vendor_count(
    intent: CopilotIntent, company_ids: list[int], is_wildcard: bool,
) -> _QueryPlan:
    extra_clauses = ["is_active = 1", "sector LIKE '%tedarik%'"]
    where, params = _where_with_scope(extra_clauses, [], company_ids, is_wildcard)
    sql = f"SELECT COUNT(*) AS n FROM customers{where}"

    def summary(n: Any, _intent: CopilotIntent | None) -> str:
        return f"{int(n)} aktif tedarikçi."

    return _QueryPlan(sql=sql, params=params, runner="count", summary_fn=summary)


_BUILDERS = {
    "count_invoices": _build_count_invoices,
    "list_invoices": _build_list_invoices,
    "sum_amount": _build_sum_amount,
    "list_customers": _build_list_customers,
    "list_anomalies": _build_list_anomalies,
    "cashflow_balance": _build_balance,
    "vendor_count": _build_vendor_count,
}


__all__ = ["CopilotEngine", "ReadOnlyViolation"]
