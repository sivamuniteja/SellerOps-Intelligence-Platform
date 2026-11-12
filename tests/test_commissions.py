"""Test suite for commission and fee calculation engine (Engine A)."""

from datetime import datetime
import pytest
from src.config import load_config
from src.services.commission_engine import (
    CommissionEngine,
    DuplicateCommissionError,
    RuleNotFoundError,
)


@pytest.fixture(scope="module")
def commission_engine():
    config = load_config()
    return CommissionEngine(config)


def test_standard_category_commission(commission_engine):
    """Electronics base: 8%, Standard tier discount: 0% -> 8%."""
    res = commission_engine.calculate_commission(100.00, "Electronics", "STANDARD")
    assert res["effective_rate"] == 0.08
    assert res["variable_commission"] == 8.00
    assert res["fixed_fee"] == 0.30
    assert res["total_commission"] == 8.30
    assert res["total_commission_cents"] == 830


def test_enterprise_tier_commission_discount(commission_engine):
    """Electronics base: 8%, Enterprise tier discount: 2% -> effective rate: 6%."""
    res = commission_engine.calculate_commission(100.00, "Electronics", "ENTERPRISE")
    assert res["effective_rate"] == 0.06
    assert res["variable_commission"] == 6.00
    assert res["fixed_fee"] == 0.30
    assert res["total_commission"] == 6.30
    assert res["total_commission_cents"] == 630


def test_minimum_commission_floor(commission_engine):
    """Gross: $2.00, Electronics rate: 8% -> 0.16 -> floors to min $0.50 + $0.30 fee = $0.80."""
    res = commission_engine.calculate_commission(2.00, "Electronics", "STANDARD")
    assert res["variable_commission"] == 0.50
    assert res["fixed_fee"] == 0.30
    assert res["total_commission"] == 0.80
    assert res["total_commission_cents"] == 80


def test_exact_integer_cents_calculation(commission_engine):
    """Test integer cents exact math for Fashion ($54.32 = 5432 cents at 15%)."""
    # 5432 * 1500 // 10000 = 814 cents ($8.14) + 30 cents fixed fee = 844 cents ($8.44)
    res = commission_engine.calculate_commission_cents(5432, "Fashion & Apparel", "STANDARD")
    assert res["rate_basis_points"] == 1500
    assert res["variable_commission_cents"] == 814
    assert res["fixed_fee_cents"] == 30
    assert res["total_commission_cents"] == 844


def test_effective_dated_rule_matching():
    """Test matching rules by effective dates."""
    rules = [
        {
            "rule_id": "RULE-SUMMER-2026",
            "category": "Electronics",
            "tier": "STANDARD",
            "base_rate": 0.05,
            "discount_rate": 0.0,
            "fixed_fee_cents": 25,
            "min_commission_cents": 40,
            "effective_from": "2026-06-01",
            "effective_to": "2026-08-31",
        },
        {
            "rule_id": "RULE-FALL-2026",
            "category": "Electronics",
            "tier": "STANDARD",
            "base_rate": 0.09,
            "discount_rate": 0.0,
            "fixed_fee_cents": 35,
            "min_commission_cents": 50,
            "effective_from": "2026-09-01",
            "effective_to": "2026-11-30",
        },
    ]
    engine = CommissionEngine(rules=rules)

    # Date in summer promo window
    summer_res = engine.calculate_commission(
        100.00, "Electronics", "STANDARD", transaction_date="2026-07-15"
    )
    assert summer_res["rule_id"] == "RULE-SUMMER-2026"
    assert summer_res["effective_rate"] == 0.05
    assert summer_res["fixed_fee"] == 0.25
    assert summer_res["total_commission"] == 5.25

    # Date in fall window
    fall_res = engine.calculate_commission(
        100.00, "Electronics", "STANDARD", transaction_date="2026-10-01"
    )
    assert fall_res["rule_id"] == "RULE-FALL-2026"
    assert fall_res["effective_rate"] == 0.09
    assert summer_res["total_commission"] != fall_res["total_commission"]


def test_prevent_duplicate_commission(commission_engine):
    """Engine must raise DuplicateCommissionError when an order line is submitted twice."""
    engine = CommissionEngine()

    # First record succeeds
    entry1 = engine.record_commission_ledger_entry(
        order_line_id="ORDLN-TEST-0001",
        order_id="ORD-TEST-0001",
        seller_id="SELL-000001",
        gross_amount_cents=10000,
        category="Electronics",
        seller_tier="STANDARD",
        transaction_date="2026-05-01 10:00:00",
    )
    assert entry1["ledger_id"].startswith("CML-")
    assert entry1["total_commission_cents"] == 830

    # Second record with same order_line_id must raise DuplicateCommissionError
    with pytest.raises(DuplicateCommissionError) as exc_info:
        engine.record_commission_ledger_entry(
            order_line_id="ORDLN-TEST-0001",
            order_id="ORD-TEST-0001",
            seller_id="SELL-000001",
            gross_amount_cents=10000,
            category="Electronics",
            seller_tier="STANDARD",
            transaction_date="2026-05-01 10:00:00",
        )
    assert "Duplicate fee application prevented" in str(exc_info.value)
