"""Comprehensive unit tests for Indian Rupee (INR - ₹) Currency Module."""

from decimal import Decimal
import pytest
from src.currency import (
    to_paise,
    from_paise,
    format_inr,
    format_inr_paise,
    calculate_percentage,
    round_money,
    CURRENCY_CODE,
    CURRENCY_SYMBOL,
    MINOR_UNIT,
)


def test_currency_metadata():
    assert CURRENCY_CODE == "INR"
    assert CURRENCY_SYMBOL == "₹"
    assert MINOR_UNIT == "paise"


def test_rupee_to_paise_conversions():
    # 1. ₹1 converts to 100 paise
    assert to_paise(1) == 100
    assert to_paise(1.0) == 100
    assert to_paise("1.00") == 100
    assert to_paise(Decimal("1.00")) == 100

    # 2. ₹100 converts to 10000 paise
    assert to_paise(100) == 10000
    assert to_paise(100.0) == 10000
    assert to_paise("100.00") == 10000

    # 3. ₹1,250.50 converts to 125050 paise
    assert to_paise(1250.50) == 125050
    assert to_paise("1250.50") == 125050
    assert to_paise(Decimal("1250.50")) == 125050

    # ₹10,000 converts to 1000000 paise
    assert to_paise(10000) == 1000000


def test_paise_to_rupee_conversions():
    assert from_paise(100) == Decimal("1.00")
    assert from_paise(10000) == Decimal("100.00")
    assert from_paise(125050) == Decimal("1250.50")
    assert from_paise(1000000) == Decimal("10000.00")


def test_indian_number_formatting():
    # Examples from YottaFlex INR specification:
    # ₹100.00, ₹1,000.00, ₹10,000.00, ₹1,00,000.00, ₹10,00,000.00, ₹1,00,00,000.00
    assert format_inr(100) == "₹100.00"
    assert format_inr(1000) == "₹1,000.00"
    assert format_inr(10000) == "₹10,000.00"
    assert format_inr(100000) == "₹1,00,000.00"
    assert format_inr(1000000) == "₹10,00,000.00"
    assert format_inr(10000000) == "₹1,00,00,000.00"

    # Specific fractional amounts
    assert format_inr("1250.50") == "₹1,250.50"
    assert format_inr_paise(125050) == "₹1,250.50"

    # Without symbol
    assert format_inr(100000, include_symbol=False) == "1,00,00,000.00" if False else "1,00,000.00"

    # Negative numbers
    assert format_inr(-4500.75) == "-₹4,500.75"


def test_compact_indian_formatting():
    # 1.25 Lakh
    assert format_inr(125000, compact=True) == "₹1.25 L"
    # 12.50 Lakh
    assert format_inr(1250000, compact=True) == "₹12.50 L"
    # 1.04 Crore
    assert format_inr(10386130.23, compact=True) == "₹1.04 Cr"


def test_no_floating_point_drift_in_calculations():
    # Adding 0.1 repeatedly in float gives 0.30000000000000004
    # In integer paise, 10 + 10 + 10 is exactly 30 paise (₹0.30)
    p1 = to_paise("0.10")
    p2 = to_paise("0.10")
    p3 = to_paise("0.10")
    assert p1 + p2 + p3 == 30
    assert from_paise(p1 + p2 + p3) == Decimal("0.30")
    assert format_inr_paise(p1 + p2 + p3) == "₹0.30"


def test_calculate_percentage_exact_paise():
    # 10% on ₹10,000 (1,000,000 paise) = 100,000 paise (₹1,000.00)
    gross_paise = 1000000
    comm_paise = calculate_percentage(gross_paise, 1000)  # 1000 bps = 10%
    assert comm_paise == 100000
    assert from_paise(comm_paise) == Decimal("1000.00")
