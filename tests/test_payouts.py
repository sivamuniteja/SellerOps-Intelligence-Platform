"""Test suite for Reserve Engine (Engine B) and Payout Engine (Engine D)."""

from datetime import datetime, timedelta
import pytest
from src.config import load_config
from src.services.reserve_engine import (
    ReserveEngine,
    PrematureReserveReleaseError,
    SuspendedSellerReleaseError,
)
from src.services.payout_engine import (
    PayoutEngine,
    DuplicatePayoutLineError,
    DoubleDeductionError,
    InvalidPayoutStateTransitionError,
)


@pytest.fixture(scope="module")
def engines():
    config = load_config()
    return ReserveEngine(config), PayoutEngine(config)


# ==========================================
# RESERVE ENGINE TESTS (ENGINE B)
# ==========================================

def test_reserve_calculation_by_tier(engines):
    """Test standard vs enterprise reserve hold rates and durations."""
    reserve_engine, _ = engines
    deliv_dt = datetime(2026, 6, 1, 12, 0, 0)

    # Standard seller with normal risk (<= 65): 10% reserve, 14 days hold
    std_res = reserve_engine.calculate_reserve(100.00, "STANDARD", 20.0, deliv_dt)
    assert std_res["reserve_rate"] == 0.10
    assert std_res["reserve_amount"] == 10.00
    assert std_res["hold_days"] == 14
    assert std_res["release_date"] == deliv_dt + timedelta(days=14)

    # Enterprise seller: 5% reserve, 7 days hold
    ent_res = reserve_engine.calculate_reserve(100.00, "ENTERPRISE", 15.0, deliv_dt)
    assert ent_res["reserve_rate"] == 0.05
    assert ent_res["reserve_amount"] == 5.00
    assert ent_res["hold_days"] == 7
    assert ent_res["release_date"] == deliv_dt + timedelta(days=7)


def test_high_risk_reserve_surcharge(engines):
    """Sellers with risk score > 65 incur +5% reserve hold and +7 days hold duration."""
    reserve_engine, _ = engines
    deliv_dt = datetime(2026, 6, 1, 12, 0, 0)

    res = reserve_engine.calculate_reserve(100.00, "STANDARD", 75.0, deliv_dt)
    assert res["reserve_rate"] == 0.15  # 10% + 5%
    assert res["reserve_amount"] == 15.00
    assert res["hold_days"] == 21  # 14 + 7 days


def test_premature_reserve_release_blocked(engines):
    """Reserve engine must not release reserves prior to the configured hold window."""
    reserve_engine, _ = engines
    deliv_dt = datetime(2026, 6, 1, 10, 0, 0)

    entry = reserve_engine.create_reserve_entry(
        order_line_id="ORDLN-TEST-RSV-01",
        seller_id="SELL-000001",
        gross_amount_cents=10000,
        seller_tier="STANDARD",
        risk_score=20.0,
        delivery_date=deliv_dt,
    )
    assert entry["status"] == "HELD"

    # Attempting release on day 5 (before day 14) must raise PrematureReserveReleaseError
    day_5 = deliv_dt + timedelta(days=5)
    with pytest.raises(PrematureReserveReleaseError):
        reserve_engine.release_reserve(entry["reserve_id"], as_of_date=day_5, seller_status="ACTIVE")

    # Release on day 15 (after day 14) must succeed
    day_15 = deliv_dt + timedelta(days=15)
    released = reserve_engine.release_reserve(entry["reserve_id"], as_of_date=day_15, seller_status="ACTIVE")
    assert released["status"] == "RELEASED"
    assert released["released_amount_cents"] == 1000


def test_suspended_seller_reserve_release_blocked(engines):
    """Reserve release must be strictly blocked if seller is SUSPENDED."""
    reserve_engine, _ = engines
    deliv_dt = datetime(2026, 1, 1, 10, 0, 0)

    entry = reserve_engine.create_reserve_entry(
        order_line_id="ORDLN-TEST-RSV-02",
        seller_id="SELL-000002",
        gross_amount_cents=20000,
        seller_tier="STANDARD",
        risk_score=20.0,
        delivery_date=deliv_dt,
    )

    # Even after 60 days, suspended seller cannot release reserve
    day_60 = deliv_dt + timedelta(days=60)
    with pytest.raises(SuspendedSellerReleaseError):
        reserve_engine.release_reserve(entry["reserve_id"], as_of_date=day_60, seller_status="SUSPENDED")


def test_reserve_balance_tracking(engines):
    """Verify reserve creation, released reserve, and remaining reserve balance."""
    reserve_engine, _ = engines
    seller_id = "SELL-BAL-TEST"
    deliv_dt = datetime(2026, 6, 1, 10, 0, 0)

    e1 = reserve_engine.create_reserve_entry(
        order_line_id="ORDLN-BAL-01",
        seller_id=seller_id,
        gross_amount_cents=10000,  # 10% = 1000 cents
        seller_tier="STANDARD",
        risk_score=20.0,
        delivery_date=deliv_dt,
    )
    e2 = reserve_engine.create_reserve_entry(
        order_line_id="ORDLN-BAL-02",
        seller_id=seller_id,
        gross_amount_cents=20000,  # 10% = 2000 cents
        seller_tier="STANDARD",
        risk_score=20.0,
        delivery_date=deliv_dt,
    )

    # Balance before release: held = 3000, released = 0, remaining = 3000
    bal1 = reserve_engine.get_reserve_balance(seller_id)
    assert bal1["total_reserve_held_cents"] == 3000
    assert bal1["total_reserve_released_cents"] == 0
    assert bal1["remaining_reserve_cents"] == 3000

    # Release e1
    reserve_engine.release_reserve(e1["reserve_id"], as_of_date=deliv_dt + timedelta(days=20), seller_status="ACTIVE")

    # Balance after release: held = 3000, released = 1000, remaining = 2000
    bal2 = reserve_engine.get_reserve_balance(seller_id)
    assert bal2["total_reserve_held_cents"] == 3000
    assert bal2["total_reserve_released_cents"] == 1000
    assert bal2["remaining_reserve_cents"] == 2000


# ==========================================
# PAYOUT ENGINE TESTS (ENGINE D)
# ==========================================

def test_payout_eligibility_criteria(engines):
    """Test order settlement eligibility for payout inclusion."""
    _, payout_engine = engines

    # Delivered, reserve released, active seller, no dispute -> Eligible
    assert payout_engine.evaluate_order_payout_eligibility(
        order_status="DELIVERED",
        reserve_released=True,
        seller_status="ACTIVE",
        has_unresolved_dispute=False,
    ) is True

    # Undelivered -> Ineligible
    assert payout_engine.evaluate_order_payout_eligibility(
        order_status="SHIPPED",
        reserve_released=True,
        seller_status="ACTIVE",
    ) is False

    # Suspended seller -> Ineligible
    assert payout_engine.evaluate_order_payout_eligibility(
        order_status="DELIVERED",
        reserve_released=True,
        seller_status="SUSPENDED",
    ) is False

    # Unresolved dispute -> Ineligible
    assert payout_engine.evaluate_order_payout_eligibility(
        order_status="DELIVERED",
        reserve_released=True,
        seller_status="ACTIVE",
        has_unresolved_dispute=True,
    ) is False


def test_exact_net_payable_formula(engines):
    """
    Net Payable = Gross - Commission - Refunds - Disputes - Reserve Held + Previously Eligible Reserve Releases.
    """
    _, payout_engine = engines

    gross = 10000       # $100.00
    commission = 830    # $8.30
    refunds = 500       # $5.00
    disputes = 1200     # $12.00
    reserve_held = 1000 # $10.00
    reserve_released = 1000 # $10.00

    # Expected: 10000 - 830 - 500 - 1200 - 1000 + 1000 = 7470 ($74.70)
    net = payout_engine.calculate_net_payable_cents(
        gross_cents=gross,
        commission_cents=commission,
        refunds_cents=refunds,
        dispute_cents=disputes,
        reserve_held_cents=reserve_held,
        reserve_released_cents=reserve_released,
    )
    assert net == 7470


def test_duplicate_payout_line_prevention(engines):
    """Payout engine must prevent duplicate payout lines for the same order line."""
    _, payout_engine = engines
    batch_dt = datetime(2026, 7, 1, 10, 0, 0)

    items = [
        {
            "order_line_id": "ORDLN-DUP-001",
            "order_id": "ORD-DUP-001",
            "gross_amount_cents": 5000,
            "commission_cents": 400,
            "reserve_held_cents": 500,
            "reserve_released_cents": 500,
        }
    ]

    # First batch disbursement succeeds
    res1 = payout_engine.create_payout_batch_cents(
        payout_id="PO-TEST-001",
        seller_id="SELL-000001",
        batch_date=batch_dt,
        eligible_items=items,
        seller_status="ACTIVE",
    )
    assert res1["header"]["status"] == "PAID"
    assert res1["header"]["net_payout_cents"] == 4600

    # Second batch attempting to disburse the same order line must fail
    with pytest.raises(DuplicatePayoutLineError):
        payout_engine.create_payout_batch_cents(
            payout_id="PO-TEST-002",
            seller_id="SELL-000001",
            batch_date=batch_dt,
            eligible_items=items,
            seller_status="ACTIVE",
        )


def test_avoid_double_deductions(engines):
    """Payout engine must raise DoubleDeductionError if a dispute is deducted multiple times."""
    _, payout_engine = engines
    batch_dt = datetime(2026, 7, 1, 10, 0, 0)

    items1 = [
        {
            "order_line_id": "ORDLN-DED-001",
            "dispute_id": "DSP-DED-001",
            "gross_amount_cents": 10000,
            "commission_cents": 830,
            "dispute_cents": 2500,
        }
    ]
    payout_engine.create_payout_batch_cents(
        payout_id="PO-TEST-003",
        seller_id="SELL-000001",
        batch_date=batch_dt,
        eligible_items=items1,
        seller_status="ACTIVE",
    )

    items2 = [
        {
            "order_line_id": "ORDLN-DED-002",
            "dispute_id": "DSP-DED-001",  # Same dispute ID
            "gross_amount_cents": 10000,
            "commission_cents": 830,
            "dispute_cents": 2500,
        }
    ]
    with pytest.raises(DoubleDeductionError):
        payout_engine.create_payout_batch_cents(
            payout_id="PO-TEST-004",
            seller_id="SELL-000001",
            batch_date=batch_dt,
            eligible_items=items2,
            seller_status="ACTIVE",
        )


def test_payout_threshold_held_status(engines):
    """If net payout is below $25.00 (2500 cents), status must be HELD."""
    _, payout_engine = engines
    batch_dt = datetime(2026, 7, 1, 10, 0, 0)

    # Net: 2000 - 300 = 1700 cents ($17.00 < $25.00 min threshold)
    items = [
        {
            "order_line_id": "ORDLN-LOW-001",
            "gross_amount_cents": 2000,
            "commission_cents": 300,
        }
    ]
    res = payout_engine.create_payout_batch_cents(
        payout_id="PO-TEST-005",
        seller_id="SELL-000001",
        batch_date=batch_dt,
        eligible_items=items,
        seller_status="ACTIVE",
    )
    assert res["header"]["status"] == "HELD"


def test_payout_state_transitions(engines):
    """Verify valid and invalid payout lifecycle status transitions."""
    _, payout_engine = engines
    occ_dt = datetime(2026, 7, 1, 12, 0, 0)

    # Valid transition: PROCESSING -> PAID
    evt = payout_engine.transition_payout_status(
        payout_id="PO-TRANS-01",
        current_status="PROCESSING",
        next_status="PAID",
        occurred_at=occ_dt,
    )
    assert evt["new_status"] == "PAID"

    # Invalid transition: PAID -> PROCESSING (PAID is terminal)
    with pytest.raises(InvalidPayoutStateTransitionError):
        payout_engine.transition_payout_status(
            payout_id="PO-TRANS-01",
            current_status="PAID",
            next_status="PROCESSING",
            occurred_at=occ_dt,
        )
