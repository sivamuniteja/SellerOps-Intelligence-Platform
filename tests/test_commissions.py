"""Test suite for commission and fee calculation engine."""

import pytest
from src.config import load_config
from src.services.commission_engine import CommissionEngine


@pytest.fixture(scope="module")
def commission_engine():
    config = load_config()
    return CommissionEngine(config)


def test_standard_category_commission(commission_engine):
    # Electronics base: 8%, Standard tier discount: 0% -> 8%
    # Gross: $100.00 -> variable: $8.00, fixed fee: $0.30 -> total: $8.30
    res = commission_engine.calculate_commission(100.00, "Electronics", "STANDARD")
    assert res["effective_rate"] == 0.08
    assert res["variable_commission"] == 8.00
    assert res["fixed_fee"] == 0.30
    assert res["total_commission"] == 8.30


def test_enterprise_tier_commission_discount(commission_engine):
    # Electronics base: 8%, Enterprise tier discount: 2% -> effective rate: 6%
    # Gross: $100.00 -> variable: $6.00, fixed fee: $0.30 -> total: $6.30
    res = commission_engine.calculate_commission(100.00, "Electronics", "ENTERPRISE")
    assert res["effective_rate"] == 0.06
    assert res["variable_commission"] == 6.00
    assert res["total_commission"] == 6.30


def test_minimum_commission_floor(commission_engine):
    # Gross: $2.00, Electronics rate: 8% -> 0.16 -> floors to min $0.50 + $0.30 fee = $0.80
    res = commission_engine.calculate_commission(2.00, "Electronics", "STANDARD")
    assert res["variable_commission"] == 0.50
    assert res["total_commission"] == 0.80
