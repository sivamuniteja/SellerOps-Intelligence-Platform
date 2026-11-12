"""Test suite for Fulfillment Lifecycle and SLA Engine (Engine C)."""

from datetime import datetime, timedelta
import pytest
from src.config import load_config
from src.services.fulfillment_engine import (
    FulfillmentEngine,
    InvalidFulfillmentTransitionError,
)


@pytest.fixture(scope="module")
def fulfillment_engine():
    config = load_config()
    return FulfillmentEngine(config)


def test_valid_fulfillment_state_flow(fulfillment_engine):
    """Test valid end-to-end lifecycle progression: ORDER_RECEIVED -> PROCESSING -> PACKED -> SHIPPED -> OUT_FOR_DELIVERY -> DELIVERED."""
    states = [
        "ORDER_RECEIVED",
        "PROCESSING",
        "PACKED",
        "SHIPPED",
        "OUT_FOR_DELIVERY",
        "DELIVERED",
    ]

    for i in range(len(states) - 1):
        curr, nxt = states[i], states[i + 1]
        assert fulfillment_engine.is_valid_transition(curr, nxt) is True


def test_order_cancellation_allowed_states(fulfillment_engine):
    """Cancellation is allowed from early processing states but NOT after shipment."""
    assert fulfillment_engine.is_valid_transition("ORDER_RECEIVED", "CANCELLED") is True
    assert fulfillment_engine.is_valid_transition("PROCESSING", "CANCELLED") is True
    assert fulfillment_engine.is_valid_transition("PACKED", "CANCELLED") is True

    # After shipment or delivery, direct cancellation is illegal
    assert fulfillment_engine.is_valid_transition("SHIPPED", "CANCELLED") is False
    assert fulfillment_engine.is_valid_transition("DELIVERED", "CANCELLED") is False


def test_delivered_can_transition_to_returned(fulfillment_engine):
    """A delivered item can be returned."""
    assert fulfillment_engine.is_valid_transition("DELIVERED", "RETURNED") is True
    assert fulfillment_engine.is_valid_transition("RETURNED", "DELIVERED") is False


def test_invalid_state_transition_raises_error(fulfillment_engine):
    """Illegal transitions must raise InvalidFulfillmentTransitionError."""
    occ_dt = datetime(2026, 6, 1, 10, 0, 0)

    # Cannot transition from DELIVERED to PROCESSING
    with pytest.raises(InvalidFulfillmentTransitionError):
        fulfillment_engine.transition_status(
            fulfillment_id="FUL-TEST-001",
            current_state="DELIVERED",
            next_state="PROCESSING",
            occurred_at=occ_dt,
        )

    # Cannot transition from CANCELLED to SHIPPED
    with pytest.raises(InvalidFulfillmentTransitionError):
        fulfillment_engine.transition_status(
            fulfillment_id="FUL-TEST-002",
            current_state="CANCELLED",
            next_state="SHIPPED",
            occurred_at=occ_dt,
        )


def test_sla_dispatch_evaluation(fulfillment_engine):
    """Dispatch within 48h SLA window is ON_TIME; dispatch after 48h is LATE."""
    order_dt = datetime(2026, 6, 1, 10, 0, 0)

    # Dispatched in 24 hours (on-time)
    disp_24h = order_dt + timedelta(hours=24)
    deliv_dt = disp_24h + timedelta(days=2)
    res_on_time = fulfillment_engine.evaluate_sla(order_dt, disp_24h, deliv_dt)
    assert res_on_time["sla_status"] == "ON_TIME"
    assert res_on_time["is_late"] is False
    assert res_on_time["is_on_time"] is True
    assert res_on_time["sla_breached"] is False
    assert res_on_time["dispatch_delay_hours"] == 24.0

    # Dispatched in 72 hours (late - exceeds 48h threshold)
    disp_72h = order_dt + timedelta(hours=72)
    res_late = fulfillment_engine.evaluate_sla(order_dt, disp_72h, deliv_dt)
    assert res_late["sla_status"] == "LATE"
    assert res_late["is_late"] is True
    assert res_late["is_on_time"] is False
    assert res_late["sla_breached"] is True
    assert res_late["dispatch_delay_hours"] == 72.0


def test_delay_calculations(fulfillment_engine):
    """Test delay hours calculations against expected timestamps."""
    order_dt = datetime(2026, 6, 1, 10, 0, 0)
    exp_ship = order_dt + timedelta(hours=48)
    actual_ship = order_dt + timedelta(hours=60)  # 12 hours late

    exp_deliv = actual_ship + timedelta(days=3)
    actual_deliv = exp_deliv + timedelta(hours=8)  # 8 hours late

    delays = fulfillment_engine.calculate_delays(
        order_date=order_dt,
        expected_shipment_date=exp_ship,
        actual_shipment_date=actual_ship,
        expected_delivery_date=exp_deliv,
        actual_delivery_date=actual_deliv,
    )
    assert delays["shipment_delay_hours"] == 12.0
    assert delays["delivery_delay_hours"] == 8.0
    assert delays["is_on_time_shipment"] is False
    assert delays["is_on_time_delivery"] is False
    assert delays["sla_breached"] is True


def test_preserve_event_history(fulfillment_engine):
    """Event history must record every transition immutably."""
    flf_id = "FUL-HIST-TEST"
    t1 = datetime(2026, 6, 1, 10, 0, 0)
    t2 = datetime(2026, 6, 1, 14, 0, 0)

    e1 = fulfillment_engine.transition_status(flf_id, "ORDER_RECEIVED", "PROCESSING", t1)
    e2 = fulfillment_engine.transition_status(flf_id, "PROCESSING", "PACKED", t2)

    events = fulfillment_engine.get_fulfillment_events(flf_id)
    assert len(events) == 2
    assert events[0]["previous_status"] == "ORDER_RECEIVED"
    assert events[0]["new_status"] == "PROCESSING"
    assert events[1]["previous_status"] == "PROCESSING"
    assert events[1]["new_status"] == "PACKED"
