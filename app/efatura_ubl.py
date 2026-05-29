"""G1.7: e-Fatura UBL-TR 2.1 üretici + okuyucu.

## UBL-TR 2.1

Türkiye'nin e-Fatura standardı OASIS UBL 2.1'in alt kümesidir.
GİB özel entegratörleri (Logo, Mikro, Edm vb.) ile uyumlu XML.

Bu modül:
  * generate_efatura_xml(invoice) — fatura dict'i → UBL-TR 2.1 XML
  * parse_efatura_xml(xml_bytes) — UBL-TR XML → standart dict

## Minimal namespace + element seti

UBL 2.1 spec'inden Türkiye için zorunlu olanlar:
  * Invoice (root)
  * UBLVersionID = "2.1"
  * CustomizationID = "TR1.2"
  * ProfileID = "TEMELFATURA" / "TICARIFATURA"
  * ID = fatura numarası
  * IssueDate, IssueTime
  * InvoiceTypeCode = "SATIS" | "IADE" | "TEVKIFAT" | ...
  * DocumentCurrencyCode = "TRY" / "USD"
  * AccountingSupplierParty (satıcı)
  * AccountingCustomerParty (alıcı)
  * InvoiceLine (kalemler)
  * TaxTotal (vergi özeti)
  * LegalMonetaryTotal (genel toplam)

## Yaklaşım

Stdlib xml.etree.ElementTree. Pure-Python fallback yok — UBL XML
genellikle expat'ı zaten bulunan production ortamda üretilir, eğer
yoksa graceful error.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from xml.etree import ElementTree as ET


# UBL-TR 2.1 namespaces
NS = {
    "":      "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac":   "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc":   "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ext":   "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "ds":    "http://www.w3.org/2000/09/xmldsig#",
    "xsi":   "http://www.w3.org/2001/XMLSchema-instance",
}

# CustomizationID for TR
TR_CUSTOMIZATION_ID = "TR1.2"
TR_DEFAULT_PROFILE = "TEMELFATURA"
TR_INVOICE_TYPE_SATIS = "SATIS"

# Default KDV oranı
DEFAULT_VAT_RATE = 0.18


# ── Domain dataclasses ────────────────────────────────────────────────


@dataclass
class EfaturaParty:
    """Satıcı veya alıcı tarafı."""

    tax_number: str
    name: str
    tax_office: str | None = None
    address: str | None = None
    district: str | None = None  # ilçe
    city: str | None = None
    country_code: str = "TR"
    email: str | None = None
    phone: str | None = None


@dataclass
class EfaturaLineItem:
    """Fatura kalemi."""

    description: str
    quantity: float
    unit_code: str = "C62"  # one (unitless)
    unit_price: float = 0.0
    vat_rate_pct: float = 18.0  # default KDV %18
    line_extension_amount: float = 0.0  # net = quantity × unit_price
    vat_amount: float = 0.0

    def compute(self) -> None:
        """quantity + unit_price → net + vat tutarları hesapla."""
        net = self.quantity * self.unit_price
        self.line_extension_amount = round(net, 2)
        self.vat_amount = round(net * (self.vat_rate_pct / 100), 2)


@dataclass
class EfaturaInvoice:
    """Tam e-Fatura nesnesi."""

    invoice_number: str
    issue_date: str             # YYYY-MM-DD
    issue_time: str = "10:00:00"
    invoice_type_code: str = TR_INVOICE_TYPE_SATIS
    document_currency_code: str = "TRY"
    profile_id: str = TR_DEFAULT_PROFILE
    supplier: EfaturaParty | None = None
    customer: EfaturaParty | None = None
    lines: list[EfaturaLineItem] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    uuid_override: str | None = None  # deterministic test için

    @property
    def uuid(self) -> str:
        if self.uuid_override:
            return self.uuid_override
        # Deterministic UUID-v4 benzeri: sha256(invoice_no+date)
        raw = f"{self.invoice_number}|{self.issue_date}"
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"

    @property
    def line_extension_total(self) -> float:
        return round(sum(li.line_extension_amount for li in self.lines), 2)

    @property
    def tax_total(self) -> float:
        return round(sum(li.vat_amount for li in self.lines), 2)

    @property
    def tax_inclusive_total(self) -> float:
        return round(self.line_extension_total + self.tax_total, 2)


# ── XML Generation ────────────────────────────────────────────────────


def generate_efatura_xml(invoice: EfaturaInvoice) -> bytes:
    """e-Fatura UBL-TR 2.1 XML üret.

    Returns: UTF-8 encoded XML bytes.

    Raises:
        ValueError: zorunlu field eksikse veya tutarlar tutmazsa.
    """
    _validate(invoice)
    for li in invoice.lines:
        # Eğer hesaplanmamışsa hesapla
        if li.line_extension_amount == 0 and li.unit_price > 0:
            li.compute()

    # Register namespace prefixes BEFORE creating Element
    for prefix, uri in NS.items():
        if prefix:
            ET.register_namespace(prefix, uri)

    root = ET.Element(_cbc("Invoice", NS[""]))
    root.set("xmlns", NS[""])
    root.set("xmlns:cac", NS["cac"])
    root.set("xmlns:cbc", NS["cbc"])
    root.set("xmlns:ext", NS["ext"])

    # Header — sıra UBL spec'ine uygun
    _add_cbc(root, "UBLVersionID", "2.1")
    _add_cbc(root, "CustomizationID", TR_CUSTOMIZATION_ID)
    _add_cbc(root, "ProfileID", invoice.profile_id)
    _add_cbc(root, "ID", invoice.invoice_number)
    _add_cbc(root, "UUID", invoice.uuid)
    _add_cbc(root, "IssueDate", invoice.issue_date)
    _add_cbc(root, "IssueTime", invoice.issue_time)
    _add_cbc(root, "InvoiceTypeCode", invoice.invoice_type_code)
    for note in invoice.notes:
        _add_cbc(root, "Note", note)
    _add_cbc(
        root, "DocumentCurrencyCode", invoice.document_currency_code,
    )
    _add_cbc(root, "LineCountNumeric", str(len(invoice.lines)))

    # Supplier
    if invoice.supplier:
        _add_party(root, "AccountingSupplierParty", invoice.supplier)
    if invoice.customer:
        _add_party(root, "AccountingCustomerParty", invoice.customer)

    # Tax Total
    tax_total_node = ET.SubElement(root, _q("cac", "TaxTotal"))
    _add_amount(
        tax_total_node, "TaxAmount", invoice.tax_total,
        invoice.document_currency_code,
    )
    tax_subtotal = ET.SubElement(tax_total_node, _q("cac", "TaxSubtotal"))
    _add_amount(
        tax_subtotal, "TaxableAmount", invoice.line_extension_total,
        invoice.document_currency_code,
    )
    _add_amount(
        tax_subtotal, "TaxAmount", invoice.tax_total,
        invoice.document_currency_code,
    )
    _add_cbc(tax_subtotal, "Percent", "18.00")
    tax_cat = ET.SubElement(tax_subtotal, _q("cac", "TaxCategory"))
    tax_scheme = ET.SubElement(tax_cat, _q("cac", "TaxScheme"))
    _add_cbc(tax_scheme, "Name", "KDV")
    _add_cbc(tax_scheme, "TaxTypeCode", "0015")

    # Legal Monetary Total
    lmt = ET.SubElement(root, _q("cac", "LegalMonetaryTotal"))
    _add_amount(
        lmt, "LineExtensionAmount", invoice.line_extension_total,
        invoice.document_currency_code,
    )
    _add_amount(
        lmt, "TaxExclusiveAmount", invoice.line_extension_total,
        invoice.document_currency_code,
    )
    _add_amount(
        lmt, "TaxInclusiveAmount", invoice.tax_inclusive_total,
        invoice.document_currency_code,
    )
    _add_amount(
        lmt, "PayableAmount", invoice.tax_inclusive_total,
        invoice.document_currency_code,
    )

    # Invoice Lines
    for idx, line in enumerate(invoice.lines, start=1):
        _add_invoice_line(
            root, idx, line, invoice.document_currency_code,
        )

    # Serialize with declaration
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _validate(invoice: EfaturaInvoice) -> None:
    if not invoice.invoice_number.strip():
        raise ValueError("invoice_number boş olamaz")
    try:
        datetime.strptime(invoice.issue_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(
            f"issue_date YYYY-MM-DD olmalı: {invoice.issue_date!r}"
        ) from exc
    if not invoice.supplier:
        raise ValueError("supplier zorunlu")
    if not invoice.customer:
        raise ValueError("customer zorunlu")
    if not invoice.lines:
        raise ValueError("En az 1 fatura kalemi gerekli")
    if not invoice.supplier.tax_number:
        raise ValueError("supplier.tax_number zorunlu")
    if not invoice.customer.tax_number:
        raise ValueError("customer.tax_number zorunlu")
    for li in invoice.lines:
        if li.quantity <= 0:
            raise ValueError(
                f"Kalem '{li.description[:40]}' quantity > 0 olmalı"
            )


def _add_cbc(parent: ET.Element, tag: str, text: str) -> ET.Element:
    el = ET.SubElement(parent, _q("cbc", tag))
    el.text = text
    return el


def _add_amount(
    parent: ET.Element, tag: str, value: float, currency: str,
) -> ET.Element:
    el = ET.SubElement(parent, _q("cbc", tag))
    el.set("currencyID", currency)
    el.text = f"{value:.2f}"
    return el


def _add_party(
    parent: ET.Element, wrapper_tag: str, party: EfaturaParty,
) -> None:
    wrapper = ET.SubElement(parent, _q("cac", wrapper_tag))
    party_node = ET.SubElement(wrapper, _q("cac", "Party"))

    # PartyIdentification — VKN
    pid = ET.SubElement(party_node, _q("cac", "PartyIdentification"))
    pid_id = _add_cbc(pid, "ID", party.tax_number)
    scheme = "VKN" if len(party.tax_number) == 10 else "TCKN"
    pid_id.set("schemeID", scheme)

    # PartyName
    pn = ET.SubElement(party_node, _q("cac", "PartyName"))
    _add_cbc(pn, "Name", party.name)

    # PostalAddress
    if party.address or party.city:
        addr = ET.SubElement(party_node, _q("cac", "PostalAddress"))
        if party.address:
            _add_cbc(addr, "StreetName", party.address)
        if party.district:
            _add_cbc(addr, "CitySubdivisionName", party.district)
        if party.city:
            _add_cbc(addr, "CityName", party.city)
        country = ET.SubElement(addr, _q("cac", "Country"))
        _add_cbc(country, "IdentificationCode", party.country_code)

    # PartyTaxScheme (vergi dairesi)
    if party.tax_office:
        pts = ET.SubElement(party_node, _q("cac", "PartyTaxScheme"))
        ts = ET.SubElement(pts, _q("cac", "TaxScheme"))
        _add_cbc(ts, "Name", party.tax_office)

    # Contact
    if party.email or party.phone:
        contact = ET.SubElement(party_node, _q("cac", "Contact"))
        if party.phone:
            _add_cbc(contact, "Telephone", party.phone)
        if party.email:
            _add_cbc(contact, "ElectronicMail", party.email)


def _add_invoice_line(
    parent: ET.Element,
    line_id: int,
    line: EfaturaLineItem,
    currency: str,
) -> None:
    il = ET.SubElement(parent, _q("cac", "InvoiceLine"))
    _add_cbc(il, "ID", str(line_id))

    qty_el = ET.SubElement(il, _q("cbc", "InvoicedQuantity"))
    qty_el.set("unitCode", line.unit_code)
    qty_el.text = f"{line.quantity:.4f}"

    _add_amount(
        il, "LineExtensionAmount", line.line_extension_amount, currency,
    )

    tax_total_node = ET.SubElement(il, _q("cac", "TaxTotal"))
    _add_amount(tax_total_node, "TaxAmount", line.vat_amount, currency)
    sub = ET.SubElement(tax_total_node, _q("cac", "TaxSubtotal"))
    _add_amount(
        sub, "TaxableAmount", line.line_extension_amount, currency,
    )
    _add_amount(sub, "TaxAmount", line.vat_amount, currency)
    _add_cbc(sub, "Percent", f"{line.vat_rate_pct:.2f}")
    cat = ET.SubElement(sub, _q("cac", "TaxCategory"))
    scheme = ET.SubElement(cat, _q("cac", "TaxScheme"))
    _add_cbc(scheme, "Name", "KDV")
    _add_cbc(scheme, "TaxTypeCode", "0015")

    item = ET.SubElement(il, _q("cac", "Item"))
    _add_cbc(item, "Name", line.description)

    pp = ET.SubElement(il, _q("cac", "Price"))
    _add_amount(pp, "PriceAmount", line.unit_price, currency)


def _q(prefix: str, tag: str) -> str:
    """Namespace-qualified tag name (ET.SubElement için)."""
    return f"{{{NS[prefix]}}}{tag}"


def _cbc(tag: str, ns_uri: str) -> str:
    return f"{{{ns_uri}}}{tag}"


# ── XML Parsing ───────────────────────────────────────────────────────


def parse_efatura_xml(xml_bytes: bytes) -> dict[str, Any]:
    """e-Fatura UBL-TR XML → standart dict.

    Returns: invoice_number, issue_date, supplier/customer, lines,
             totals etc.
    """
    root = ET.fromstring(xml_bytes)

    def find_text(parent: ET.Element, path: str) -> str | None:
        el = parent.find(path, NS)
        return el.text if el is not None and el.text else None

    invoice_number = find_text(root, "cbc:ID")
    issue_date = find_text(root, "cbc:IssueDate")
    invoice_type = find_text(root, "cbc:InvoiceTypeCode")
    currency = find_text(root, "cbc:DocumentCurrencyCode") or "TRY"

    supplier = _parse_party(root, "cac:AccountingSupplierParty")
    customer = _parse_party(root, "cac:AccountingCustomerParty")

    lines: list[dict[str, Any]] = []
    for il in root.findall("cac:InvoiceLine", NS):
        line_id = find_text(il, "cbc:ID")
        qty_el = il.find("cbc:InvoicedQuantity", NS)
        qty = float(qty_el.text) if qty_el is not None and qty_el.text else 0
        lea = find_text(il, "cbc:LineExtensionAmount")
        vat_el = il.find(
            "cac:TaxTotal/cbc:TaxAmount", NS,
        )
        vat = float(vat_el.text) if vat_el is not None and vat_el.text else 0
        item_name = find_text(il, "cac:Item/cbc:Name")
        price_el = il.find("cac:Price/cbc:PriceAmount", NS)
        unit_price = (
            float(price_el.text) if price_el is not None and price_el.text else 0
        )
        lines.append({
            "id": line_id,
            "description": item_name,
            "quantity": qty,
            "unit_price": unit_price,
            "line_extension_amount": float(lea) if lea else 0,
            "vat_amount": vat,
        })

    lmt = root.find("cac:LegalMonetaryTotal", NS)
    totals: dict[str, float] = {}
    if lmt is not None:
        for k in (
            "LineExtensionAmount", "TaxExclusiveAmount",
            "TaxInclusiveAmount", "PayableAmount",
        ):
            el = lmt.find(f"cbc:{k}", NS)
            if el is not None and el.text:
                totals[k] = float(el.text)

    return {
        "invoice_number": invoice_number,
        "issue_date": issue_date,
        "invoice_type_code": invoice_type,
        "currency": currency,
        "supplier": supplier,
        "customer": customer,
        "lines": lines,
        "totals": totals,
    }


def _parse_party(
    root: ET.Element, wrapper_path: str,
) -> dict[str, Any] | None:
    wrapper = root.find(wrapper_path, NS)
    if wrapper is None:
        return None
    party = wrapper.find("cac:Party", NS)
    if party is None:
        return None

    pid_id_el = party.find("cac:PartyIdentification/cbc:ID", NS)
    tax_number = pid_id_el.text if pid_id_el is not None else None

    name_el = party.find("cac:PartyName/cbc:Name", NS)
    name = name_el.text if name_el is not None else None

    addr = party.find("cac:PostalAddress", NS)
    address_dict: dict[str, str | None] = {}
    if addr is not None:
        street = addr.find("cbc:StreetName", NS)
        city = addr.find("cbc:CityName", NS)
        district = addr.find("cbc:CitySubdivisionName", NS)
        country = addr.find("cac:Country/cbc:IdentificationCode", NS)
        address_dict = {
            "street": street.text if street is not None else None,
            "district": district.text if district is not None else None,
            "city": city.text if city is not None else None,
            "country": country.text if country is not None else None,
        }

    tax_office_el = party.find(
        "cac:PartyTaxScheme/cac:TaxScheme/cbc:Name", NS,
    )
    tax_office = tax_office_el.text if tax_office_el is not None else None

    return {
        "tax_number": tax_number,
        "name": name,
        "tax_office": tax_office,
        "address": address_dict,
    }
