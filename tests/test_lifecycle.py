"""Automated tests for Entity Lifecycle State Transitions and Chronology.

Verifies Finite State Machine (FSM) rules for Fulfillments, Disputes, and Orders,
ensuring illegal transitions and temporal paradoxes are prohibited.
"""

from datetime import datetime, timedelta
import pytest
from src.services.fulfillment_engine import (
    FulfillmentEngine,
    InvalidFulfillmentTransitionError,
)
from src.database.connection import get_db


@pytest.fixture
def flf_engine():
    return FulfillmentEngine()


@pytest.fixture(scope="module")
def db():
    return get_db("data/sellerops.db")


def test_fulfillment_fsm_complete_happy_path(flf_engine):
    """Verify standard happy-path progression from ORDER_RECEIVED to DELIVERED."""
    base_dt = datetime(2026, 8, 1, 10, 0, 0)
    flf_id = "FUL-ORDLN-LIFE-01"

    # ORDER_RECEIVED -> PROCESSING
    t1 = flf_engine.transition_status(flf_id, "ORDER_RECEIVED", "PROCESSING", base_dt + timedelta(hours=2))
    assert t1["new_status"] == "PROCESSING"

    # PROCESSING -> PACKED
    t2 = flf_engine.transition_status(flf_id, "PROCESSING", "PACKED", base_dt + timedelta(hours=6))
    assert t2["new_status"] == "PACKED"

    # PACKED -> SHIPPED
    t3 = flf_engine.transition_status(flf_id, "PACKED", "SHIPPED", base_dt + timedelta(hours=18))
    assert t3["new_status"] == "SHIPPED"

    # SHIPPED -> OUT_FOR_DELIVERY
    t4 = flf_engine.transition_status(flf_id, "SHIPPED", "OUT_FOR_DELIVERY", base_dt + timedelta(days=2))
    assert t4["new_status"] == "OUT_FOR_DELIVERY"

    # OUT_FOR_DELIVERY -> DELIVERED
    t5 = flf_engine.transition_status(flf_id, "OUT_FOR_DELIVERY", "DELIVERED", base_dt + timedelta(days=3))
    assert t5["new_status"] == "DELIVERED"

    # DELIVERED -> RETURNED
    t6 = flf_engine.transition_status(flf_id, "DELIVERED", "RETURNED", base_dt + timedelta(days=7))
    assert t6["new_status"] == "RETURNED"


def test_illegal_cancellation_after_shipment(flf_engine):
    """An order line cannot be CANCELLED once it has entered SHIPPED status."""
    base_dt = datetime(2026, 8, 1, 10, 0, 0)
    flf_id = "FUL-ORDLN-LIFE-02"

    flf_engine.transition_status(flf_id, "ORDER_RECEIVED", "PROCESSING", base_dt + timedelta(hours=2))
    flf_engine.transition_status(flf_id, "PROCESSING", "PACKED", base_dt + timedelta(hours=4))
    flf_engine.transition_status(flf_id, "PACKED", "SHIPPED", base_dt + timedelta(hours=10))

    # Attempt direct cancellation after shipment
    with pytest.raises(InvalidFulfillmentTransitionError):
        flf_engine.transition_status(flf_id, "SHIPPED", "CANCELLED", base_dt + timedelta(hours=12))


def test_database_chronology_ordering(db):
    """
    Verify chronological validity across database records:
    dispatched_at <= delivered_at.
    """
    with db.session() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT fulfillment_id, dispatched_at, delivered_at
            FROM fulfillments
            WHERE dispatched_at IS NOT NULL 
              AND delivered_at IS NOT NULL
              AND dispatched_at > delivered_at;
            """
        )
        paradoxes = cursor.fetchall()
        assert len(paradoxes) == 0, f"Found fulfillment chronological paradoxes: {paradoxes}"
