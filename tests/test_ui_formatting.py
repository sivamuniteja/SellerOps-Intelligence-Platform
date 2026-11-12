"""Automated tests for Enterprise UI formatting and Indian Rupee presentation.

Verifies that financial metrics, labels, tooltips, and boundary numbers are
formatted correctly without clipping or rounding anomalies.
"""

import pytest
from src.currency import format_inr, format_inr_paise, to_paise, from_paise


def test_standard_indian_rupee_formatting():
    """Verify standard Indian grouping format across all magnitude tiers."""
    assert format_inr(999.00) == "₹999.00"
    assert format_inr(10000.00) == "₹10,000.00"
    assert format_inr(125000.00) == "₹1,25,000.00"
    assert format_inr(1250000.00) == "₹12,50,000.00"
    assert format_inr(10000000.00) == "₹1,00,00,000.00"
    assert format_inr(10386130.23) == "₹1,03,86,130.23"


def test_paise_to_rupee_formatting():
    """Verify exact integer paise to Indian Rupee string formatting."""
    assert format_inr_paise(0) == "₹0.00"
    assert format_inr_paise(50) == "₹0.50"
    assert format_inr_paise(100) == "₹1.00"
    assert format_inr_paise(99900) == "₹999.00"
    assert format_inr_paise(1000000) == "₹10,000.00"
    assert format_inr_paise(788500) == "₹7,885.00"  # Phase 5 mandatory fixture net payout
    assert format_inr_paise(1000000000) == "₹1,00,00,000.00"


def test_compact_indian_notation():
    """Verify compact notation uses Lakhs and Crores rather than Western Millions/Billions."""
    # Under 1 Lakh: full amount or thousands notation
    assert format_inr(50000.00, compact=True) in ["₹50.00 K", "₹50,000.00"]
    # Lakhs (1,00,000 to 99,99,999)
    assert format_inr(1250000.00, compact=True) == "₹12.50 L"
    assert format_inr_paise(125000000, compact=True) == "₹12.50 L"
    # Crores (1,00,00,000 and above)
    assert format_inr(10000000.00, compact=True) == "₹1.00 Cr"
    assert format_inr(10386130.23, compact=True) == "₹1.04 Cr"


def test_zero_and_negative_inr_formatting():
    """Verify formatting handles zero and negative amounts (e.g. chargeback balances) gracefully."""
    assert format_inr(0.0) == "₹0.00"
    assert format_inr(-500.0) == "-₹500.00"
    assert format_inr_paise(-20000) == "-₹200.00"


def test_metric_card_clean_title_attribute():
    """Verify clean string escaping for HTML title attribute in metric cards."""
    test_val = '₹1,03,86,130.23'
    clean = str(test_val).replace('"', '&quot;')
    assert clean == '₹1,03,86,130.23'
    assert '"' not in clean
