"""Automated Anomaly Detection Engine for Operational Exceptions."""

from typing import Dict, List, Any
import pandas as pd
from src.database.connection import DatabaseManager


class AnomalyDetectionEngine:
    """
    Scans the database to identify the 5 mandated operational exceptions:
    1. Payout before delivery or hold release.
    2. Commission applied twice.
    3. Suspended seller continues listing or selling.
    4. Dispute not deducted from payout / balance.
    5. Payout total does not equal payout line items.
    """

    def __init__(self, db: DatabaseManager):
        self.db = db

    def run_all_detectors(self) -> Dict[str, Any]:
        """Execute all anomaly detection rules and compute benchmark metrics."""
        a1 = self.detect_premature_payouts()
        a2 = self.detect_double_commissions()
        a3 = self.detect_suspended_seller_activity()
        a4 = self.detect_unclawbacked_disputes()
        a5 = self.detect_payout_total_mismatches()

        all_detected = a1 + a2 + a3 + a4 + a5
        benchmark = self.evaluate_against_ground_truth(all_detected)

        return {
            "summary": {
                "total_anomalies_detected": len(all_detected),
                "anomaly_1_count": len(a1),
                "anomaly_2_count": len(a2),
                "anomaly_3_count": len(a3),
                "anomaly_4_count": len(a4),
                "anomaly_5_count": len(a5),
                "precision": benchmark["precision"],
                "recall": benchmark["recall"],
                "f1_score": benchmark["f1_score"],
            },
            "anomalies": {
                "premature_payouts": a1,
                "double_commissions": a2,
                "suspended_seller_activity": a3,
                "unclawbacked_disputes": a4,
                "payout_total_mismatches": a5,
            },
            "ground_truth_benchmark": benchmark,
        }

    def detect_premature_payouts(self) -> List[Dict[str, Any]]:
        """
        Anomaly 1: Payout line item disbursed for an order that is either not DELIVERED
        or whose reserve release date is in the future.
        """
        q = """
            SELECT
                pl.line_id,
                pl.payout_id,
                pl.order_id,
                o.order_status,
                s.reserve_release_date,
                pb.batch_date,
                pl.net_line_amount,
                'PREMATURE_PAYOUT' as anomaly_type,
                'CRITICAL' as severity,
                'Payout disbursed before delivery confirmation or prior to reserve hold maturity' as description
            FROM payout_lines pl
            JOIN orders o ON pl.order_id = o.order_id
            JOIN order_settlements s ON pl.order_id = s.order_id
            JOIN payout_batches pb ON pl.payout_id = pb.payout_id
            WHERE o.order_status != 'DELIVERED'
               OR pb.batch_date < s.reserve_release_date;
        """
        return self.db.query_df(q).to_dict(orient="records")

    def detect_double_commissions(self) -> List[Dict[str, Any]]:
        """
        Anomaly 2: Commission fee applied twice on an identical order item settlement.
        """
        q = """
            SELECT
                s.settlement_id,
                s.order_id,
                s.seller_id,
                s.gross_amount,
                s.commission_amount,
                s.commission_rate,
                ROUND(s.commission_amount / s.gross_amount, 4) as effective_taken_rate,
                'DOUBLE_COMMISSION' as anomaly_type,
                'HIGH' as severity,
                'Platform commission fee applied twice on the same settlement' as description
            FROM order_settlements s
            WHERE s.commission_amount > (s.gross_amount * s.commission_rate * 1.5);
        """
        return self.db.query_df(q).to_dict(orient="records")

    def detect_suspended_seller_activity(self) -> List[Dict[str, Any]]:
        """
        Anomaly 3: Seller flagged as SUSPENDED has active listings and continues generating orders.
        """
        q = """
            SELECT
                s.seller_id,
                s.name as seller_name,
                s.status as seller_status,
                l.listing_id,
                l.title as listing_title,
                l.status as listing_status,
                'SUSPENDED_SELLER_ACTIVE' as anomaly_type,
                'CRITICAL' as severity,
                'Suspended seller continues listing active inventory or accepting orders' as description
            FROM sellers s
            JOIN listings l ON s.seller_id = l.seller_id
            WHERE s.status = 'SUSPENDED' AND l.status = 'ACTIVE';
        """
        return self.db.query_df(q).to_dict(orient="records")

    def detect_unclawbacked_disputes(self) -> List[Dict[str, Any]]:
        """
        Anomaly 4: Dispute decided in buyer's favor without deducting chargeback amount.
        """
        q = """
            SELECT
                d.dispute_id,
                d.order_id,
                d.seller_id,
                d.disputed_amount,
                d.status as dispute_status,
                d.clawback_applied,
                'UNCLAWBACKED_DISPUTE' as anomaly_type,
                'HIGH' as severity,
                'Resolved dispute in buyer favor was not clawed back from seller payout' as description
            FROM disputes d
            WHERE d.status IN ('RESOLVED_BUYER_FAVOR', 'CHARGEBACK_LOST')
              AND d.clawback_applied = 0;
        """
        return self.db.query_df(q).to_dict(orient="records")

    def detect_payout_total_mismatches(self) -> List[Dict[str, Any]]:
        """
        Anomaly 5: Total payout disbursement in batch header does not equal arithmetic sum of line items.
        """
        q = """
            SELECT
                p.payout_id,
                p.seller_id,
                ROUND(p.net_payout_amount, 2) as header_net,
                ROUND(COALESCE(SUM(l.net_line_amount), 0.0), 2) as lines_net_sum,
                ROUND(p.net_payout_amount - COALESCE(SUM(l.net_line_amount), 0.0), 2) as variance,
                'PAYOUT_TOTAL_MISMATCH' as anomaly_type,
                'CRITICAL' as severity,
                'Batch header net payout does not match arithmetic sum of payout lines' as description
            FROM payout_batches p
            JOIN payout_lines l ON p.payout_id = l.payout_id
            GROUP BY p.payout_id
            HAVING ABS(header_net - lines_net_sum) > 0.01;
        """
        return self.db.query_df(q).to_dict(orient="records")

    def evaluate_against_ground_truth(self, detected_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare detected anomalies against the ground-truth registry."""
        gt_df = self.db.query_df("SELECT * FROM anomalies_ground_truth;")
        if gt_df.empty:
            return {
                "ground_truth_total": 0,
                "detected_total": len(detected_records),
                "true_positives": 0,
                "false_positives": len(detected_records),
                "false_negatives": 0,
                "precision": 1.0 if not detected_records else 0.0,
                "recall": 1.0,
                "f1_score": 1.0 if not detected_records else 0.0,
            }

        # Build set of ground truth entity IDs
        gt_keys = set(zip(gt_df["anomaly_type"], gt_df["entity_id"]))

        # Match detected records
        tp = 0
        fp = 0
        for rec in detected_records:
            atype = rec.get("anomaly_type")
            # Map anomaly type to entity_id key
            entity_id = (
                rec.get("line_id")
                or rec.get("settlement_id")
                or rec.get("listing_id")
                or rec.get("dispute_id")
                or rec.get("payout_id")
            )
            if (atype, entity_id) in gt_keys:
                tp += 1
            else:
                fp += 1

        fn = max(0, len(gt_keys) - tp)
        precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
        f1 = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) > 0 else 0.0

        return {
            "ground_truth_total": len(gt_keys),
            "detected_total": len(detected_records),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
        }
