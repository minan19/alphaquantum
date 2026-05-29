"""G1.7: e-Fatura UBL-TR 2.1 router — invoice → UBL XML generate + parse."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.efatura_ubl import (
    EfaturaInvoice,
    EfaturaLineItem,
    EfaturaParty,
    generate_efatura_xml,
    parse_efatura_xml,
)
from app.models import UserProfile
from app.routers._deps import _value_error_to_http
from app.security import require_permissions


router = APIRouter()


# ── Pydantic models (local — küçük yüzey) ──────────────────────────────


class EfaturaPartyPayload(BaseModel):
    tax_number: str = Field(min_length=10, max_length=11)
    name: str = Field(min_length=1, max_length=200)
    tax_office: str | None = Field(default=None, max_length=80)
    address: str | None = Field(default=None, max_length=500)
    district: str | None = Field(default=None, max_length=80)
    city: str | None = Field(default=None, max_length=80)
    country_code: str = Field(default="TR", pattern="^[A-Z]{2}$")
    email: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)


class EfaturaLinePayload(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    quantity: float = Field(gt=0)
    unit_code: str = Field(default="C62", max_length=10)
    unit_price: float = Field(ge=0)
    vat_rate_pct: float = Field(default=18.0, ge=0, le=100)


class EfaturaInvoicePayload(BaseModel):
    invoice_number: str = Field(min_length=1, max_length=40)
    issue_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    issue_time: str = Field(default="10:00:00", pattern=r"^\d{2}:\d{2}:\d{2}$")
    invoice_type_code: str = Field(
        default="SATIS",
        pattern="^(SATIS|IADE|TEVKIFAT|ISTISNA|OZELMATRAH)$",
    )
    document_currency_code: str = Field(default="TRY", pattern="^[A-Z]{3}$")
    profile_id: str = Field(
        default="TEMELFATURA",
        pattern="^(TEMELFATURA|TICARIFATURA|YOLCUBERABERFATURA)$",
    )
    supplier: EfaturaPartyPayload
    customer: EfaturaPartyPayload
    lines: list[EfaturaLinePayload] = Field(min_length=1, max_length=1000)
    notes: list[str] = Field(default_factory=list, max_length=10)


class EfaturaParsedResponse(BaseModel):
    invoice_number: str | None
    issue_date: str | None
    invoice_type_code: str | None
    currency: str
    supplier: dict[str, Any] | None
    customer: dict[str, Any] | None
    lines: list[dict[str, Any]]
    totals: dict[str, float]


# ── Endpoints ──────────────────────────────────────────────────────────


@router.post(
    "/api/v1/efatura/generate",
    response_class=Response,
    tags=["efatura"],
)
def generate_invoice_xml(
    payload: EfaturaInvoicePayload,
    _user: UserProfile = Depends(require_permissions("manage_finance")),
) -> Response:
    """e-Fatura JSON → UBL-TR 2.1 XML.

    Returns: application/xml — content-disposition attachment.
    """
    supplier = EfaturaParty(**payload.supplier.model_dump())
    customer = EfaturaParty(**payload.customer.model_dump())
    lines = [
        EfaturaLineItem(**li.model_dump())
        for li in payload.lines
    ]
    invoice = EfaturaInvoice(
        invoice_number=payload.invoice_number,
        issue_date=payload.issue_date,
        issue_time=payload.issue_time,
        invoice_type_code=payload.invoice_type_code,
        document_currency_code=payload.document_currency_code,
        profile_id=payload.profile_id,
        supplier=supplier,
        customer=customer,
        lines=lines,
        notes=payload.notes,
    )
    try:
        xml_bytes = generate_efatura_xml(invoice)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc

    filename = f"efatura_{payload.invoice_number}.xml".replace("/", "_")
    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post(
    "/api/v1/efatura/parse",
    response_model=EfaturaParsedResponse,
    tags=["efatura"],
)
async def parse_invoice_xml(
    file: UploadFile = File(...),
    _user: UserProfile = Depends(require_permissions("read_finance")),
) -> EfaturaParsedResponse:
    """Yüklenen e-Fatura UBL XML'i parse et."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Boş dosya")
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Max 5 MB XML")
    try:
        parsed = parse_efatura_xml(data)
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"XML parse hatası: {exc}",
        ) from exc
    return EfaturaParsedResponse(**parsed)
