"""I1: Connector base — jenerik ERP import arayüzü.

Tasarım kararları:
  * Connector saftır → IO yok. Input bytes/str alır, ParseResult döner.
  * Idempotency: her record bir signature_hash üretir (örn. fatura no +
    şirket VKN). Engine bu hash'i kullanarak yeniden import etmez.
  * Error tolerance: bir kötü satır tüm import'u öldürmemeli; ParseError
    listesi taşınır, kullanıcıya rapor edilir.
  * Field mapping: connector default mapping'i hardcoded; kullanıcı
    DB'deki connector_field_mappings ile override edebilir (future).
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Protocol


class ConnectorMode(str, enum.Enum):
    XML = "xml"
    EXCEL = "excel"
    WEB_SERVICE = "web_service"


# ── Parsed record types ────────────────────────────────────────────────


@dataclass(frozen=True)
class ParsedCustomer:
    """Logo'dan gelen Cari (müşteri/tedarikçi).

    Birleşik model: hem alıcı hem satıcı yan, role flag ile ayrılır.
    """

    source_code: str               # Logo'daki CARI_KODU
    name: str
    tax_number: str | None = None  # VKN/TCKN
    tax_office: str | None = None
    role: str = "both"             # 'customer' | 'supplier' | 'both'
    address: str | None = None
    email: str | None = None
    phone: str | None = None
    iban: str | None = None
    balance: float = 0.0
    currency: str = "TRY"
    signature_hash: str = ""       # source_code + tax_number


@dataclass(frozen=True)
class ParsedInvoice:
    """Logo Fatura."""

    source_no: str                 # Fatura no
    customer_source_code: str      # Logo CARI_KODU referansı
    issue_date: str                # YYYY-MM-DD
    due_date: str | None = None
    total_excl_tax: float = 0.0
    tax_amount: float = 0.0
    total_incl_tax: float = 0.0
    currency: str = "TRY"
    direction: str = "outgoing"    # 'outgoing' (sales) | 'incoming' (purchase)
    description: str | None = None
    signature_hash: str = ""       # source_no + direction


@dataclass(frozen=True)
class ParseError:
    row_index: int
    record_type: str
    error_code: str
    error_message: str
    raw_payload: str | None = None


@dataclass
class ParseResult:
    """Connector parse() çıktısı — engine bu sonucu DB'ye yazar."""

    customers: list[ParsedCustomer] = field(default_factory=list)
    invoices: list[ParsedInvoice] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)
    source_info: dict[str, Any] = field(default_factory=dict)

    @property
    def summary(self) -> dict[str, int]:
        return {
            "customers": len(self.customers),
            "invoices": len(self.invoices),
            "errors": len(self.errors),
        }


# ── Connector protocol ─────────────────────────────────────────────────


class BaseConnector(Protocol):
    """Tüm ERP connector'larının uyduğu sözleşme.

    parse() saf bir fonksiyon: bytes/str → ParseResult. IO yok, side effect yok.
    Engine bu sonucu validate eder ve persist eder.
    """

    connector_type: str
    supported_modes: tuple[ConnectorMode, ...]

    def parse(
        self,
        *,
        data: bytes,
        mode: ConnectorMode,
        filename: str | None = None,
    ) -> ParseResult:
        ...
