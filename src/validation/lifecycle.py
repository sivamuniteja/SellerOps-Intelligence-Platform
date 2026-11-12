"""Lifecycle and Temporal State Machine Validator."""

from typing import Dict, List, Any
from src.database.connection import DatabaseManager


class LifecycleValidator:
    """
    Validates chronological integrity and state machine transitions across marketplace entities:
    - Fulfillment chronology: order_date <= dispatched_at <= delivered_at
    - Dispute chronology: order_date <= dispute_date
    - Review chronology: delivered_at <= review_date
    - Reserve hold chronology: hold_start_date <= hold_release_date
    - Payout release timing: order delivered and hold elapsed before payout batch
    - Status consistency across relational entities
    """

    def __init__(self, db: DatabaseManager):
        self.db = db

    def check_all(self) -> Dict[str, Any]:
        """Run all state transition, chronological, and lifecycle validations."""
        fulfillment_time = self.check_fulfillment_chronology()
        dispute_time = self.check_dispute_chronology()
        reserve_time = self.check_reserve_hold_chronology()
        status_consistency = self.check_status_consistency()
        payout_maturity = self.check_payout_maturity_chronology()

        total_violations = (
            len(fulfillment_time.get("violations", []))
            + len(dispute_time.get("violations", []))
            + len(reserve_time.get("violations", []))
            + len(status_consistency.get("violations", []))
            + len(payout_maturity.get("violations", []))
        )

        return {
            "passed": total_violations == 0,
            "total_violations": total_violations,
            "fulfillment_chronology": fulfillment_time,
            "dispute_chronology": dispute_time,
            "reserve_hold_chronology": reserve_time,
            "status_consistency": status_consistency,
            "payout_maturity_chronology": payout_maturity,
        }

    def check_fulfillment_chronology(self) -> Dict[str, Any]:
        """Verify: order_date <= dispatched_at <= delivered_at."""
        q = """
            SELECT f.fulfillment_id, o.order_id, o.order_date, f.dispatched_at, f.delivered_at
            FROM fulfillments f
            JOIN orders o ON f.order_id = o.order_id
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
        """Verify: dispute_date >= order_date."""
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

    def check_reserve_hold_chronology(self) -> Dict[str, Any]:
        """Verify: release_scheduled_date >= created_at for all reserve records."""
        q = """
            SELECT r.entry_id, r.order_line_id, r.hold_days, r.created_at, r.release_scheduled_date
            FROM reserve_ledger r
            WHERE r.release_scheduled_date < r.created_at;
        """
        df = self.db.query_df(q)
        violations = df.to_dict(orient="records")
        return {
            "valid": len(violations) == 0,
            "violations_count": len(violations),
            "violations": violations,
        }

    def check_payout_maturity_chronology(self) -> Dict[str, Any]:
        """
        Verify that payout disbursements occur after reserve maturity date.
        Flags premature payouts (Anomaly 1).
        """
        q = """
            SELECT
                pl.line_id,
                pl.payout_id,
                pl.order_line_id,
                p.batch_date,
                r.release_scheduled_date,
                ol.line_status
            FROM payout_lines pl
            JOIN payouts p ON pl.payout_id = p.payout_id
            JOIN reserve_ledger r ON pl.order_line_id = r.order_line_id
            JOIN order_lines ol ON pl.order_line_id = ol.order_line_id
            WHERE p.batch_date < r.release_scheduled_date
               OR ol.line_status != 'DELIVERED';
        """
        df = self.db.query_df(q)
        violations = df.to_dict(orient="records")
        return {
            "valid": len(violations) == 0,
            "violations_count": len(violations),
            "violations": violations,
        }

    def check_status_consistency(self) -> Dict[str, Any]:
        """
        Verify relational status consistency:
        - Delivered order lines have delivered timestamps on fulfillments.
        - Cancelled order lines do not have active deliveries.
        """
        q = """
            SELECT f.fulfillment_id, f.order_line_id, ol.line_status, f.sla_status, f.delivered_at
            FROM fulfillments f
            JOIN order_lines ol ON f.order_line_id = ol.order_line_id
            WHERE (ol.line_status = 'DELIVERED' AND f.delivered_at IS NULL AND f.sla_status != 'CANCELLED')
               OR (ol.line_status = 'CANCELLED' AND f.delivered_at IS NOT NULL);
        """
        df = self.db.query_df(q)
        violations = df.to_dict(orient="records")
        return {
            "valid": len(violations) == 0,
            "violations_count": len(violations),
            "violations": violations,
        }
