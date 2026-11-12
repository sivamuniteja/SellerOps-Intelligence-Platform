"""Test suite for reserve holds and payout eligibility."""

from datetime import datetime
import pytest
from src.config import load_config
from src.services.reserve_engine import ReserveEngine
from src.services.payout_engine import PayoutEngine


@pytest.fixture(scope="module")
def engines():
    config = load_config()
    return ReserveEngine(config), PayoutEngine(config)


def test_reserve_calculation_and_eligibility(engines):
    reserve_engine, payout_engine = engines
    deliv_dt = datetime(2026, 1, 1, 12, 0, 0)

    # Standard seller with low risk: 10% reserve, 14 days hold
    res = reserve_engine.calculate_reserve(100.00, "STANDARD", 20.0, deliv_dt)
    assert res["reserve_rate"] == 0.10
    assert res["reserve_amount"] == 10.00
    assert res["hold_days"] == 14

    # Payout eligibility
    eligible = payout_engine.evaluate_order_payout_eligibility(
        order_status="DELIVERED",
        reserve_released=True,
        seller_status="ACTIVE",
        has_unresolved_dispute=False,
    )
    assert eligible is True

    # Undelivered order must NOT be eligible
    ineligible_status = payout_engine.evaluate_order_payout_eligibility(
        order_status="SHIPPED",
        reserve_released=True,
        seller_status="ACTIVE",
    )
    assert ineligible_status is False

    # Suspended seller must NOT be eligible
    ineligible_suspended = payout_engine.evaluate_order_payout_eligibility(
        order_status="DELIVERED",
        reserve_released=True,
        seller_status="SUSPENDED",
    )
    assert ineligible_suspended is False
