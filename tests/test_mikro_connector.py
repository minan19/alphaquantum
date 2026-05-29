"""I3: Mikro ERP Connector tests."""
from __future__ import annotations

import unittest

from app.connectors import (
    ConnectorMode,
    MikroConnector,
    get_connector,
)


VALID_MIKRO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<MIKROIO>
  <CARILER>
    <CARI>
      <KOD>MK001</KOD>
      <UNVAN>Mikro Test Ticaret Ltd</UNVAN>
      <VERGI_NO>1234567890</VERGI_NO>
      <VERGI_DAIRE>Kadikoy</VERGI_DAIRE>
      <ADRES>Bagdat Cad. 1/1</ADRES>
      <TEL>02165551234</TEL>
      <EMAIL>info@mikrotest.com</EMAIL>
      <IBAN>TR33 0006 1005 1978 6457 8413 26</IBAN>
      <BAKIYE>15000.50</BAKIYE>
      <DOVIZ>TRY</DOVIZ>
      <TIP>ALICI</TIP>
    </CARI>
    <CARI>
      <KOD>MK002</KOD>
      <UNVAN>Mikro Tedarikci AS</UNVAN>
      <VERGI_NO>9876543210</VERGI_NO>
      <TIP>SATICI</TIP>
    </CARI>
  </CARILER>
  <FATURALAR>
    <FATURA>
      <NUMARA>MK-F-001</NUMARA>
      <CARI_KODU>MK001</CARI_KODU>
      <TARIH>2026-05-15</TARIH>
      <VADE>2026-06-15</VADE>
      <ARA_TOPLAM>10000.00</ARA_TOPLAM>
      <KDV_TOPLAM>1800.00</KDV_TOPLAM>
      <GENEL_TOPLAM>11800.00</GENEL_TOPLAM>
      <DOVIZ>TRY</DOVIZ>
      <TUR>SATIS</TUR>
      <ACIKLAMA>Mayis donemi danismanlik</ACIKLAMA>
    </FATURA>
    <FATURA>
      <NUMARA>MK-F-002</NUMARA>
      <CARI_KODU>MK002</CARI_KODU>
      <TARIH>15.05.2026</TARIH>
      <ARA_TOPLAM>5000</ARA_TOPLAM>
      <KDV_TOPLAM>900</KDV_TOPLAM>
      <GENEL_TOPLAM>5900</GENEL_TOPLAM>
      <TUR>ALIS</TUR>
    </FATURA>
  </FATURALAR>
</MIKROIO>
""".encode("utf-8")


INVALID_MIKRO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<MIKROIO>
  <CARI>
    <KOD>MK003</KOD>
    <!-- No UNVAN -->
  </CARI>
</MIKROIO>
""".encode("utf-8")


class MikroXMLParseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connector = MikroConnector()

    def test_parse_valid_xml_customers(self) -> None:
        result = self.connector.parse(
            data=VALID_MIKRO_XML, mode=ConnectorMode.XML,
        )
        self.assertEqual(len(result.customers), 2)
        c1 = result.customers[0]
        self.assertEqual(c1.source_code, "MK001")
        self.assertEqual(c1.name, "Mikro Test Ticaret Ltd")
        self.assertEqual(c1.tax_number, "1234567890")
        self.assertEqual(c1.role, "customer")  # ALICI → customer
        self.assertEqual(c1.balance, 15000.50)

    def test_parse_valid_xml_invoices(self) -> None:
        result = self.connector.parse(
            data=VALID_MIKRO_XML, mode=ConnectorMode.XML,
        )
        self.assertEqual(len(result.invoices), 2)
        inv1 = result.invoices[0]
        self.assertEqual(inv1.source_no, "MK-F-001")
        self.assertEqual(inv1.customer_source_code, "MK001")
        self.assertEqual(inv1.issue_date, "2026-05-15")
        self.assertEqual(inv1.total_incl_tax, 11800.00)
        self.assertEqual(inv1.direction, "outgoing")  # SATIS → outgoing

    def test_role_mapping_mikro_specific(self) -> None:
        """Mikro: ALICI=customer, SATICI=supplier"""
        result = self.connector.parse(
            data=VALID_MIKRO_XML, mode=ConnectorMode.XML,
        )
        self.assertEqual(result.customers[0].role, "customer")  # ALICI
        self.assertEqual(result.customers[1].role, "supplier")  # SATICI

    def test_direction_mapping_mikro_specific(self) -> None:
        """Mikro: SATIS=outgoing, ALIS=incoming"""
        result = self.connector.parse(
            data=VALID_MIKRO_XML, mode=ConnectorMode.XML,
        )
        self.assertEqual(result.invoices[0].direction, "outgoing")  # SATIS
        self.assertEqual(result.invoices[1].direction, "incoming")  # ALIS

    def test_dd_mm_yyyy_date_normalization(self) -> None:
        result = self.connector.parse(
            data=VALID_MIKRO_XML, mode=ConnectorMode.XML,
        )
        self.assertEqual(result.invoices[1].issue_date, "2026-05-15")

    def test_iban_normalization(self) -> None:
        result = self.connector.parse(
            data=VALID_MIKRO_XML, mode=ConnectorMode.XML,
        )
        iban = result.customers[0].iban
        self.assertIsNotNone(iban)
        assert iban is not None
        self.assertNotIn(" ", iban)
        self.assertEqual(len(iban), 26)

    def test_missing_required_field_becomes_error(self) -> None:
        result = self.connector.parse(
            data=INVALID_MIKRO_XML, mode=ConnectorMode.XML,
        )
        self.assertEqual(len(result.customers), 0)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0].error_code, "invalid_customer")

    def test_summary_correct(self) -> None:
        result = self.connector.parse(
            data=VALID_MIKRO_XML, mode=ConnectorMode.XML,
        )
        self.assertEqual(result.summary["customers"], 2)
        self.assertEqual(result.summary["invoices"], 2)
        self.assertEqual(result.summary["errors"], 0)

    def test_signature_hash_unique_per_record(self) -> None:
        result = self.connector.parse(
            data=VALID_MIKRO_XML, mode=ConnectorMode.XML,
        )
        sigs = [c.signature_hash for c in result.customers]
        self.assertEqual(len(set(sigs)), len(sigs))

    def test_signature_hash_differs_from_logo(self) -> None:
        """Aynı kayıt Logo + Mikro signature_hash farklı olmalı.

        Bu önemli — staging promotion duplicate'leri ayırt etmek için.
        """
        from app.connectors import LogoTigerConnector
        mikro_result = self.connector.parse(
            data=VALID_MIKRO_XML, mode=ConnectorMode.XML,
        )
        # Aynı kayıt Logo formatında
        logo_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <LOGOWORLD>
          <CARI>
            <CARI_KODU>MK001</CARI_KODU>
            <CARI_UNVAN>Mikro Test Ticaret Ltd</CARI_UNVAN>
            <CARI_VKN>1234567890</CARI_VKN>
            <CARI_TIPI>1</CARI_TIPI>
          </CARI>
        </LOGOWORLD>""".encode("utf-8")
        logo_result = LogoTigerConnector().parse(
            data=logo_xml, mode=ConnectorMode.XML,
        )
        # Same source_code + tax_number but different connector → different hash
        mikro_hash = mikro_result.customers[0].signature_hash
        logo_hash = logo_result.customers[0].signature_hash
        self.assertNotEqual(mikro_hash, logo_hash)


class MikroAlternativeTagsTests(unittest.TestCase):
    def test_fatura_no_alternative(self) -> None:
        alt_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <ROOT>
          <FATURA>
            <FATURA_NO>ALT-001</FATURA_NO>
            <CARI_KODU>CR1</CARI_KODU>
            <TARIH>2026-05-01</TARIH>
            <GENEL_TOPLAM>1000</GENEL_TOPLAM>
            <TUR>SATIS</TUR>
          </FATURA>
        </ROOT>""".encode("utf-8")
        result = MikroConnector().parse(data=alt_xml, mode=ConnectorMode.XML)
        self.assertEqual(len(result.invoices), 1)
        self.assertEqual(result.invoices[0].source_no, "ALT-001")

    def test_web_service_mode_raises(self) -> None:
        with self.assertRaises(NotImplementedError):
            MikroConnector().parse(
                data=b"", mode=ConnectorMode.WEB_SERVICE,
            )


class MikroRegistryTests(unittest.TestCase):
    def test_registry_returns_mikro(self) -> None:
        connector = get_connector("mikro")
        self.assertIsInstance(connector, MikroConnector)
        self.assertEqual(connector.connector_type, "mikro")
        self.assertIn(ConnectorMode.XML, connector.supported_modes)
        self.assertIn(ConnectorMode.EXCEL, connector.supported_modes)


if __name__ == "__main__":
    unittest.main()
