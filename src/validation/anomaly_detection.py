"""Automated Rule-Based Anomaly Detection Engine for Operational Exceptions."""

from typing import Dict, List, Any, Optional
import pandas as pd
from src.database.connection import DatabaseManager


class AnomalyDetectionEngine:
    """
    Scans operational database tables to identify the 5 mandated operational exception scenarios:
    1. PAYOUT BEFORE DELIVERY OR HOLD RELEASE
    2. COMMISSION APPLIED TWICE
    3. SUSPENDED SELLER CONTINUES LISTING
    4. DISPUTE NOT DEDUCTED
    5. PAYOUT TOTAL DOES NOT EQUAL PAYOUT LINES

    Never leaks ground-truth labels into detection input features.
    Computes rigorous precision, recall, F1 score, and false-positive metrics.
    """

    def __init__(self, db: DatabaseManager):
        self.db = db

    def run_all_detectors(self) -> Dict[str, Any]:
        """Execute all anomaly detection rules, structure output records, and compute benchmark metrics."""
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
                "false_positives": benchmark["false_positives"],
                "false_negatives": benchmark["false_negatives"],
            },
            "anomalies": {
                "premature_payouts": a1,
                "double_commissions": a2,
                "suspended_seller_activity": a3,
                "unclawbacked_disputes": a4,
                "payout_total_mismatches": a5,
            },
            "all_detected_list": all_detected,
            "ground_truth_benchmark": benchmark,
        }

    def detect_premature_payouts(self) -> List[Dict[str, Any]]:
        """
        Scenario 1: PAYOUT BEFORE DELIVERY OR HOLD RELEASE
        Detect a payout whose batch_date precedes actual delivery or required hold release.
        """
        q = """
            SELECT
                pl.line_id,
                pl.payout_id,
                pl.order_line_id,
                ol.line_status,
                r.release_scheduled_date,
                p.batch_date,
                pl.net_line_amount_cents
            FROM payout_lines pl
            JOIN order_lines ol ON pl.order_line_id = ol.order_line_id
            JOIN reserve_ledger r ON pl.order_line_id = r.order_line_id
            JOIN payouts p ON pl.payout_id = p.payout_id
            WHERE ol.line_status != 'DELIVERED'
               OR p.batch_date < r.release_scheduled_date;
        """
        rows = self.db.query_df(q).to_dict(orient="records")
        anomalies = []
        for r in rows:
            anomalies.append({
                "scenario_id": "SCENARIO-1",
                "entity_id": r["line_id"],
                "entity_type": "PAYOUT_LINE",
                "issue_type": "PREMATURE_PAYOUT",
                "ground_truth_label": "ANOMALY_1_PREMATURE_PAYOUT",
                "expected_result": "Payout line item must only be disbursed after delivery confirmation and reserve hold maturity.",
                "expected_corrective_action": "Claw back premature disbursement and hold settlement until reserve release scheduled date.",
                "actual_detection_result": "DETECTED_ANOMALY",
                "severity": "CRITICAL",
                "details": {
                    "payout_id": r["payout_id"],
                    "order_line_id": r["order_line_id"],
                    "line_status": r["line_status"],
                    "batch_date": r["batch_date"],
                    "release_scheduled_date": r["release_scheduled_date"],
                    "net_amount_cents": r["net_line_amount_cents"],
                },
                "description": f"Payout line {r['line_id']} for order line {r['order_line_id']} was disbursed on {r['batch_date']} prior to hold release {r['release_scheduled_date']} (status: {r['line_status']}).",
            })
        return anomalies

    def detect_double_commissions(self) -> List[Dict[str, Any]]:
        """
        Scenario 2: COMMISSION APPLIED TWICE
        Detect multiple commission ledger entries for the same order line or double commission fee.
        """
        q = """
            SELECT
                c.entry_id,
                c.order_line_id,
                c.seller_id,
                c.gross_amount_cents,
                c.total_commission_cents,
                c.rate_basis_points,
                c.fixed_fee_cents,
                c.created_at
            FROM commission_ledger c
            WHERE c.total_commission_cents > ((c.gross_amount_cents * c.rate_basis_points / 10000.0 + c.fixed_fee_cents) * 1.5);
        """
        rows = self.db.query_df(q).to_dict(orient="records")
        anomalies = []
        for r in rows:
            expected_fee = int((r["gross_amount_cents"] * r["rate_basis_points"]) / 10000 + r["fixed_fee_cents"])
            anomalies.append({
                "scenario_id": "SCENARIO-2",
                "entity_id": r["entry_id"],
                "entity_type": "COMMISSION_LEDGER",
                "issue_type": "DOUBLE_COMMISSION",
                "ground_truth_label": "ANOMALY_2_DOUBLE_COMMISSION",
                "expected_result": "Single platform commission fee applied per order line according to category and tier rate schedule.",
                "expected_corrective_action": "Void duplicate commission charge and issue financial ledger credit adjustment to seller balance.",
                "actual_detection_result": "DETECTED_ANOMALY",
                "severity": "HIGH",
                "details": {
                    "order_line_id": r["order_line_id"],
                    "seller_id": r["seller_id"],
                    "gross_amount_cents": r["gross_amount_cents"],
                    "actual_commission_cents": r["total_commission_cents"],
                    "expected_commission_cents": expected_fee,
                    "variance_cents": r["total_commission_cents"] - expected_fee,
                },
                "description": f"Commission entry {r['entry_id']} for order line {r['order_line_id']} charged double fee ({r['total_commission_cents']} cents vs expected {expected_fee} cents).",
            })
        return anomalies

    def detect_suspended_seller_activity(self) -> List[Dict[str, Any]]:
        """
        Scenario 3: SUSPENDED SELLER CONTINUES LISTING
        Detect a listing created or activated while the seller is suspended.
        """
        q = """
            SELECT
                s.seller_id,
                s.name as seller_name,
                s.status as seller_status,
                l.listing_id,
                l.title as listing_title,
                l.status as listing_status,
                l.created_at as listing_created_at
            FROM sellers s
            JOIN listings l ON s.seller_id = l.seller_id
            WHERE s.status = 'SUSPENDED' AND l.status = 'ACTIVE';
        """
        rows = self.db.query_df(q).to_dict(orient="records")
        anomalies = []
        for r in rows:
            anomalies.append({
                "scenario_id": "SCENARIO-3",
                "entity_id": r["listing_id"],
                "entity_type": "LISTING",
                "issue_type": "SUSPENDED_SELLER_ACTIVE",
                "ground_truth_label": "ANOMALY_3_SUSPENDED_SELLER_ACTIVE",
                "expected_result": "Suspended sellers must have all catalog listings deactivated and cannot maintain active storefront inventory.",
                "expected_corrective_action": "Immediately transition listing status to SUSPENDED and quarantine catalog items from marketplace search.",
                "actual_detection_result": "DETECTED_ANOMALY",
                "severity": "CRITICAL",
                "details": {
                    "seller_id": r["seller_id"],
                    "seller_name": r["seller_name"],
                    "seller_status": r["seller_status"],
                    "listing_id": r["listing_id"],
                    "listing_title": r["listing_title"],
                    "listing_status": r["listing_status"],
                },
                "description": f"Listing {r['listing_id']} ('{r['listing_title']}') remains ACTIVE while seller {r['seller_id']} is SUSPENDED.",
            })
        return anomalies

    def detect_unclawbacked_disputes(self) -> List[Dict[str, Any]]:
        """
        Scenario 4: DISPUTE NOT DEDUCTED
        Detect a finalized lost dispute or chargeback that is missing from payout deductions.
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
                d.dispute_date
            FROM disputes d
            WHERE d.status IN ('RESOLVED_BUYER_FAVOR', 'CHARGEBACK_LOST')
              AND d.clawback_applied = 0;
        """
        rows = self.db.query_df(q).to_dict(orient="records")
        anomalies = []
        for r in rows:
            anomalies.append({
                "scenario_id": "SCENARIO-4",
                "entity_id": r["dispute_id"],
                "entity_type": "DISPUTE",
                "issue_type": "UNCLAWBACKED_DISPUTE",
                "ground_truth_label": "ANOMALY_4_UNCLAWBACKED_DISPUTE",
                "expected_result": "Finalized lost disputes must be deducted as financial clawbacks from seller settlement balances.",
                "expected_corrective_action": "Execute retroactive dispute clawback deduction against seller reserve or pending payout balance.",
                "actual_detection_result": "DETECTED_ANOMALY",
                "severity": "HIGH",
                "details": {
                    "dispute_id": r["dispute_id"],
                    "order_id": r["order_id"],
                    "order_line_id": r["order_line_id"],
                    "seller_id": r["seller_id"],
                    "dispute_status": r["dispute_status"],
                    "disputed_amount_cents": r["disputed_amount_cents"],
                    "clawback_applied": r["clawback_applied"],
                },
                "description": f"Dispute {r['dispute_id']} resolved as {r['dispute_status']} for {r['disputed_amount_cents']} cents was never clawed back (clawback_applied = 0).",
            })
        return anomalies

    def detect_payout_total_mismatches(self) -> List[Dict[str, Any]]:
        """
        Scenario 5: PAYOUT TOTAL DOES NOT EQUAL PAYOUT LINES
        Detect a payout header whose total differs from the sum of its payout lines.
        """
        q = """
            SELECT
                p.payout_id,
                p.seller_id,
                p.batch_date,
                p.net_payout_amount_cents as header_net_cents,
                COALESCE(SUM(l.net_line_amount_cents), 0) as lines_net_sum_cents,
                (p.net_payout_amount_cents - COALESCE(SUM(l.net_line_amount_cents), 0)) as variance_cents,
                COUNT(l.line_id) as line_count
            FROM payouts p
            JOIN payout_lines l ON p.payout_id = l.payout_id
            GROUP BY p.payout_id
            HAVING ABS(header_net_cents - lines_net_sum_cents) > 0;
        """
        rows = self.db.query_df(q).to_dict(orient="records")
        anomalies = []
        for r in rows:
            anomalies.append({
                "scenario_id": "SCENARIO-5",
                "entity_id": r["payout_id"],
                "entity_type": "PAYOUT_BATCH",
                "issue_type": "PAYOUT_TOTAL_MISMATCH",
                "ground_truth_label": "ANOMALY_5_PAYOUT_TOTAL_MISMATCH",
                "expected_result": "Payout batch header net amount must exactly equal arithmetic sum of child line item net amounts.",
                "expected_corrective_action": "Recalculate batch header total from line items and flag disbursement batch for audit review.",
                "actual_detection_result": "DETECTED_ANOMALY",
                "severity": "CRITICAL",
                "details": {
                    "payout_id": r["payout_id"],
                    "seller_id": r["seller_id"],
                    "header_net_cents": r["header_net_cents"],
                    "lines_net_sum_cents": r["lines_net_sum_cents"],
                    "variance_cents": r["variance_cents"],
                    "line_count": r["line_count"],
                },
                "description": f"Payout batch {r['payout_id']} header amount ({r['header_net_cents']} cents) does not match lines sum ({r['lines_net_sum_cents']} cents, variance: {r['variance_cents']} cents).",
            })
        return anomalies

    def evaluate_against_ground_truth(self, detected_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compare detected anomalies against the ground-truth registry.
        Computes precision, recall, F1 score, and false-positive count.
        """
        gt_table = "ground_truth" if self.db.table_exists("ground_truth") else "anomalies_ground_truth"
        if not self.db.table_exists(gt_table):
            return {
                "ground_truth_total": 0,
                "detected_total": len(detected_records),
                "true_positives": 0,
                "false_positives": len(detected_records),
                "false_negatives": 0,
                "precision": 1.0 if not detected_records else 0.0,
                "recall": 1.0,
                "f1_score": 1.0 if not detected_records else 0.0,
                "scenarios": {},
            }

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
                "scenarios": {},
            }

        # Build ground-truth mapping: (issue_type, entity_id) -> record
        gt_keys = set(zip(gt_df["anomaly_type"], gt_df["entity_id"]))

        tp = 0
        fp = 0
        detected_keys = set()

        for rec in detected_records:
            itype = rec.get("issue_type")
            eid = rec.get("entity_id")
            key = (itype, eid)
            detected_keys.add(key)

            if key in gt_keys:
                tp += 1
            else:
                fp += 1

        fn = len(gt_keys - detected_keys)
        precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
        f1 = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) > 0 else 0.0

        # Per-scenario breakdown
        scenarios_breakdown = {}
        for scenario_type in ["PREMATURE_PAYOUT", "DOUBLE_COMMISSION", "SUSPENDED_SELLER_ACTIVE", "UNCLAWBACKED_DISPUTE", "PAYOUT_TOTAL_MISMATCH"]:
            gt_sub = {k for k in gt_keys if k[0] == scenario_type}
            det_sub = {k for k in detected_keys if k[0] == scenario_type}
            s_tp = len(gt_sub & det_sub)
            s_fp = len(det_sub - gt_sub)
            s_fn = len(gt_sub - det_sub)
            s_prec = round(s_tp / (s_tp + s_fp), 4) if (s_tp + s_fp) > 0 else 0.0
            s_rec = round(s_tp / (s_tp + s_fn), 4) if (s_tp + s_fn) > 0 else 0.0
            s_f1 = round(2 * s_prec * s_rec / (s_prec + s_rec), 4) if (s_prec + s_rec) > 0 else 0.0

            scenarios_breakdown[scenario_type] = {
                "ground_truth_count": len(gt_sub),
                "detected_count": len(det_sub),
                "true_positives": s_tp,
                "false_positives": s_fp,
                "false_negatives": s_fn,
                "precision": s_prec,
                "recall": s_rec,
                "f1_score": s_f1,
            }

        return {
            "ground_truth_total": len(gt_keys),
            "detected_total": len(detected_records),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "scenarios": scenarios_breakdown,
        }
