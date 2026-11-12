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


# ==========================================
# MANDATORY INR FINANCIAL FIXTURE TESTS (SECTION 5)
# ==========================================

def test_inr_illustrative_payout_fixture(engines):
    """
    Mandatory Test Fixture 1: Exact Payout Calculation
    Seller order-line gross: ₹10,000.00 (1,000,000 paise)
    Assumed commission: 10% = ₹1,000.00 (100,000 paise)
    Approved refund: ₹500.00 (50,000 paise)
    Finalized lost dispute: ₹200.00 (20,000 paise)
    Post-deduction balance: ₹10,000 - ₹1,000 - ₹500 - ₹200 = ₹8,300.00
    New reserve hold: 5% of ₹8,300 = ₹415.00 (41,500 paise)
    Net payable: ₹8,300 - ₹415 = ₹7,885.00 (788,500 paise)
    """
    _, payout_engine = engines
    batch_dt = datetime(2026, 7, 10, 10, 0, 0)

    gross_paise = 1000000  # ₹10,000.00
    commission_paise = 100000  # ₹1,000.00 (10%)
    refund_paise = 50000  # ₹500.00
    dispute_paise = 20000  # ₹200.00
    reserve_paise = 41500  # ₹415.00 (5% of ₹8,300.00)

    expected_net_paise = gross_paise - commission_paise - refund_paise - dispute_paise - reserve_paise
    assert expected_net_paise == 788500  # ₹7,885.00

    items = [
        {
            "order_line_id": "ORDLN-INR-001",
            "gross_amount_cents": gross_paise,
            "commission_cents": commission_paise,
            "refund_cents": refund_paise,
            "dispute_cents": dispute_paise,
            "reserve_held_cents": reserve_paise,
        }
    ]

    res = payout_engine.create_payout_batch_cents(
        payout_id="PO-INR-001",
        seller_id="SELL-INR-01",
        batch_date=batch_dt,
        eligible_items=items,
        seller_status="ACTIVE",
    )

    header = res["header"]
    assert header["gross_sales_cents"] == 1000000
    assert header["commission_cents"] == 100000
    assert header["refunds_cents"] == 50000
    assert header["disputes_cents"] == 20000
    assert header["reserve_held_cents"] == 41500
    assert header["net_payout_cents"] == 788500  # Exactly ₹7,885.00
    assert header["reconciliation_status"] == "MATCHED"


def test_inr_reserve_release_added_only_once(engines):
    """
    Mandatory Test Fixture 2: Reserve Release
    Ensures previously held reserve amounts are added only once after their release date.
    """
    reserve_engine, payout_engine = engines
    deliv_dt = datetime(2026, 6, 1, 10, 0, 0)
    release_dt = deliv_dt + timedelta(days=14)
    batch_dt = release_dt + timedelta(days=1)

    # 1. Create reserve hold of ₹1,000.00 (100,000 paise)
    entry = reserve_engine.create_reserve_entry(
        order_line_id="ORDLN-INR-RSV-01",
        seller_id="SELL-INR-RSV",
        gross_amount_cents=1000000,
        seller_tier="STANDARD",
        risk_score=20.0,
        delivery_date=deliv_dt,
    )
    assert entry["status"] == "HELD"

    # 2. Release reserve on release date
    rel = reserve_engine.release_reserve(
        reserve_id_or_line_id=entry["reserve_id"],
        as_of_date=release_dt,
        seller_status="ACTIVE",
    )
    assert rel["status"] == "RELEASED"
    assert rel["released_amount_cents"] == 100000  # ₹1,000.00

    # 3. First payout disbursing the released reserve must succeed
    payout_1 = payout_engine.create_payout_batch_cents(
        payout_id="PO-RSV-REL-01",
        seller_id="SELL-INR-RSV",
        batch_date=batch_dt,
        eligible_items=[{
            "order_line_id": "ORDLN-INR-RSV-01",
            "gross_amount_cents": 0,
            "commission_cents": 0,
            "reserve_released_cents": 100000,
        }],
        seller_status="ACTIVE",
    )
    assert payout_1["header"]["reserve_released_cents"] == 100000
    assert payout_1["header"]["net_payout_cents"] == 100000

    # 4. Attempting to disburse the same released reserve in another payout must be blocked
    with pytest.raises(DuplicatePayoutLineError):
        payout_engine.create_payout_batch_cents(
            payout_id="PO-RSV-REL-02",
            seller_id="SELL-INR-RSV",
            batch_date=batch_dt + timedelta(days=7),
            eligible_items=[{
                "order_line_id": "ORDLN-INR-RSV-01",
                "gross_amount_cents": 0,
                "commission_cents": 0,
                "reserve_released_cents": 100000,
            }],
            seller_status="ACTIVE",
        )


def test_inr_partial_refund_deduction(engines):
    """
    Mandatory Test Fixture 3: Partial Refund Deduction
    Partial refund of ₹250.00 (25,000 paise) on a ₹5,000.00 (500,000 paise) line.
    """
    _, payout_engine = engines
    batch_dt = datetime(2026, 7, 10, 10, 0, 0)

    gross = 500000   # ₹5,000.00
    comm = 50000     # ₹500.00 (10%)
    partial_refund = 25000  # ₹250.00 (partial refund)
    reserve = 21250  # 5% of (5000 - 500 - 250 = 4250) = ₹212.50

    expected_net = gross - comm - partial_refund - reserve  # 403,750 paise (₹4,037.50)

    items = [
        {
            "order_line_id": "ORDLN-PART-01",
            "gross_amount_cents": gross,
            "commission_cents": comm,
            "refund_cents": partial_refund,
            "reserve_held_cents": reserve,
        }
    ]

    res = payout_engine.create_payout_batch_cents(
        payout_id="PO-PART-001",
        seller_id="SELL-INR-02",
        batch_date=batch_dt,
        eligible_items=items,
        seller_status="ACTIVE",
    )

    header = res["header"]
    assert header["gross_sales_cents"] == 500000
    assert header["refunds_cents"] == 25000
    assert header["net_payout_cents"] == expected_net
    assert header["reconciliation_status"] == "MATCHED"


def test_inr_multi_seller_order_payout_separation(engines):
    """
    Mandatory Test Fixture 4: Multiple Sellers in a Single Order
    Verifying that each seller receives only their own eligible financial amounts.
    Order total: ₹10,000.00
      - Seller A: ₹6,000.00 (Line 1) -> 10% comm (₹600) -> Net: ₹5,400.00
      - Seller B: ₹4,000.00 (Line 2) -> 12% comm (₹480) -> Net: ₹3,520.00
    """
    _, payout_engine = engines
    batch_dt = datetime(2026, 7, 10, 10, 0, 0)

    # Batch for Seller A
    batch_a = payout_engine.create_payout_batch_cents(
        payout_id="PO-SELLER-A",
        seller_id="SELL-AAA",
        batch_date=batch_dt,
        eligible_items=[{
            "order_line_id": "ORDLN-MULTI-01",
            "gross_amount_cents": 600000,
            "commission_cents": 60000,
        }],
        seller_status="ACTIVE",
    )

    # Batch for Seller B
    batch_b = payout_engine.create_payout_batch_cents(
        payout_id="PO-SELLER-B",
        seller_id="SELL-BBB",
        batch_date=batch_dt,
        eligible_items=[{
            "order_line_id": "ORDLN-MULTI-02",
            "gross_amount_cents": 400000,
            "commission_cents": 48000,
        }],
        seller_status="ACTIVE",
    )

    assert batch_a["header"]["seller_id"] == "SELL-AAA"
    assert batch_a["header"]["gross_sales_cents"] == 600000
    assert batch_a["header"]["net_payout_cents"] == 540000

    assert batch_b["header"]["seller_id"] == "SELL-BBB"
    assert batch_b["header"]["gross_sales_cents"] == 400000
    assert batch_b["header"]["net_payout_cents"] == 352000

    # Sum of gross across independent payouts equals total multi-seller order amount
    assert batch_a["header"]["gross_sales_cents"] + batch_b["header"]["gross_sales_cents"] == 1000000


def test_inr_finalized_dispute_deducted_exactly_once(engines):
    """
    Mandatory Test Fixture 5: Finalized Dispute Deducted Exactly Once
    Lost dispute of ₹1,500.00 must be deducted in the first eligible payout,
    and attempting to deduct the same dispute in another line raises DoubleDeductionError.
    """
    _, payout_engine = engines
    batch_dt = datetime(2026, 7, 10, 10, 0, 0)

    item1 = {
        "order_line_id": "ORDLN-DSP-01",
        "dispute_id": "DSP-INR-DED-01",
        "gross_amount_cents": 800000,
        "commission_cents": 80000,
        "dispute_cents": 150000,  # ₹1,500.00 finalized lost dispute
    }

    batch1 = payout_engine.create_payout_batch_cents(
        payout_id="PO-DSP-BATCH-01",
        seller_id="SELL-DISPUTE-01",
        batch_date=batch_dt,
        eligible_items=[item1],
        seller_status="ACTIVE",
    )
    assert batch1["header"]["disputes_cents"] == 150000
    assert batch1["header"]["net_payout_cents"] == 800000 - 80000 - 150000

    # Second batch attempting to deduct the same dispute ID raises DoubleDeductionError
    with pytest.raises(DoubleDeductionError):
        payout_engine.create_payout_batch_cents(
            payout_id="PO-DSP-BATCH-02",
            seller_id="SELL-DISPUTE-01",
            batch_date=batch_dt + timedelta(days=7),
            eligible_items=[{
                "order_line_id": "ORDLN-DSP-02",
                "dispute_id": "DSP-INR-DED-01",  # Same dispute ID
                "gross_amount_cents": 800000,
                "commission_cents": 80000,
                "dispute_cents": 150000,
            }],
            seller_status="ACTIVE",
        )
