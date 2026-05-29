"""G+3: Decimal precision tests — kuruş kaybı doğrulamaları.

IEEE 754 binary float'ın klasik tuzaklarına karşı koruma:
  - 0.1 + 0.2 ≠ 0.3 (float)  → tam 0.30 (Decimal)
  - 1234567.89 - 1234567.88 = 0.01 (her durumda)
  - 0.005 → 0.01 (banking ROUND_HALF_UP)

Bu testler enterprise-grade finansal precision'ın temelini doğrular.
"""
import unittest
from decimal import Decimal

from app.decimal_utils import (
    multiply_money,
    quantize_money,
    quantize_rate,
    sum_money,
    to_decimal,
    to_float_for_storage,
)


class DecimalUtilsTests(unittest.TestCase):
    # ── to_decimal ─────────────────────────────────────────────────────

    def test_to_decimal_handles_none(self) -> None:
        self.assertEqual(to_decimal(None), Decimal("0"))

    def test_to_decimal_from_float_avoids_binary_artifact(self) -> None:
        # Float 0.1 binary representation 0.10000000000000000555...
        # Decimal(0.1) → uzun decimal, ama Decimal(str(0.1)) → "0.1" tam
        result = to_decimal(0.1)
        self.assertEqual(result, Decimal("0.1"))

    def test_to_decimal_from_int(self) -> None:
        self.assertEqual(to_decimal(42), Decimal("42"))

    def test_to_decimal_from_str(self) -> None:
        self.assertEqual(to_decimal("1234.56"), Decimal("1234.56"))

    def test_to_decimal_passthrough(self) -> None:
        d = Decimal("9.99")
        self.assertIs(to_decimal(d), d)

    # ── Float arithmetic problemlerinin Decimal ile çözümü ────────────

    def test_classic_float_addition_bug_fixed(self) -> None:
        """0.1 + 0.2 = 0.30 (Decimal), 0.30000000000000004 (float)."""
        # Float bug
        self.assertNotEqual(0.1 + 0.2, 0.3)
        # Decimal fix
        self.assertEqual(sum_money([0.1, 0.2]), Decimal("0.30"))

    def test_classic_float_subtraction_bug_fixed(self) -> None:
        """1234567.89 - 1234567.88 = 0.01 (Decimal), float'ta yanlış."""
        d1 = to_decimal("1234567.89")
        d2 = to_decimal("1234567.88")
        # Float yanlış: ~0.010000000000048
        self.assertEqual(quantize_money(d1 - d2), Decimal("0.01"))

    def test_sum_many_small_amounts_precision(self) -> None:
        """1000 adet 0.01 = 10.00 (Decimal), float'ta drift olur."""
        result = sum_money([0.01] * 1000)
        self.assertEqual(result, Decimal("10.00"))

    def test_karma_holding_aggregate_no_kurus_loss(self) -> None:
        """Karma holding senaryosu: 4 şirket × milyonluk ledger entries."""
        # İnşaat: 1,400,000.33
        # Lojistik: 720,123.67
        # Gıda: 480,250.11
        # Tekstil: 200,789.45
        entries = [
            "1400000.33",
            "720123.67",
            "480250.11",
            "200789.45",
        ]
        result = sum_money(entries)
        # Exact: 2801163.56
        self.assertEqual(result, Decimal("2801163.56"))

    # ── quantize_money (banking ROUND_HALF_UP) ────────────────────────

    def test_quantize_money_round_half_up_positive(self) -> None:
        """0.005 → 0.01 (banking standard)."""
        self.assertEqual(quantize_money("0.005"), Decimal("0.01"))

    def test_quantize_money_round_half_up_negative(self) -> None:
        """-0.005 → -0.01."""
        self.assertEqual(quantize_money("-0.005"), Decimal("-0.01"))

    def test_quantize_money_truncates_to_two_places(self) -> None:
        self.assertEqual(quantize_money("123.456"), Decimal("123.46"))
        self.assertEqual(quantize_money("123.454"), Decimal("123.45"))

    def test_quantize_money_zero_pad(self) -> None:
        """0 → 0.00 (always 2 places)."""
        self.assertEqual(quantize_money(0), Decimal("0.00"))

    # ── quantize_rate (FX 4 decimal) ──────────────────────────────────

    def test_quantize_rate_four_places(self) -> None:
        self.assertEqual(quantize_rate("32.54321"), Decimal("32.5432"))

    # ── multiply_money (cross-currency) ───────────────────────────────

    def test_multiply_money_clean_result(self) -> None:
        """$50,000 × 32.5 TRY/USD = 1,625,000.00 (tam doğru)."""
        result = multiply_money(50000, 32.5)
        self.assertEqual(result, Decimal("1625000.00"))

    def test_multiply_money_with_fractional_rate(self) -> None:
        """1,000 EUR × 35.1234 TRY/EUR = 35,123.40."""
        result = multiply_money(1000, "35.1234")
        self.assertEqual(result, Decimal("35123.40"))

    def test_multiply_money_avoids_float_artifact(self) -> None:
        """3 × 0.1 float'ta 0.30000000000000004 olur, Decimal'da 0.30."""
        result = multiply_money(3, 0.1)
        self.assertEqual(result, Decimal("0.30"))

    # ── to_float_for_storage ──────────────────────────────────────────

    def test_to_float_for_storage_roundtrip(self) -> None:
        """Decimal → float → REAL kolonu storage."""
        result = to_float_for_storage(Decimal("1234.56"))
        self.assertEqual(result, 1234.56)
        self.assertIsInstance(result, float)

    def test_to_float_for_storage_quantizes(self) -> None:
        """123.456 → 123.46 (kuruş yuvarlama before storage)."""
        result = to_float_for_storage("123.456")
        self.assertEqual(result, 123.46)

    # ── sum_money empty + None handling ───────────────────────────────

    def test_sum_money_empty_returns_zero(self) -> None:
        self.assertEqual(sum_money([]), Decimal("0.00"))

    def test_sum_money_handles_none_in_list(self) -> None:
        """None values count as 0 (defensive — DB SUM may return None)."""
        self.assertEqual(sum_money([100, None, 200]), Decimal("300.00"))

    def test_sum_money_mixed_types(self) -> None:
        """int + float + str + Decimal hepsi karışık."""
        result = sum_money([100, 0.5, "50.25", Decimal("9.75")])
        self.assertEqual(result, Decimal("160.50"))


if __name__ == "__main__":
    unittest.main()
