#!/usr/bin/env python3
"""CLI script to run end-to-end data validation and anomaly detection audit."""

import argparse
import sys
from pathlib import Path
from tabulate import tabulate

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import get_db
from src.validation.integrity import IntegrityValidator
from src.validation.lifecycle import LifecycleValidator
from src.validation.reconciliation import FinancialReconciliation
from src.validation.anomaly_detection import AnomalyDetectionEngine


def main():
    parser = argparse.ArgumentParser(description="Validate SellerOps database integrity & detect anomalies.")
    parser.add_argument("--db-path", type=str, default="data/sellerops.db", help="Path to SQLite database.")
    args = parser.parse_args()

    db = get_db(args.db_path)
    print(f"\n=======================================================")
    print(f"🔍 Running SellerOps Validation & Anomaly Detection")
    print(f"Target Database: {args.db_path}")
    print(f"=======================================================\n")

    # 1. Referential Integrity
    iv = IntegrityValidator(db).check_all()
    print("1. REFERENTIAL & SCHEMA INTEGRITY:")
    if iv["passed"]:
        print("   ✅ Foreign keys, primary keys, and non-null constraints: 100% VALID (0 issues)")
    else:
        print(f"   ❌ FAILED: {iv['total_issues']} issues detected.")

    # 2. Lifecycle Chronology
    lv = LifecycleValidator(db).check_all()
    print("\n2. LIFECYCLE & TEMPORAL CONSISTENCY:")
    if lv["passed"]:
        print("   ✅ Chronology (order <= dispatch <= delivery <= dispute): 100% VALID (0 issues)")
    else:
        print(f"   ❌ FAILED: {lv['total_violations']} chronology violations.")

    # 3. Financial Reconciliation
    fr = FinancialReconciliation(db).reconcile_all()
    payout_disc = fr["payouts"]["discrepancy_count"]
    print("\n3. FINANCIAL RECONCILIATION:")
    print(f"   [-] Total Payout Batches Evaluated: {fr['payouts']['total_batches_checked']}")
    print(f"   [-] Batches with Ledger Discrepancies (Anomaly 5): {payout_disc}")

    # 4. Anomaly Detection
    ad = AnomalyDetectionEngine(db).run_all_detectors()
    summary = ad["summary"]
    print("\n4. OPERATIONAL ANOMALY DETECTION REPORT:")
    table_data = [
        ["Anomaly 1 (Premature Payout)", summary["anomaly_1_count"], "CRITICAL"],
        ["Anomaly 2 (Double Commission)", summary["anomaly_2_count"], "HIGH"],
        ["Anomaly 3 (Suspended Seller Active)", summary["anomaly_3_count"], "CRITICAL"],
        ["Anomaly 4 (Unclawbacked Dispute)", summary["anomaly_4_count"], "HIGH"],
        ["Anomaly 5 (Payout Total Mismatch)", summary["anomaly_5_count"], "CRITICAL"],
    ]
    print(tabulate(table_data, headers=["Scenario", "Count Detected", "Severity"], tablefmt="grid"))
    print(f"\nBenchmark Metrics against Ground Truth:")
    print(f"   • Detection Precision : {summary['precision'] * 100:.2f}%")
    print(f"   • Detection Recall    : {summary['recall'] * 100:.2f}%")
    print(f"   • F1 Score            : {summary['f1_score'] * 100:.2f}%\n")


if __name__ == "__main__":
    main()
