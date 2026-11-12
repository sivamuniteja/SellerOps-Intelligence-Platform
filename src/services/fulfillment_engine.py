"""Fulfillment Lifecycle Tracking and SLA Calculation Engine for SellerOps Intelligence Platform."""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple, Union
from src.config import PlatformConfig, load_config


class FulfillmentError(Exception):
    """Base exception for fulfillment engine errors."""
    pass


class InvalidFulfillmentTransitionError(FulfillmentError):
    """Raised when an illegal fulfillment state transition is attempted."""
    pass


class FulfillmentNotFoundError(FulfillmentError):
    """Raised when a fulfillment record is not found."""
    pass


class FulfillmentEngine:
    """
    Computes fulfillment transit metrics, enforces finite state transitions,
    calculates SLA compliance, and preserves immutable event history.
    """

    # Finite lifecycle states
    STATE_ORDER_RECEIVED = "ORDER_RECEIVED"
    STATE_PROCESSING = "PROCESSING"
    STATE_PACKED = "PACKED"
    STATE_SHIPPED = "SHIPPED"
    STATE_OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    STATE_DELIVERED = "DELIVERED"
    STATE_CANCELLED = "CANCELLED"
    STATE_RETURNED = "RETURNED"

    VALID_STATES: Set[str] = {
        STATE_ORDER_RECEIVED,
        STATE_PROCESSING,
        STATE_PACKED,
        STATE_SHIPPED,
        STATE_OUT_FOR_DELIVERY,
        STATE_DELIVERED,
        STATE_CANCELLED,
        STATE_RETURNED,
    }

    # State aliases for platform flexibility
    STATE_ALIASES: Dict[str, str] = {
        "PLACED": STATE_ORDER_RECEIVED,
        "CREATED": STATE_ORDER_RECEIVED,
    }

    # Valid transitions graph
    TRANSITIONS: Dict[str, Set[str]] = {
        STATE_ORDER_RECEIVED: {STATE_PROCESSING, STATE_CANCELLED},
        STATE_PROCESSING: {STATE_PACKED, STATE_CANCELLED},
        STATE_PACKED: {STATE_SHIPPED, STATE_CANCELLED},
        STATE_SHIPPED: {STATE_OUT_FOR_DELIVERY, STATE_DELIVERED},
        STATE_OUT_FOR_DELIVERY: {STATE_DELIVERED},
        STATE_DELIVERED: {STATE_RETURNED},
        STATE_CANCELLED: set(),
        STATE_RETURNED: set(),
    }

    def __init__(self, config: Optional[PlatformConfig] = None):
        self.config = config or load_config()
        self.dispatch_limit_hours = int(self.config.sla_thresholds.get("dispatch_window_hours", 48))
        self.standard_transit_days = 3

        # In-memory store for tracking and event history
        self._fulfillments: Dict[str, Dict[str, Any]] = {}
        self._events: List[Dict[str, Any]] = []

    def normalize_state(self, state: str) -> str:
        """Normalize state names and resolve aliases."""
        upper_state = state.strip().upper()
        return self.STATE_ALIASES.get(upper_state, upper_state)

    def is_valid_transition(self, current_state: str, next_state: str) -> bool:
        """Validate if transition between current_state and next_state is legal."""
        curr = self.normalize_state(current_state)
        nxt = self.normalize_state(next_state)

        if curr not in self.VALID_STATES or nxt not in self.VALID_STATES:
            return False

        allowed = self.TRANSITIONS.get(curr, set())
        return nxt in allowed

    def validate_transition(self, current_state: str, next_state: str) -> None:
        """Validate transition, raising InvalidFulfillmentTransitionError if illegal."""
        curr = self.normalize_state(current_state)
        nxt = self.normalize_state(next_state)

        if not self.is_valid_transition(curr, nxt):
            allowed = self.TRANSITIONS.get(curr, set())
            raise InvalidFulfillmentTransitionError(
                f"Invalid fulfillment transition from '{curr}' to '{nxt}'. Allowed transitions: {sorted(list(allowed))}"
            )

    def transition_status(
        self,
        fulfillment_id: str,
        current_state: str,
        next_state: str,
        occurred_at: datetime,
        notes: Optional[str] = None,
        db_conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """
        Execute an immutable state transition, updating fulfillment status and logging an event.
        """
        curr = self.normalize_state(current_state)
        nxt = self.normalize_state(next_state)

        self.validate_transition(curr, nxt)

        event_seq = len(self._events) + 1
        event_id = f"FEVT-{fulfillment_id}-{event_seq:04d}"
        occ_str = occurred_at.strftime("%Y-%m-%d %H:%M:%S")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        event = {
            "event_id": event_id,
            "fulfillment_id": fulfillment_id,
            "event_type": f"TRANSITION_{nxt}",
            "previous_status": curr,
            "new_status": nxt,
            "notes": notes or f"Status transitioned from {curr} to {nxt}",
            "occurred_at": occ_str,
            "created_at": now_str,
        }

        # Immutable append
        self._events.append(event)

        # Update in-memory record if exists
        if fulfillment_id in self._fulfillments:
            self._fulfillments[fulfillment_id]["fulfillment_status"] = nxt
            self._fulfillments[fulfillment_id]["updated_at"] = occ_str
            if nxt == self.STATE_SHIPPED:
                self._fulfillments[fulfillment_id]["actual_shipment_date"] = occ_str
            elif nxt == self.STATE_DELIVERED:
                self._fulfillments[fulfillment_id]["actual_delivery_date"] = occ_str

        # Persist to database if provided
        if db_conn:
            cursor = db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO fulfillment_events (
                    event_id, fulfillment_id, event_type, previous_status,
                    new_status, notes, occurred_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    fulfillment_id,
                    event["event_type"],
                    curr,
                    nxt,
                    event["notes"],
                    occ_str,
                    now_str,
                ),
            )
            # Update fulfillment status
            cursor.execute(
                """
                UPDATE fulfillments
                SET fulfillment_status = ?, updated_at = ?
                WHERE fulfillment_id = ?
                """,
                (nxt, occ_str, fulfillment_id),
            )
            db_conn.commit()

        return event

    def calculate_delays(
        self,
        order_date: datetime,
        expected_shipment_date: datetime,
        actual_shipment_date: Optional[datetime],
        expected_delivery_date: Optional[datetime],
        actual_delivery_date: Optional[datetime],
    ) -> Dict[str, Any]:
        """
        Calculate shipment delay, delivery delay, and on-time compliance status.
        """
        shipment_delay_hours = 0.0
        is_on_time_shipment = True

        if actual_shipment_date:
            shipment_delta = actual_shipment_date - expected_shipment_date
            shipment_delay_hours = round(shipment_delta.total_seconds() / 3600.0, 1)
            is_on_time_shipment = shipment_delay_hours <= 0.0

        delivery_delay_hours = 0.0
        is_on_time_delivery = True

        if actual_delivery_date and expected_delivery_date:
            delivery_delta = actual_delivery_date - expected_delivery_date
            delivery_delay_hours = round(delivery_delta.total_seconds() / 3600.0, 1)
            is_on_time_delivery = delivery_delay_hours <= 0.0

        is_on_time = is_on_time_shipment and is_on_time_delivery
        sla_breached = not is_on_time

        return {
            "shipment_delay_hours": max(0.0, shipment_delay_hours),
            "delivery_delay_hours": max(0.0, delivery_delay_hours),
            "is_on_time_shipment": is_on_time_shipment,
            "is_on_time_delivery": is_on_time_delivery,
            "is_on_time": is_on_time,
            "sla_breached": sla_breached,
        }

    def evaluate_sla(
        self,
        order_date: datetime,
        dispatched_at: Optional[datetime],
        delivered_at: Optional[datetime],
        is_cancelled: bool = False,
        expected_delivery_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate fulfillment SLA against standard 48h dispatch window and transit duration.
        Maintains backward compatibility with generators and test suites.
        """
        if is_cancelled or dispatched_at is None:
            return {
                "sla_status": "CANCELLED" if is_cancelled else "IN_TRANSIT",
                "dispatch_delay_hours": None,
                "transit_days": None,
                "is_late": False,
                "is_on_time": False,
                "sla_breached": False,
            }

        dispatch_delta = dispatched_at - order_date
        dispatch_delay_hours = round(dispatch_delta.total_seconds() / 3600.0, 1)
        is_late_dispatch = dispatch_delay_hours > self.dispatch_limit_hours

        transit_days = None
        if delivered_at and delivered_at >= dispatched_at:
            transit_delta = delivered_at - dispatched_at
            transit_days = max(1, int(transit_delta.total_seconds() / 86400.0))

        # Expected delivery default is 3 days post dispatch
        exp_deliv = expected_delivery_date or (dispatched_at + timedelta(days=self.standard_transit_days))
        is_late_delivery = (delivered_at > exp_deliv) if delivered_at else False

        is_late = is_late_dispatch or is_late_delivery
        is_on_time = not is_late

        sla_status = "LATE" if is_late else "ON_TIME"
        if not delivered_at and not is_late_dispatch:
            sla_status = "IN_TRANSIT"

        return {
            "sla_status": sla_status,
            "dispatch_delay_hours": dispatch_delay_hours,
            "transit_days": transit_days,
            "is_late": is_late,
            "is_on_time": is_on_time,
            "sla_breached": is_late,
        }

    def get_fulfillment_events(
        self,
        fulfillment_id: str,
        db_conn: Optional[sqlite3.Connection] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve chronological history of fulfillment lifecycle events."""
        if db_conn:
            cursor = db_conn.cursor()
            cursor.execute(
                """
                SELECT event_id, fulfillment_id, event_type, previous_status,
                       new_status, notes, occurred_at, created_at
                FROM fulfillment_events
                WHERE fulfillment_id = ?
                ORDER BY occurred_at ASC
                """,
                (fulfillment_id,),
            )
            cols = [col[0] for col in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

        return [e for e in self._events if e["fulfillment_id"] == fulfillment_id]
