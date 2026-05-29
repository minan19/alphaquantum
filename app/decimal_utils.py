"""G+3: Decimal precision utilities — kuruş kaybı sıfır.

## Problem

Python float (IEEE 754 double):
  >>> 0.1 + 0.2
  0.30000000000000004
  >>> 1234567.89 - 1234567.88
  0.010000000000048022

Karma sektörlü holding'in 4 şirketinden gelen milyonluk ledger entries
toplanırken bu hatalar **kuruş kaybına** dönüşür. Bir kuruş kayıp =
müşteri güveni kaybı = enterprise pozisyondan kayıp.

## Bu modül

Decimal-aware finansal hesaplama altyapısı:
  - to_decimal(): float/int/str → Decimal (REAL kolon değerlerini parse eder)
  - quantize_money(): TRY/FX için kuruş yuvarlama (ROUND_HALF_UP — Türk Lirası bankacılık standardı)
  - sum_money(): Decimal toplama (float toplama yerine)
  - to_float_for_storage(): Decimal → float (REAL kolon'a sakla)

## Mimari karar

Schema (REAL kolon) geriye uyumlu kalır. **Python tarafı Decimal yapar**:
hesaplama Decimal, storage float (round_half_up ile 2 ondalık).

PostgreSQL geçişinde NUMERIC(20,4) kolon olur, decimal_utils ile birlikte
otomatik uyumlu — `to_float_for_storage()` `to_decimal_for_storage()` ile
swap olur, geri kalan kod değişmez.

## Banking standardı

ROUND_HALF_UP: 0.5 → 1, -0.5 → -1 (yarıyı yukarı yuvarla).
Bankers' rounding (ROUND_HALF_EVEN) finansal standartlarda da kullanılır,
ama TR muhasebe uygulamasında ROUND_HALF_UP yaygındır (KDV faturalandırma,
e-fatura GİB doğrulama). KDV mahsubu hesaplamalarında ROUND_HALF_UP zorunlu.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Iterable


# Decimal context: precision 28 (default), karma holding milyar TL'ye dayanır
# Ana hesaplama 28 hane precision'ında, sonuçta 2 hane'ye round
getcontext().prec = 28

# Para birimi için kuruş precision (2 ondalık)
TWO_PLACES = Decimal("0.01")

# Cross-currency hesaplama için 4 ondalık (örn. FX rate × amount)
FOUR_PLACES = Decimal("0.0001")


def to_decimal(value: float | int | str | Decimal | None) -> Decimal:
    """Convert any numeric input → Decimal, defensively.

    - None → Decimal("0")
    - float → str dönüştür → Decimal (binary float artifact'ından kaçın)
    - int/str → doğrudan Decimal
    - Decimal → identity

    str konversiyon kritik: Decimal(0.1) = Decimal('0.10000000000...') ama
    Decimal(str(0.1)) = Decimal('0.1') (Python str'da float artifact yuvarlanır).
    """
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(value)


def quantize_money(value: Decimal | float | int | str) -> Decimal:
    """Round to 2 decimal places (kuruş precision) — ROUND_HALF_UP.

    Banking standard: 0.005 → 0.01, -0.005 → -0.01. TR muhasebe + KDV
    faturalandırma için doğru kural.
    """
    d = to_decimal(value)
    return d.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def quantize_rate(value: Decimal | float | int | str) -> Decimal:
    """Round to 4 decimal places (FX rate precision)."""
    d = to_decimal(value)
    return d.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def sum_money(values: Iterable[Decimal | float | int | str | None]) -> Decimal:
    """Decimal-aware sum.

    >>> sum_money([0.1, 0.2])  # Float toplama 0.30000000000000004
    Decimal('0.30')              # Decimal toplama tam doğru

    Kullanım: ConsolidationEngine'da gross_total_income, GroupFXEngine'da
    total_long_try, BalanceService'da company_balance hesaplamaları.
    """
    total = Decimal("0")
    for v in values:
        total += to_decimal(v)
    return quantize_money(total)


def to_float_for_storage(value: Decimal | float | int | str) -> float:
    """Convert Decimal → float for REAL column storage.

    SQLite REAL kolonu float bekler. PostgreSQL geçişinde bu fonksiyonun
    yerine to_decimal_for_storage() gelir (NUMERIC kolonu Decimal alır).
    """
    return float(quantize_money(value))


def multiply_money(
    amount: Decimal | float | int | str,
    rate: Decimal | float | int | str,
) -> Decimal:
    """Cross-currency conversion: amount × rate, kuruş precision.

    Örnek: $50,000 USD × 32.5 TRY/USD = 1,625,000.00 TRY (tam doğru)
    Float: 50000 * 32.5 = 1625000.0000000002 (binary artifact)
    """
    a = to_decimal(amount)
    r = to_decimal(rate)
    return quantize_money(a * r)
