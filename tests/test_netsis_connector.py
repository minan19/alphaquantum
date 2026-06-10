"""I4: Netsis ERP connector tests."""
from __future__ import annotations

import unittest

from app.connectors import (
    ConnectorMode,
    NetsisConnector,
    get_connector,
)


VALID_NETSIS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<NETSIS_EXPORT>
  <CARI_LIST>
    <CARI>
      <CARI_KOD>NS001</CARI_KOD>
      <CARI_UNVANI>Netsis Test Ticaret Ltd</CARI_UNVANI>
      <VKN_TCKN>1234567890</VKN_TCKN>
      <VD>Kadikoy</VD>
      <TELEFON>02165551234</TELEFON>
      <EMAIL>info@netsistest.com</EMAIL>
      <IBAN>TR330006100519786457841326</IBAN>
      <BAKIYE>15000.50</BAKIYE>
      <DOVIZ>TRY</DOVIZ>
      <TIP>1</TIP>
    </CARI>
    <CARI>
      <CARI_KOD>NS002</CARI_KOD>
      <CARI_UNVANI>Netsis Tedarikci AS</CARI_UNVANI>
      <VKN_TCKN>9876543210</VKN_TCKN>
      <TIP>2</TIP>
    </CARI>
  </CARI_LIST>
  <FATURA_LIST>
    <FATURA>
      <FATURA_NUM>NS-F-001</FATURA_NUM>
      <CARI_KOD>NS001</CARI_KOD>
      <FATURA_TARIH>2026-05-15</FATURA_TARIH>
      <VADE_TARIH>2026-06-15</VADE_TARIH>
      <MAT_TOPLAM>10000.00</MAT_TOPLAM>
      <KDV_TOPLAM>1800.00</KDV_TOPLAM>
      <GENEL_TOP>11800.00</GENEL_TOP>
      <DOVIZ>TRY</DOVIZ>
      <FATURA_TIPI>1</FATURA_TIPI>
      <ACIK>Mayis donemi</ACIK>
    </FATURA>
    <FATURA>
      <FATURA_NUM>NS-F-002</FATURA_NUM>
      <CARI_KOD>NS002</CARI_KOD>
      <FATURA_TARIH>15.05.2026</FATURA_TARIH>
      <MAT_TOPLAM>5000</MAT_TOPLAM>
      <KDV_TOPLAM>900</KDV_TOPLAM>
      <GENEL_TOP>5900</GENEL_TOP>
      <FATURA_TIPI>2</FATURA_TIPI>
    </FATURA>
  </FATURA_LIST>
</NETSIS_EXPORT>
""".encode("utf-8")


class NetsisParseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.c = NetsisConnector()

    def test_parse_customers(self) -> None:
        r = self.c.parse(data=VALID_NETSIS_XML, mode=ConnectorMode.XML)
        self.assertEqual(len(r.customers), 2)
        c1 = r.customers[0]
        self.assertEqual(c1.source_code, "NS001")
        self.assertEqual(c1.tax_number, "1234567890")
        self.assertEqual(c1.role, "customer")  # TIP=1
        self.assertEqual(c1.balance, 15000.50)

    def test_parse_invoices(self) -> None:
        r = self.c.parse(data=VALID_NETSIS_XML, mode=ConnectorMode.XML)
        self.assertEqual(len(r.invoices), 2)
        inv = r.invoices[0]
        self.assertEqual(inv.source_no, "NS-F-001")
        self.assertEqual(inv.issue_date, "2026-05-15")
        self.assertEqual(inv.total_incl_tax, 11800.00)
        self.assertEqual(inv.direction, "outgoing")  # TIP=1

    def test_supplier_role_from_type2(self) -> None:
        r = self.c.parse(data=VALID_NETSIS_XML, mode=ConnectorMode.XML)
        self.assertEqual(r.customers[1].role, "supplier")

    def test_incoming_direction_from_type2(self) -> None:
        r = self.c.parse(data=VALID_NETSIS_XML, mode=ConnectorMode.XML)
        self.assertEqual(r.invoices[1].direction, "incoming")

    def test_tr_date_normalize(self) -> None:
        r = self.c.parse(data=VALID_NETSIS_XML, mode=ConnectorMode.XML)
        self.assertEqual(r.invoices[1].issue_date, "2026-05-15")

    def test_iban_clean(self) -> None:
        r = self.c.parse(data=VALID_NETSIS_XML, mode=ConnectorMode.XML)
        iban = r.customers[0].iban
        self.assertIsNotNone(iban)
        assert iban is not None
        self.assertNotIn(" ", iban)

    def test_summary_correct(self) -> None:
        r = self.c.parse(data=VALID_NETSIS_XML, mode=ConnectorMode.XML)
        self.assertEqual(r.summary["customers"], 2)
        self.assertEqual(r.summary["invoices"], 2)

    def test_signature_hash_differs_from_logo_and_mikro(self) -> None:
        r = self.c.parse(data=VALID_NETSIS_XML, mode=ConnectorMode.XML)
        # Aynı kayıt Logo veya Mikro'dan gelirse farklı hash olmalı
        sig = r.customers[0].signature_hash
        from app.connectors import LogoTigerConnector
        logo_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <LOGOWORLD>
          <CARI>
            <CARI_KODU>NS001</CARI_KODU>
            <CARI_UNVAN>Netsis Test Ticaret Ltd</CARI_UNVAN>
            <CARI_VKN>1234567890</CARI_VKN>
            <CARI_TIPI>1</CARI_TIPI>
          </CARI>
        </LOGOWORLD>""".encode("utf-8")
        logo_sig = LogoTigerConnector().parse(
            data=logo_xml, mode=ConnectorMode.XML,
        ).customers[0].signature_hash
        self.assertNotEqual(sig, logo_sig)

    def test_registry_returns_netsis(self) -> None:
        c = get_connector("netsis")
        self.assertIsInstance(c, NetsisConnector)
        self.assertEqual(c.connector_type, "netsis")

    def test_missing_field_raises(self) -> None:
        invalid = """<?xml version="1.0" encoding="UTF-8"?>
        <NETSIS_EXPORT>
          <CARI>
            <CARI_KOD>X</CARI_KOD>
            <!-- No UNVAN -->
          </CARI>
        </NETSIS_EXPORT>""".encode("utf-8")
        r = self.c.parse(data=invalid, mode=ConnectorMode.XML)
        self.assertEqual(len(r.customers), 0)
        self.assertEqual(len(r.errors), 1)

    def test_web_service_mode_raises(self) -> None:
        with self.assertRaises(NotImplementedError):
            self.c.parse(data=b"", mode=ConnectorMode.WEB_SERVICE)


if __name__ == "__main__":
    unittest.main()
