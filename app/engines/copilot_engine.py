"""AC1: CopilotEngine — intent → whitelisted SQL → safe query."""
from __future__ import annotations

import sqlite3
from typing import Any

from app.copilot_intent_parser import (
    CopilotIntent,
    CopilotResponse,
    OfflineCopilotParser,
)


# Whitelisted query templates — intent → (sql, params_factory)
# Direkt SQL execution YOK; sadece bu templater'lar kullanılır.

class CopilotEngine:
    """Whitelist-based query execution."""

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

    def ask(self, *, query: str) -> CopilotResponse:
        intent = self._parser.parse(query)
        return self._execute(intent)

    def _execute(self, intent: CopilotIntent) -> CopilotResponse:
        if intent.intent == "unknown":
            return CopilotResponse(
                intent=intent,
                summary_text="Soruyu anlayamadım. Örnek: 'Geçen ay AcmeCo'ya kaç fatura kestik?'",
                explanation="Intent classification: unknown",
            )

        results: list[dict[str, Any]] = []
        summary = ""
        explanation = ""
        sql_template = None

        if intent.intent == "count_invoices":
            sql_template = "count_invoices"
            sql, params = self._build_count_invoices(intent)
            results, summary = self._run_count(sql, params, intent)
            explanation = self._explain_intent(intent, "count")

        elif intent.intent == "list_invoices":
            sql_template = "list_invoices"
            sql, params = self._build_list_invoices(intent)
            results = self._run_select(sql, params)
            summary = f"{len(results)} fatura listelendi."
            explanation = self._explain_intent(intent, "list")

        elif intent.intent == "sum_amount":
            sql_template = "sum_amount"
            sql, params = self._build_sum_amount(intent)
            results, summary = self._run_sum(sql, params, intent)
            explanation = self._explain_intent(intent, "sum")

        elif intent.intent == "list_customers":
            sql_template = "list_customers"
            sql, params = self._build_list_customers(intent)
            results = self._run_select(sql, params)
            summary = f"{len(results)} cari (müşteri/tedarikçi)."
            explanation = "customers tablosundan tüm aktif kayıtlar."

        elif intent.intent == "list_anomalies":
            sql_template = "list_anomalies"
            sql, params = self._build_list_anomalies(intent)
            results = self._run_select(sql, params)
            summary = f"{len(results)} açık anomali sinyali."
            explanation = (
                "anomaly_signals tablosundan status='open', "
                "severity DESC sıralı."
            )

        elif intent.intent == "cashflow_balance":
            sql_template = "cashflow_balance"
            sql, params = self._build_balance(intent)
            results, summary = self._run_balance(sql, params)
            explanation = (
                "finance_ledger_entries'den income - expense farkı."
            )

        elif intent.intent == "vendor_count":
            sql_template = "vendor_count"
            row = self._connect().execute(
                """
                SELECT COUNT(*) AS n FROM customers
                WHERE is_active = 1 AND sector LIKE '%tedarik%'
                """,
            ).fetchone()
            n = int(row["n"]) if row else 0
            summary = f"{n} aktif tedarikçi."
            results = [{"vendor_count": n}]
            explanation = "customers tablosundan sector LIKE '%tedarik%'."

        return CopilotResponse(
            intent=intent,
            results=results,
            summary_text=summary,
            explanation=explanation,
            sql_template_used=sql_template,
        )

    # ── Query builders (whitelisted SQL) ───────────────────────────────

    def _build_count_invoices(
        self, intent: CopilotIntent,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if intent.time_window_days is not None:
            clauses.append("issue_date >= date('now', '-' || ? || ' days')")
            params.append(intent.time_window_days)
        if intent.entity_name:
            clauses.append(
                "EXISTS (SELECT 1 FROM customers c "
                "WHERE c.id = invoices.customer_id "
                "AND c.full_name LIKE '%' || ? || '%')"
            )
            params.append(intent.entity_name)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        return f"SELECT COUNT(*) AS n FROM invoices{where}", params

    def _build_list_invoices(
        self, intent: CopilotIntent,
    ) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if intent.time_window_days is not None:
            clauses.append("issue_date >= date('now', '-' || ? || ' days')")
            params.append(intent.time_window_days)
        if intent.entity_name:
            clauses.append(
                "EXISTS (SELECT 1 FROM customers c "
                "WHERE c.id = invoices.customer_id "
                "AND c.full_name LIKE '%' || ? || '%')"
            )
            params.append(intent.entity_name)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = (
            "SELECT id, invoice_number, title, amount, currency, "
            "status, issue_date, due_date "
            f"FROM invoices{where} ORDER BY issue_date DESC LIMIT 50"
        )
        return sql, params

    def _build_sum_amount(
        self, intent: CopilotIntent,
    ) -> tuple[str, list[Any]]:
        # Ledger entries üzerinden toplam
        clauses: list[str] = []
        params: list[Any] = []
        if intent.time_window_days is not None:
            clauses.append("entry_date >= date('now', '-' || ? || ' days')")
            params.append(intent.time_window_days)
        if intent.direction == "outgoing":
            clauses.append("entry_type = 'income'")
        elif intent.direction == "incoming":
            clauses.append("entry_type = 'expense'")
        if intent.entity_name:
            clauses.append("counterparty_company LIKE '%' || ? || '%'")
            params.append(intent.entity_name)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        return f"SELECT SUM(amount) AS total FROM finance_ledger_entries{where}", params

    def _build_list_customers(
        self, intent: CopilotIntent,
    ) -> tuple[str, list[Any]]:
        return (
            "SELECT id, full_name, email, sector "
            "FROM customers WHERE is_active = 1 "
            "ORDER BY full_name LIMIT 50"
        ), []

    def _build_list_anomalies(
        self, intent: CopilotIntent,
    ) -> tuple[str, list[Any]]:
        return (
            "SELECT id, signal_type, severity, confidence_pct, title "
            "FROM anomaly_signals WHERE status = 'open' "
            "ORDER BY "
            "CASE severity "
            "WHEN 'critical' THEN 0 WHEN 'high' THEN 1 "
            "WHEN 'medium' THEN 2 ELSE 3 END, "
            "detected_at DESC LIMIT 20"
        ), []

    def _build_balance(
        self, intent: CopilotIntent,
    ) -> tuple[str, list[Any]]:
        return (
            "SELECT "
            "SUM(CASE WHEN entry_type = 'income' THEN amount ELSE 0 END) AS income, "
            "SUM(CASE WHEN entry_type = 'expense' THEN amount ELSE 0 END) AS expense "
            "FROM finance_ledger_entries"
        ), []

    # ── Runners ────────────────────────────────────────────────────────

    def _run_select(
        self, sql: str, params: list[Any],
    ) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _run_count(
        self, sql: str, params: list[Any], intent: CopilotIntent,
    ) -> tuple[list[dict[str, Any]], str]:
        conn = self._connect()
        try:
            row = conn.execute(sql, tuple(params)).fetchone()
        finally:
            conn.close()
        n = int(row["n"]) if row else 0
        text_parts = [f"{n} fatura"]
        if intent.entity_name:
            text_parts.insert(0, intent.entity_name + "'ya")
        if intent.time_window_days:
            text_parts.insert(0, f"Son {intent.time_window_days} günde")
        return [{"count": n}], " ".join(text_parts) + "."

    def _run_sum(
        self, sql: str, params: list[Any], intent: CopilotIntent,
    ) -> tuple[list[dict[str, Any]], str]:
        conn = self._connect()
        try:
            row = conn.execute(sql, tuple(params)).fetchone()
        finally:
            conn.close()
        total = float(row["total"] or 0) if row else 0
        parts = [f"₺{total:,.2f}"]
        if intent.direction == "outgoing":
            parts.append("toplam gelir")
        elif intent.direction == "incoming":
            parts.append("toplam gider")
        if intent.entity_name:
            parts.append(f"({intent.entity_name})")
        return [{"total": total}], " ".join(parts) + "."

    def _run_balance(
        self, sql: str, params: list[Any],
    ) -> tuple[list[dict[str, Any]], str]:
        conn = self._connect()
        try:
            row = conn.execute(sql, tuple(params)).fetchone()
        finally:
            conn.close()
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

    @staticmethod
    def _explain_intent(intent: CopilotIntent, kind: str) -> str:
        parts: list[str] = [f"Intent: {intent.intent}"]
        if intent.entity_name:
            parts.append(f"entity={intent.entity_name}")
        if intent.time_window_days:
            parts.append(f"window={intent.time_window_days}g")
        if intent.direction:
            parts.append(f"direction={intent.direction}")
        return " | ".join(parts)
