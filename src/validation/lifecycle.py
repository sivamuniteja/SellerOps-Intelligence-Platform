"""Lifecycle and Temporal State Machine Validator."""

from datetime import datetime
from typing import Dict, List, Any
from src.database.connection import DatabaseManager


class LifecycleValidator:
    """Validates chronological order and state machine transitions across marketplace entities."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def check_all(self) -> Dict[str, Any]:
        """Run all state transition and temporal validations."""
        fulfillment_time = self.check_fulfillment_chronology()
        dispute_time = self.check_dispute_chronology()
        status_consistency = self.check_status_consistency()

        total_violations = (
            len(fulfillment_time.get("violations", []))
            + len(dispute_time.get("violations", []))
            + len(status_consistency.get("violations", []))
        )

        return {
            "passed": total_violations == 0,
            "total_violations": total_violations,
            "fulfillment_chronology": fulfillment_time,
            "dispute_chronology": dispute_time,
            "status_consistency": status_consistency,
        }

    def check_fulfillment_chronology(self) -> Dict[str, Any]:
        """Verify order_date <= dispatched_at <= delivered_at."""
        q = """
            SELECT o.order_id, o.order_date, f.dispatched_at, f.delivered_at
            FROM orders o
            JOIN fulfillments f ON o.order_id = f.order_id
            WHERE (f.dispatched_at IS NOT NULL AND f.dispatched_at < o.order_date)
               OR (f.delivered_at IS NOT NULL AND f.dispatched_at IS NOT NULL AND f.delivered_at < f.dispatched_at);
        """
        df = self.db.query_df(q)
        violations = df.to_dict(orient="records")
        return {
            "valid": len(violations) == 0,
            "violations_count": len(violations),
            "violations": violations,
        }

    def check_dispute_chronology(self) -> Dict[str, Any]:
        """Verify dispute_date >= order_date."""
        q = """
            SELECT d.dispute_id, d.order_id, d.dispute_date, o.order_date
            FROM disputes d
            JOIN orders o ON d.order_id = o.order_id
            WHERE d.dispute_date < o.order_date;
        """
        df = self.db.query_df(q)
        violations = df.to_dict(orient="records")
        return {
            "valid": len(violations) == 0,
            "violations_count": len(violations),
            "violations": violations,
        }

    def check_status_consistency(self) -> Dict[str, Any]:
        """Verify that delivered orders have delivery timestamps and valid SLA."""
        q = """
            SELECT o.order_id, o.order_status, f.delivered_at, f.sla_status
            FROM orders o
            JOIN fulfillments f ON o.order_id = f.order_id
            WHERE (o.order_status = 'DELIVERED' AND f.delivered_at IS NULL)
               OR (o.order_status = 'CANCELLED' AND f.sla_status != 'CANCELLED');
        """
        df = self.db.query_df(q)
        violations = df.to_dict(orient="records")
        return {
            "valid": len(violations) == 0,
            "violations_count": len(violations),
            "violations": violations,
        }
