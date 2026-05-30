"""G1.7: e-Fatura UBL-TR 2.1 generate + parse tests."""
from __future__ import annotations

import unittest

from app.efatura_ubl import (
    EfaturaInvoice,
    EfaturaLineItem,
    EfaturaParty,
    generate_efatura_xml,
    parse_efatura_xml,
)


def _has_expat() -> bool:
    """Some Python builds (Homebrew issue) lack expat; XML parse fails."""
    try:
        from xml.parsers import expat  # noqa: F401
        return True
    except ImportError:
        try:
            import pyexpat  # noqa: F401
            return True
        except ImportError:
            return False


_EXPAT_AVAILABLE = _has_expat()


def _make_invoice(**overrides) -> EfaturaInvoice:
    defaults = {
        "invoice_number": "F-2026-000001",
        "issue_date": "2026-05-15",
        "supplier": EfaturaParty(
            tax_number="1234567890", name="Demo Holding A.S.",
            tax_office="Kadikoy",
        ),
        "customer": EfaturaParty(
            tax_number="9876543210", name="Musteri Ltd.",
            tax_office="Beyoglu",
        ),
        "lines": [
            EfaturaLineItem(
                description="Test Hizmet",
                quantity=2.0, unit_price=500.0, vat_rate_pct=18.0,
            ),
        ],
        "uuid_override": "00000000-0000-0000-0000-000000000001",
    }
    defaults.update(overrides)
    inv = EfaturaInvoice(**defaults)
    for li in inv.lines:
        li.compute()
    return inv


class EfaturaGenerateTests(unittest.TestCase):
    def test_generate_minimal_valid_invoice(self) -> None:
        inv = _make_invoice()
        xml = generate_efatura_xml(inv)
        self.assertTrue(xml.startswith(b"<?xml"))
        # UBL-TR markers
        self.assertIn(b"UBLVersionID", xml)
        self.assertIn(b"2.1", xml)
        self.assertIn(b"TR1.2", xml)
        self.assertIn(b"TEMELFATURA", xml)
        self.assertIn(b"F-2026-000001", xml)
        self.assertIn(b"1234567890", xml)
        self.assertIn(b"9876543210", xml)

    def test_amounts_computed_correctly(self) -> None:
        inv = _make_invoice()
        # 2 × 500 = 1000 net, KDV %18 = 180, gross = 1180
        self.assertAlmostEqual(inv.line_extension_total, 1000.0)
        self.assertAlmostEqual(inv.tax_total, 180.0)
        self.assertAlmostEqual(inv.tax_inclusive_total, 1180.0)

    def test_multiple_lines_sum_correctly(self) -> None:
        inv = _make_invoice(lines=[
            EfaturaLineItem(description="A", quantity=2, unit_price=100),
            EfaturaLineItem(description="B", quantity=1, unit_price=250),
        ])
        for li in inv.lines:
            li.compute()
        # 200 + 250 = 450 net, KDV %18 = 81, gross = 531
        self.assertAlmostEqual(inv.line_extension_total, 450.0)
        self.assertAlmostEqual(inv.tax_total, 81.0)
        self.assertAlmostEqual(inv.tax_inclusive_total, 531.0)

    def test_validate_empty_invoice_number_raises(self) -> None:
        inv = _make_invoice(invoice_number="   ")
        with self.assertRaises(ValueError):
            generate_efatura_xml(inv)

    def test_validate_invalid_date_raises(self) -> None:
        inv = _make_invoice(issue_date="2026/05/15")
        with self.assertRaises(ValueError):
            generate_efatura_xml(inv)

    def test_validate_missing_supplier_raises(self) -> None:
        inv = _make_invoice(supplier=None)
        with self.assertRaises(ValueError):
            generate_efatura_xml(inv)

    def test_validate_no_lines_raises(self) -> None:
        inv = _make_invoice(lines=[])
        with self.assertRaises(ValueError):
            generate_efatura_xml(inv)

    def test_validate_zero_quantity_raises(self) -> None:
        inv = _make_invoice(lines=[
            EfaturaLineItem(description="X", quantity=0, unit_price=100),
        ])
        with self.assertRaises(ValueError):
            generate_efatura_xml(inv)

    def test_uuid_deterministic_from_number_and_date(self) -> None:
        inv1 = _make_invoice(uuid_override=None)
        inv2 = _make_invoice(uuid_override=None)
        self.assertEqual(inv1.uuid, inv2.uuid)

    def test_uuid_changes_with_invoice_number(self) -> None:
        inv1 = _make_invoice(invoice_number="F-001", uuid_override=None)
        inv2 = _make_invoice(invoice_number="F-002", uuid_override=None)
        self.assertNotEqual(inv1.uuid, inv2.uuid)


@unittest.skipUnless(
    _EXPAT_AVAILABLE,
    "xml.parsers.expat unavailable in this Python build",
)
class EfaturaParseTests(unittest.TestCase):
    def test_round_trip_generate_then_parse(self) -> None:
        inv = _make_invoice()
        xml = generate_efatura_xml(inv)
        parsed = parse_efatura_xml(xml)
        self.assertEqual(parsed["invoice_number"], "F-2026-000001")
        self.assertEqual(parsed["issue_date"], "2026-05-15")
        self.assertEqual(parsed["currency"], "TRY")
        self.assertEqual(parsed["invoice_type_code"], "SATIS")
        self.assertEqual(len(parsed["lines"]), 1)

    def test_round_trip_supplier_customer(self) -> None:
        inv = _make_invoice()
        xml = generate_efatura_xml(inv)
        parsed = parse_efatura_xml(xml)
        self.assertEqual(parsed["supplier"]["tax_number"], "1234567890")
        self.assertEqual(parsed["supplier"]["name"], "Demo Holding A.S.")
        self.assertEqual(parsed["customer"]["tax_number"], "9876543210")
        self.assertEqual(parsed["customer"]["name"], "Musteri Ltd.")

    def test_round_trip_totals(self) -> None:
        inv = _make_invoice()
        xml = generate_efatura_xml(inv)
        parsed = parse_efatura_xml(xml)
        self.assertAlmostEqual(
            parsed["totals"]["LineExtensionAmount"], 1000.0,
        )
        self.assertAlmostEqual(
            parsed["totals"]["TaxInclusiveAmount"], 1180.0,
        )

    def test_parse_invalid_xml_raises(self) -> None:
        with self.assertRaises(Exception):
            parse_efatura_xml(b"<not really xml")


if __name__ == "__main__":
    unittest.main()
