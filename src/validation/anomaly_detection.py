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
        Anomaly 1: Payout line item disbursed for an order line that is either not DELIVERED
        or where batch_date < release_scheduled_date.
        """
        q = """
            SELECT
                pl.line_id,
                pl.payout_id,
                pl.order_line_id,
                ol.line_status,
                r.release_scheduled_date,
                p.batch_date,
                pl.net_line_amount_cents,
                'PREMATURE_PAYOUT' as anomaly_type,
                'CRITICAL' as severity,
                'Payout disbursed before delivery confirmation or prior to reserve maturity' as description
            FROM payout_lines pl
            JOIN order_lines ol ON pl.order_line_id = ol.order_line_id
            JOIN reserve_ledger r ON pl.order_line_id = r.order_line_id
            JOIN payouts p ON pl.payout_id = p.payout_id
            WHERE ol.line_status != 'DELIVERED'
               OR p.batch_date < r.release_scheduled_date;
        """
        return self.db.query_df(q).to_dict(orient="records")

    def detect_double_commissions(self) -> List[Dict[str, Any]]:
        """
        Anomaly 2: Commission fee applied twice on an identical order item settlement.
        """
        q = """
            SELECT
                c.entry_id,
                c.order_line_id,
                c.seller_id,
                c.gross_amount_cents,
                c.total_commission_cents,
                c.rate_basis_points,
                'DOUBLE_COMMISSION' as anomaly_type,
                'HIGH' as severity,
                'Platform commission fee applied twice on the same line' as description
            FROM commission_ledger c
            WHERE c.total_commission_cents > ((c.gross_amount_cents * c.rate_basis_points / 10000.0 + c.fixed_fee_cents) * 1.5);
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
                'Suspended seller continues listing active inventory' as description
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
                d.order_line_id,
                d.seller_id,
                d.disputed_amount_cents,
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
                p.net_payout_amount_cents as header_net_cents,
                COALESCE(SUM(l.net_line_amount_cents), 0) as lines_net_sum_cents,
                (p.net_payout_amount_cents - COALESCE(SUM(l.net_line_amount_cents), 0)) as variance_cents,
                'PAYOUT_TOTAL_MISMATCH' as anomaly_type,
                'CRITICAL' as severity,
                'Batch header net payout does not match arithmetic sum of payout lines' as description
            FROM payouts p
            JOIN payout_lines l ON p.payout_id = l.payout_id
            GROUP BY p.payout_id
            HAVING ABS(header_net_cents - lines_net_sum_cents) > 0;
        """
        return self.db.query_df(q).to_dict(orient="records")

    def evaluate_against_ground_truth(self, detected_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare detected anomalies against the ground-truth registry."""
        gt_table = "ground_truth" if self.db.table_exists("ground_truth") else "anomalies_ground_truth"
        gt_df = self.db.query_df(f"SELECT * FROM {gt_table};")
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
            entity_id = (
                rec.get("line_id")
                or rec.get("entry_id")
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
