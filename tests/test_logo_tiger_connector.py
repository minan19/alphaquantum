"""I1: Logo Tiger Connector — XML parse doğruluk testleri.

Sentetik Logo XML fixture'ları ile:
  * Cari + Fatura parse doğru mu
  * Field tolerance: alternatif tag isimleri çalışıyor mu
  * TR tarih + TR sayı (1.234,56) doğru normalize ediliyor mu
  * Eksik field, geçersiz format → error olarak raporlanıyor mu
  * Signature_hash deterministik mi
"""
from __future__ import annotations

import unittest

from app.connectors import (
    ConnectorMode,
    LogoTigerConnector,
    get_connector,
)


# ── Fixture XML ────────────────────────────────────────────────────────

VALID_LOGO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<LOGOWORLD>
  <CARI>
    <CARI_KODU>CR001</CARI_KODU>
    <CARI_UNVAN>Acme Ticaret Ltd. Sirketi</CARI_UNVAN>
    <CARI_VKN>1234567890</CARI_VKN>
    <CARI_VERGI_DAIRESI>Kadikoy</CARI_VERGI_DAIRESI>
    <CARI_ADRES>Bagdat Cad. 100/5, Kadikoy</CARI_ADRES>
    <CARI_TELEFON>0216 555 1234</CARI_TELEFON>
    <CARI_EMAIL>info@acme.com.tr</CARI_EMAIL>
    <CARI_IBAN>TR33 0006 1005 1978 6457 8413 26</CARI_IBAN>
    <CARI_BAKIYE>15.000,50</CARI_BAKIYE>
    <CARI_DOVIZ>TRY</CARI_DOVIZ>
    <CARI_TIPI>1</CARI_TIPI>
  </CARI>
  <CARI>
    <CARI_KODU>CR002</CARI_KODU>
    <CARI_UNVAN>Beta Lojistik AS</CARI_UNVAN>
    <CARI_VKN>9876543210</CARI_VKN>
    <CARI_TIPI>2</CARI_TIPI>
  </CARI>
  <FATURA>
    <FATURA_NO>F2026000001</FATURA_NO>
    <FATURA_CARI_KODU>CR001</FATURA_CARI_KODU>
    <FATURA_TARIHI>2026-05-15</FATURA_TARIHI>
    <FATURA_VADE>2026-06-15</FATURA_VADE>
    <FATURA_NET>10.000,00</FATURA_NET>
    <FATURA_KDV>1.800,00</FATURA_KDV>
    <FATURA_BRUT>11.800,00</FATURA_BRUT>
    <FATURA_DOVIZ>TRY</FATURA_DOVIZ>
    <FATURA_TIPI>1</FATURA_TIPI>
    <FATURA_ACIKLAMA>Mayis donemi danismanlik</FATURA_ACIKLAMA>
  </FATURA>
  <FATURA>
    <FATURA_NO>F2026000002</FATURA_NO>
    <FATURA_CARI_KODU>CR002</FATURA_CARI_KODU>
    <FATURA_TARIHI>15.05.2026</FATURA_TARIHI>
    <FATURA_NET>5000</FATURA_NET>
    <FATURA_KDV>900</FATURA_KDV>
    <FATURA_BRUT>5900</FATURA_BRUT>
    <FATURA_TIPI>2</FATURA_TIPI>
  </FATURA>
</LOGOWORLD>
""".encode("utf-8")


INVALID_FIELD_XML = """<?xml version="1.0" encoding="UTF-8"?>
<LOGOWORLD>
  <CARI>
    <CARI_KODU>CR003</CARI_KODU>
    <!-- No CARI_UNVAN - should fail -->
  </CARI>
  <FATURA>
    <FATURA_NO>F2026000003</FATURA_NO>
    <FATURA_CARI_KODU>CR001</FATURA_CARI_KODU>
    <!-- No FATURA_TARIHI - should fail -->
  </FATURA>
</LOGOWORLD>
""".encode("utf-8")


MALFORMED_XML = b"<LOGOWORLD><CARI><CARI_KODU>CR001"  # truncated


class LogoTigerXMLParseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connector = LogoTigerConnector()

    def test_parse_valid_xml_customers(self) -> None:
        result = self.connector.parse(
            data=VALID_LOGO_XML, mode=ConnectorMode.XML,
        )
        self.assertEqual(len(result.customers), 2)
        c1 = result.customers[0]
        self.assertEqual(c1.source_code, "CR001")
        self.assertEqual(c1.name, "Acme Ticaret Ltd. Sirketi")
        self.assertEqual(c1.tax_number, "1234567890")
        self.assertEqual(c1.tax_office, "Kadikoy")
        self.assertEqual(c1.role, "customer")
        self.assertEqual(c1.balance, 15000.50)  # TR format normalize
        self.assertTrue(c1.iban and c1.iban.startswith("TR33"))

    def test_parse_valid_xml_invoices(self) -> None:
        result = self.connector.parse(
            data=VALID_LOGO_XML, mode=ConnectorMode.XML,
        )
        self.assertEqual(len(result.invoices), 2)
        inv1 = result.invoices[0]
        self.assertEqual(inv1.source_no, "F2026000001")
        self.assertEqual(inv1.customer_source_code, "CR001")
        self.assertEqual(inv1.issue_date, "2026-05-15")
        self.assertEqual(inv1.due_date, "2026-06-15")
        self.assertEqual(inv1.total_excl_tax, 10000.00)
        self.assertEqual(inv1.total_incl_tax, 11800.00)
        self.assertEqual(inv1.direction, "outgoing")

    def test_parse_handles_dd_mm_yyyy_date_format(self) -> None:
        result = self.connector.parse(
            data=VALID_LOGO_XML, mode=ConnectorMode.XML,
        )
        inv2 = result.invoices[1]
        self.assertEqual(inv2.issue_date, "2026-05-15")

    def test_parse_invoice_direction_from_type(self) -> None:
        result = self.connector.parse(
            data=VALID_LOGO_XML, mode=ConnectorMode.XML,
        )
        # FATURA_TIPI=1 → outgoing, =2 → incoming
        self.assertEqual(result.invoices[0].direction, "outgoing")
        self.assertEqual(result.invoices[1].direction, "incoming")

    def test_parse_customer_role_from_type(self) -> None:
        result = self.connector.parse(
            data=VALID_LOGO_XML, mode=ConnectorMode.XML,
        )
        # CARI_TIPI=1 → customer, =2 → supplier
        self.assertEqual(result.customers[0].role, "customer")
        self.assertEqual(result.customers[1].role, "supplier")

    def test_parse_iban_cleaned_no_spaces(self) -> None:
        result = self.connector.parse(
            data=VALID_LOGO_XML, mode=ConnectorMode.XML,
        )
        # Source IBAN had spaces; cleaned version no spaces
        iban = result.customers[0].iban
        self.assertIsNotNone(iban)
        assert iban is not None
        self.assertNotIn(" ", iban)
        self.assertEqual(len(iban), 26)

    def test_missing_required_fields_become_errors(self) -> None:
        result = self.connector.parse(
            data=INVALID_FIELD_XML, mode=ConnectorMode.XML,
        )
        self.assertEqual(len(result.customers), 0)
        self.assertEqual(len(result.invoices), 0)
        # 1 customer error + 1 invoice error
        self.assertEqual(len(result.errors), 2)
        error_codes = {e.error_code for e in result.errors}
        self.assertIn("invalid_customer", error_codes)
        self.assertIn("invalid_invoice", error_codes)

    def test_malformed_xml_returns_root_error(self) -> None:
        result = self.connector.parse(
            data=MALFORMED_XML, mode=ConnectorMode.XML,
        )
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0].error_code, "invalid_xml")

    def test_signature_hash_deterministic(self) -> None:
        result1 = self.connector.parse(
            data=VALID_LOGO_XML, mode=ConnectorMode.XML,
        )
        result2 = self.connector.parse(
            data=VALID_LOGO_XML, mode=ConnectorMode.XML,
        )
        hashes1 = [c.signature_hash for c in result1.customers]
        hashes2 = [c.signature_hash for c in result2.customers]
        self.assertEqual(hashes1, hashes2)
        # Hashes non-empty + unique per customer
        self.assertTrue(all(h for h in hashes1))
        self.assertEqual(len(set(hashes1)), len(hashes1))

    def test_summary_counts_correct(self) -> None:
        result = self.connector.parse(
            data=VALID_LOGO_XML, mode=ConnectorMode.XML,
        )
        self.assertEqual(result.summary["customers"], 2)
        self.assertEqual(result.summary["invoices"], 2)
        self.assertEqual(result.summary["errors"], 0)


class ConnectorRegistryTests(unittest.TestCase):
    def test_get_logo_tiger_connector(self) -> None:
        connector = get_connector("logo_tiger")
        self.assertIsInstance(connector, LogoTigerConnector)
        self.assertEqual(connector.connector_type, "logo_tiger")
        self.assertIn(ConnectorMode.XML, connector.supported_modes)

    def test_unknown_connector_raises(self) -> None:
        with self.assertRaises(ValueError):
            get_connector("garbage_erp")


class AlternativeFieldNamesTests(unittest.TestCase):
    """Logo versiyon farkları — alternatif tag isimleri çalışıyor mu."""

    def test_kod_alternative_tag(self) -> None:
        alt_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <ROOT>
          <CARI>
            <KOD>ALT001</KOD>
            <UNVAN>Test Alt Cari</UNVAN>
          </CARI>
        </ROOT>"""
        result = LogoTigerConnector().parse(data=alt_xml, mode=ConnectorMode.XML)
        self.assertEqual(len(result.customers), 1)
        self.assertEqual(result.customers[0].source_code, "ALT001")
        self.assertEqual(result.customers[0].name, "Test Alt Cari")

    def test_web_service_mode_raises_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError):
            LogoTigerConnector().parse(
                data=b"", mode=ConnectorMode.WEB_SERVICE,
            )


if __name__ == "__main__":
    unittest.main()
