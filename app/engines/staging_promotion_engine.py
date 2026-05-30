"""I2: StagingPromotionEngine — stage edilmiş Logo verilerini gerçek tablolara aktarım.

## Akış

  1. list_staged()        — kullanıcının stage edilmiş kayıtları
  2. preview_promotion()  — dry-run: hangi yeni, hangi conflict (VKN match)
  3. promote()            — actual yazım + ledger entry oluşturma

## Conflict stratejileri

User policy seçer (frontend'den), engine uygular:
  * 'create_new'      → her zaman yeni kayıt aç (default)
  * 'update_existing' → eşleşen mevcut customer'ı güncelle
  * 'skip'            → conflict varsa atla

Conflict tespiti:
  * Customer: aynı VKN veya aynı isim + email
  * Invoice:  aynı invoice_number + customer_id

## Idempotency

staging_promotion_log → (user_id, signature_hash, record_type) UNIQUE
Aynı kaydı 2× promote etmek skip edilir (target_id'yi geri döner).

## Ledger entry üretimi

Outgoing fatura → income ledger entry
Incoming fatura → expense ledger entry
Otomatik üretilir, category='logo_import', description='{customer} #{no}'.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, cast


# Conflict resolution policies
CREATE_NEW = "create_new"
UPDATE_EXISTING = "update_existing"
SKIP = "skip"

VALID_POLICIES = {CREATE_NEW, UPDATE_EXISTING, SKIP}


@dataclass
class PromotionPlan:
    """preview_promotion() çıktısı — UI bu planı kullanıcıya gösterir."""

    new_customers: int = 0
    new_invoices: int = 0
    conflict_customers: int = 0  # mevcut bir kayıtla eşleşenler
    conflict_invoices: int = 0
    already_promoted_customers: int = 0  # promotion_log'a kayıtlı olanlar
    already_promoted_invoices: int = 0
    ledger_entries_to_create: int = 0
    customer_details: list[dict[str, Any]] | None = None
    invoice_details: list[dict[str, Any]] | None = None


@dataclass
class PromotionResult:
    """promote() çıktısı."""

    customers_created: int = 0
    customers_updated: int = 0
    customers_skipped: int = 0
    invoices_created: int = 0
    invoices_skipped: int = 0
    ledger_entries_created: int = 0
    errors: list[str] | None = None


class StagingPromotionEngine:
    """Logo staging → gerçek CRM/Invoice/Ledger aktarım."""

    LOGO_LEDGER_CATEGORY = "logo_import"

    def __init__(self, *, database_path: str) -> None:
        self._database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._database_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ── Public API ─────────────────────────────────────────────────────

    def list_staged(
        self, *, user_id: str, limit: int = 200,
    ) -> dict[str, Any]:
        """Kullanıcının stage edilmiş ham Logo kayıtları."""
        conn = self._connect()
        try:
            customers = [
                self._safe_payload(row)
                for row in conn.execute(
                    """
                    SELECT signature_hash, payload_json, created_at
                    FROM connector_staged_customers
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                ).fetchall()
            ]
            invoices = [
                self._safe_payload(row)
                for row in conn.execute(
                    """
                    SELECT signature_hash, payload_json, created_at
                    FROM connector_staged_invoices
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                ).fetchall()
            ]
        finally:
            conn.close()
        return {
            "customers": customers,
            "invoices": invoices,
            "customer_count": len(customers),
            "invoice_count": len(invoices),
        }

    def preview_promotion(
        self,
        *,
        user_id: str,
        company_name: str,
        policy: str = CREATE_NEW,
    ) -> PromotionPlan:
        """Dry-run: gerçek tablolara hangi etki olur?"""
        if policy not in VALID_POLICIES:
            raise ValueError(
                f"Geçersiz policy: {policy!r}. Geçerli: {sorted(VALID_POLICIES)}"
            )

        staged = self.list_staged(user_id=user_id, limit=10_000)
        plan = PromotionPlan(customer_details=[], invoice_details=[])

        conn = self._connect()
        try:
            already_customer_sigs = self._fetch_promoted_signatures(
                conn, user_id, "customer",
            )
            already_invoice_sigs = self._fetch_promoted_signatures(
                conn, user_id, "invoice",
            )

            for c in staged["customers"]:
                sig = c["signature_hash"]
                payload = c["payload"]
                if sig in already_customer_sigs:
                    plan.already_promoted_customers += 1
                    continue
                existing = self._find_matching_customer(
                    conn, company_name=company_name, payload=payload,
                )
                action: str
                if existing:
                    plan.conflict_customers += 1
                    action = policy
                else:
                    plan.new_customers += 1
                    action = "create"
                assert plan.customer_details is not None
                plan.customer_details.append({
                    "signature_hash": sig,
                    "source_code": payload.get("source_code"),
                    "name": payload.get("name"),
                    "tax_number": payload.get("tax_number"),
                    "existing_id": existing["id"] if existing else None,
                    "planned_action": action,
                })

            for inv in staged["invoices"]:
                sig = inv["signature_hash"]
                payload = inv["payload"]
                if sig in already_invoice_sigs:
                    plan.already_promoted_invoices += 1
                    continue
                # Invoice conflict = same invoice_number + company
                existing_inv = self._find_matching_invoice(
                    conn, company_name=company_name, payload=payload,
                )
                if existing_inv:
                    plan.conflict_invoices += 1
                    inv_action = policy
                else:
                    plan.new_invoices += 1
                    inv_action = "create"
                assert plan.invoice_details is not None
                plan.invoice_details.append({
                    "signature_hash": sig,
                    "source_no": payload.get("source_no"),
                    "customer_source_code": payload.get("customer_source_code"),
                    "issue_date": payload.get("issue_date"),
                    "amount": payload.get("total_incl_tax"),
                    "direction": payload.get("direction"),
                    "existing_id": existing_inv["id"] if existing_inv else None,
                    "planned_action": inv_action,
                })

            # Ledger entries = new invoices that will create (skip policy
            # için skip olanları sayma)
            assert plan.invoice_details is not None
            plan.ledger_entries_to_create = sum(
                1 for inv in plan.invoice_details
                if inv["planned_action"] in ("create", "update_existing", "create_new")
                and not (policy == SKIP and inv["existing_id"] is not None)
            )
        finally:
            conn.close()
        return plan

    def promote(
        self,
        *,
        user_id: str,
        company_name: str,
        policy: str = CREATE_NEW,
    ) -> PromotionResult:
        """Stage → gerçek tablolar. ATOMIK değil (per-record commit),
        ancak her record idempotent → tekrar çalıştırmak güvenli.
        """
        if policy not in VALID_POLICIES:
            raise ValueError(
                f"Geçersiz policy: {policy!r}. Geçerli: {sorted(VALID_POLICIES)}"
            )

        staged = self.list_staged(user_id=user_id, limit=10_000)
        result = PromotionResult(errors=[])
        now = int(time.time())

        conn = self._connect()
        try:
            already_customer_sigs = self._fetch_promoted_signatures(
                conn, user_id, "customer",
            )
            already_invoice_sigs = self._fetch_promoted_signatures(
                conn, user_id, "invoice",
            )

            # customer source_code → customer_id mapping (invoice'da gerek)
            sig_to_customer_id: dict[str, int] = {}
            # promoted_log'tan eski mapping'i yükle
            for row in conn.execute(
                """
                SELECT source_signature_hash, target_id
                FROM staging_promotion_log
                WHERE user_id = ? AND record_type = 'customer'
                """,
                (user_id,),
            ).fetchall():
                sig_to_customer_id[row["source_signature_hash"]] = int(row["target_id"])

            source_code_to_customer_id: dict[str, int] = {}
            # ── Customers ──────────────────────────────────────────────
            for c in staged["customers"]:
                sig = c["signature_hash"]
                payload = c["payload"]
                source_code = payload.get("source_code") or ""

                if sig in already_customer_sigs:
                    target_id = sig_to_customer_id.get(sig)
                    if target_id and source_code:
                        source_code_to_customer_id[source_code] = target_id
                    result.customers_skipped += 1
                    continue

                existing = self._find_matching_customer(
                    conn, company_name=company_name, payload=payload,
                )
                target_id = None
                action_taken: str = CREATE_NEW

                if existing and policy == SKIP:
                    target_id = int(existing["id"])
                    action_taken = SKIP
                    result.customers_skipped += 1
                elif existing and policy == UPDATE_EXISTING:
                    self._update_customer(
                        conn, existing_id=int(existing["id"]),
                        company_name=company_name, payload=payload, now=now,
                    )
                    target_id = int(existing["id"])
                    action_taken = UPDATE_EXISTING
                    result.customers_updated += 1
                else:
                    # create_new (either no existing, or policy='create_new'
                    # with existing)
                    try:
                        target_id = self._create_customer(
                            conn, company_name=company_name,
                            payload=payload, now=now,
                        )
                        action_taken = CREATE_NEW
                        result.customers_created += 1
                    except Exception as exc:
                        assert result.errors is not None
                        result.errors.append(
                            f"Customer {payload.get('source_code')}: {exc}"
                        )
                        continue

                if target_id and source_code:
                    source_code_to_customer_id[source_code] = target_id
                if target_id is not None:
                    self._record_promotion(
                        conn, user_id=user_id, record_type="customer",
                        signature_hash=sig, target_table="customers",
                        target_id=target_id, conflict_resolution=action_taken,
                        now=now,
                    )

            # ── Invoices ───────────────────────────────────────────────
            for inv in staged["invoices"]:
                sig = inv["signature_hash"]
                payload = inv["payload"]

                if sig in already_invoice_sigs:
                    result.invoices_skipped += 1
                    continue

                # Customer mapping
                customer_source = payload.get("customer_source_code") or ""
                customer_id = source_code_to_customer_id.get(customer_source)
                if customer_id is None:
                    # Maybe customer wasn't staged or already had a row?
                    fallback = self._find_customer_by_source_code(
                        conn, company_name=company_name,
                        source_code=customer_source,
                    )
                    if fallback:
                        customer_id = int(fallback["id"])
                # customer_id None ise invoices.customer_id NULL kalır (FK ON DELETE SET NULL)

                existing_inv = self._find_matching_invoice(
                    conn, company_name=company_name, payload=payload,
                )
                invoice_id: int | None = None
                action_taken_inv: str = CREATE_NEW
                if existing_inv and policy == SKIP:
                    invoice_id = int(existing_inv["id"])
                    action_taken_inv = SKIP
                    result.invoices_skipped += 1
                else:
                    # create_new (update_existing is rare for invoices,
                    # treat as create)
                    try:
                        invoice_id = self._create_invoice(
                            conn, company_name=company_name,
                            customer_id=customer_id,
                            payload=payload, now=now,
                        )
                        action_taken_inv = CREATE_NEW
                        result.invoices_created += 1
                        # Ledger entry üret
                        if self._create_ledger_entry_for_invoice(
                            conn, company_name=company_name, payload=payload,
                            now=now,
                        ):
                            result.ledger_entries_created += 1
                    except Exception as exc:
                        assert result.errors is not None
                        result.errors.append(
                            f"Invoice {payload.get('source_no')}: {exc}"
                        )
                        continue

                if invoice_id is not None:
                    self._record_promotion(
                        conn, user_id=user_id, record_type="invoice",
                        signature_hash=sig, target_table="invoices",
                        target_id=invoice_id, conflict_resolution=action_taken_inv,
                        now=now,
                    )

            conn.commit()
        finally:
            conn.close()
        return result

    # ── Internal: matching ─────────────────────────────────────────────

    @staticmethod
    def _fetch_promoted_signatures(
        conn: sqlite3.Connection, user_id: str, record_type: str,
    ) -> set[str]:
        rows = conn.execute(
            """
            SELECT source_signature_hash FROM staging_promotion_log
            WHERE user_id = ? AND record_type = ?
            """,
            (user_id, record_type),
        ).fetchall()
        return {str(r["source_signature_hash"]) for r in rows}

    @staticmethod
    def _find_matching_customer(
        conn: sqlite3.Connection, *, company_name: str, payload: dict[str, Any],
    ) -> sqlite3.Row | None:
        """VKN match önce, sonra full_name + email."""
        tax_number = (payload.get("tax_number") or "").strip()
        if tax_number:
            row = conn.execute(
                """
                SELECT id FROM customers
                WHERE company_name = ?
                  AND notes LIKE ? || '%'
                LIMIT 1
                """,
                (company_name, f"VKN:{tax_number}"),
            ).fetchone()
            if row:
                return cast(sqlite3.Row, row)
        name = (payload.get("name") or "").strip()
        email = (payload.get("email") or "").strip()
        if name and email:
            row = conn.execute(
                """
                SELECT id FROM customers
                WHERE company_name = ? AND full_name = ? AND email = ?
                LIMIT 1
                """,
                (company_name, name, email),
            ).fetchone()
            if row:
                return cast(sqlite3.Row, row)
        return None

    @staticmethod
    def _find_customer_by_source_code(
        conn: sqlite3.Connection, *, company_name: str, source_code: str,
    ) -> sqlite3.Row | None:
        if not source_code:
            return None
        return cast("sqlite3.Row | None", conn.execute(
            """
            SELECT id FROM customers
            WHERE company_name = ? AND notes LIKE ?
            LIMIT 1
            """,
            (company_name, f"%LogoKod:{source_code}%"),
        ).fetchone())

    @staticmethod
    def _find_matching_invoice(
        conn: sqlite3.Connection, *, company_name: str, payload: dict[str, Any],
    ) -> sqlite3.Row | None:
        no = (payload.get("source_no") or "").strip()
        if not no:
            return None
        return cast("sqlite3.Row | None", conn.execute(
            """
            SELECT id FROM invoices
            WHERE company_name = ? AND invoice_number = ?
            LIMIT 1
            """,
            (company_name, no),
        ).fetchone())

    # ── Internal: writers ──────────────────────────────────────────────

    @staticmethod
    def _build_customer_notes(payload: dict[str, Any]) -> str:
        """VKN + LogoKod + tax_office + address birleştir."""
        parts: list[str] = []
        if payload.get("tax_number"):
            parts.append(f"VKN:{payload['tax_number']}")
        if payload.get("source_code"):
            parts.append(f"LogoKod:{payload['source_code']}")
        if payload.get("tax_office"):
            parts.append(f"VD:{payload['tax_office']}")
        if payload.get("address"):
            parts.append(str(payload["address"]))
        return " | ".join(parts)

    def _create_customer(
        self,
        conn: sqlite3.Connection,
        *,
        company_name: str,
        payload: dict[str, Any],
        now: int,
    ) -> int:
        tags = json.dumps(["logo_import"], ensure_ascii=False)
        cur = conn.execute(
            """
            INSERT INTO customers
                (company_name, full_name, email, phone, sector,
                 tags, notes, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                company_name,
                str(payload.get("name", "")).strip()[:255] or "(adı yok)",
                str(payload.get("email", "") or "")[:255],
                str(payload.get("phone", "") or "")[:50],
                "general",
                tags,
                self._build_customer_notes(payload),
                now, now,
            ),
        )
        return int(cur.lastrowid or 0)

    def _update_customer(
        self,
        conn: sqlite3.Connection,
        *,
        existing_id: int,
        company_name: str,
        payload: dict[str, Any],
        now: int,
    ) -> None:
        conn.execute(
            """
            UPDATE customers
            SET full_name = ?, email = ?, phone = ?, notes = ?,
                updated_at = ?
            WHERE id = ? AND company_name = ?
            """,
            (
                str(payload.get("name", "")).strip()[:255] or "(adı yok)",
                str(payload.get("email", "") or "")[:255],
                str(payload.get("phone", "") or "")[:50],
                self._build_customer_notes(payload),
                now, existing_id, company_name,
            ),
        )

    @staticmethod
    def _create_invoice(
        conn: sqlite3.Connection,
        *,
        company_name: str,
        customer_id: int | None,
        payload: dict[str, Any],
        now: int,
    ) -> int:
        amount = float(payload.get("total_incl_tax") or 0)
        direction = str(payload.get("direction") or "outgoing")
        # status: pending (Logo import'tan gelen genellikle bilinmez)
        status = "pending"
        description = (
            f"[Logo {direction}] "
            f"{payload.get('description', '') or ''}"
        )[:500]
        title = f"Logo {payload.get('source_no', '?')}"[:255]
        cur = conn.execute(
            """
            INSERT INTO invoices
                (company_name, customer_id, proposal_id,
                 invoice_number, title, amount, paid_amount,
                 currency, status, issue_date, due_date, paid_date,
                 description, created_at, updated_at)
            VALUES (?, ?, NULL, ?, ?, ?, 0, ?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                company_name, customer_id,
                str(payload.get("source_no", "")).strip()[:50],
                title,
                amount,
                str(payload.get("currency", "TRY") or "TRY")[:10],
                status,
                str(payload.get("issue_date", "")),
                str(payload.get("due_date") or payload.get("issue_date", "")),
                description,
                now, now,
            ),
        )
        return int(cur.lastrowid or 0)

    def _create_ledger_entry_for_invoice(
        self,
        conn: sqlite3.Connection,
        *,
        company_name: str,
        payload: dict[str, Any],
        now: int,
    ) -> bool:
        amount = float(payload.get("total_incl_tax") or 0)
        if amount <= 0:
            return False
        direction = str(payload.get("direction") or "outgoing")
        entry_type = "income" if direction == "outgoing" else "expense"
        desc = (
            f"Logo {payload.get('source_no', '?')} - "
            f"{payload.get('customer_source_code', '?')}"
        )[:500]
        conn.execute(
            """
            INSERT INTO finance_ledger_entries
                (company_name, entry_type, amount, category, description,
                 entry_date, created_at, intercompany_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                company_name, entry_type, amount,
                self.LOGO_LEDGER_CATEGORY, desc,
                str(payload.get("issue_date", "")), now,
            ),
        )
        return True

    @staticmethod
    def _record_promotion(
        conn: sqlite3.Connection,
        *,
        user_id: str,
        record_type: str,
        signature_hash: str,
        target_table: str,
        target_id: int,
        conflict_resolution: str,
        now: int,
    ) -> None:
        try:
            conn.execute(
                """
                INSERT INTO staging_promotion_log
                    (user_id, record_type, source_signature_hash,
                     target_table, target_id, conflict_resolution,
                     promoted_at, promoted_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id, record_type, signature_hash, target_table,
                    target_id, conflict_resolution, now, user_id,
                ),
            )
        except sqlite3.IntegrityError:
            # Already logged — bu idempotency koruması
            pass

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _safe_payload(row: sqlite3.Row) -> dict[str, Any]:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            payload = {}
        return {
            "signature_hash": str(row["signature_hash"]),
            "payload": payload,
            "created_at": int(row["created_at"]),
        }
