"""Automated unit and integration tests for Reserve Engine.

Verifies tier-based reserve calculations, high-risk surcharges, hold window timing,
premature release blocking, suspended seller protection, and balance tracking.
"""

from datetime import datetime, timedelta
import pytest
from src.services.reserve_engine import (
    ReserveEngine,
    PrematureReserveReleaseError,
    SuspendedSellerReleaseError,
    ReserveNotFoundError,
)


@pytest.fixture
def engine():
    return ReserveEngine()


def test_tier_reserve_calculations(engine):
    """Verify tier reserve percentages and hold days."""
    deliv_dt = datetime(2026, 6, 1, 10, 0, 0)
    gross_paise = 1000000  # ₹10,000.00

    # Enterprise: 5%, 7 days
    ent = engine.calculate_reserve_cents(gross_paise, "ENTERPRISE", 20.0, deliv_dt)
    assert ent["reserve_rate"] == 0.05
    assert ent["reserve_amount_cents"] == 50000  # ₹500.00
    assert ent["hold_days"] == 7

    # Preferred: 8%, 14 days
    pref = engine.calculate_reserve_cents(gross_paise, "PREFERRED", 20.0, deliv_dt)
    assert pref["reserve_rate"] == 0.08
    assert pref["reserve_amount_cents"] == 80000  # ₹800.00
    assert pref["hold_days"] == 14

    # Standard: 10%, 14 days
    std = engine.calculate_reserve_cents(gross_paise, "STANDARD", 20.0, deliv_dt)
    assert std["reserve_rate"] == 0.10
    assert std["reserve_amount_cents"] == 100000  # ₹1,000.00
    assert std["hold_days"] == 14

    # Probation: 20%, 30 days
    prob = engine.calculate_reserve_cents(gross_paise, "PROBATION", 20.0, deliv_dt)
    assert prob["reserve_rate"] == 0.20
    assert prob["reserve_amount_cents"] == 200000  # ₹2,000.00
    assert prob["hold_days"] == 30


def test_high_risk_surcharge_application(engine):
    """Risk score > 65 triggers +5% reserve surcharge and +7 days hold window."""
    deliv_dt = datetime(2026, 6, 1, 10, 0, 0)
    gross_paise = 1000000  # ₹10,000.00

    # Standard tier (normal 10%, 14 days) with risk score 75.0 -> 15%, 21 days
    high_risk = engine.calculate_reserve_cents(gross_paise, "STANDARD", 75.0, deliv_dt)
    assert high_risk["reserve_rate"] == 0.15
    assert high_risk["reserve_amount_cents"] == 150000  # ₹1,500.00
    assert high_risk["hold_days"] == 21


def test_premature_release_protection(engine):
    """Releasing held reserves prior to hold_release_date must raise PrematureReserveReleaseError."""
    deliv_dt = datetime(2026, 6, 1, 10, 0, 0)
    entry = engine.create_reserve_entry(
        order_line_id="ORDLN-PRV-001",
        seller_id="SELL-000001",
        gross_amount_cents=1000000,
        seller_tier="STANDARD",
        risk_score=20.0,
        delivery_date=deliv_dt,
    )
    assert entry["status"] == "HELD"

    # Attempt release 5 days later (before 14-day hold elapses)
    attempt_dt = deliv_dt + timedelta(days=5)
    with pytest.raises(PrematureReserveReleaseError):
        engine.release_reserve(
            reserve_id_or_line_id=entry["reserve_id"],
            as_of_date=attempt_dt,
            seller_status="ACTIVE",
        )


def test_suspended_seller_protection(engine):
    """Attempting reserve release for a SUSPENDED seller must raise SuspendedSellerReleaseError."""
    deliv_dt = datetime(2026, 6, 1, 10, 0, 0)
    entry = engine.create_reserve_entry(
        order_line_id="ORDLN-PRV-002",
        seller_id="SELL-000002",
        gross_amount_cents=1000000,
        seller_tier="STANDARD",
        risk_score=20.0,
        delivery_date=deliv_dt,
    )

    # Mature release date reached, but seller is SUSPENDED
    release_dt = deliv_dt + timedelta(days=20)
    with pytest.raises(SuspendedSellerReleaseError):
        engine.release_reserve(
            reserve_id_or_line_id=entry["reserve_id"],
            as_of_date=release_dt,
            seller_status="SUSPENDED",
        )


def test_reserve_balance_tracking(engine):
    """Remaining reserve balance must equal total held minus total released."""
    deliv_dt = datetime(2026, 6, 1, 10, 0, 0)
    entry = engine.create_reserve_entry(
        order_line_id="ORDLN-PRV-003",
        seller_id="SELL-000003",
        gross_amount_cents=1000000,
        seller_tier="STANDARD",
        risk_score=20.0,
        delivery_date=deliv_dt,
    )

    balance_initial = engine.get_reserve_balance("SELL-000003")
    assert balance_initial["total_reserve_held_cents"] == 100000
    assert balance_initial["remaining_reserve_cents"] == 100000
    assert balance_initial["total_reserve_released_cents"] == 0

    # Release after maturity
    release_dt = deliv_dt + timedelta(days=15)
    engine.release_reserve(
        reserve_id_or_line_id=entry["reserve_id"],
        as_of_date=release_dt,
        seller_status="ACTIVE",
    )

    balance_post = engine.get_reserve_balance("SELL-000003")
    assert balance_post["total_reserve_held_cents"] == 100000
    assert balance_post["total_reserve_released_cents"] == 100000
    assert balance_post["remaining_reserve_cents"] == 0
