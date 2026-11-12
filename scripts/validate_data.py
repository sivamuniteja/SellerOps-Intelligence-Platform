#!/usr/bin/env python3
"""CLI script to run end-to-end data validation and anomaly detection audit."""

import argparse
import sys
from pathlib import Path
from tabulate import tabulate

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import get_db
from src.validation.validator import FullPlatformValidator


def main():
    parser = argparse.ArgumentParser(description="Validate SellerOps database integrity & detect anomalies.")
    parser.add_argument("--db-path", type=str, default="data/sellerops.db", help="Path to SQLite database.")
    parser.add_argument("--output-json", type=str, default="data/validation_report.json", help="Path to export validation JSON report.")
    args = parser.parse_args()

    db = get_db(args.db_path)
    print(f"\n=======================================================")
    print(f"🔍 Running SellerOps Full-Platform Validation Engine")
    print(f"Target Database : {args.db_path}")
    print(f"Report Output   : {args.output_json}")
    print(f"=======================================================\n")

    validator = FullPlatformValidator(db)
    report = validator.run_validation(export_path=args.output_json)

    meta = report["metadata"]
    dims = report["validation_dimensions"]
    ad = report["anomaly_detection"]
    summary = ad["summary"]

    print("1. 14-DIMENSION VALIDATION MATRIX:")
    val_table = []
    for dim_name, dim_data in dims.items():
        status_str = "PASS ✅" if dim_data["passed"] else "ANOMALY / FAIL ⚠️"
        count = dim_data.get("violations_count", dim_data.get("discrepancy_count", 0))
        val_table.append([dim_name.replace("_", " ").title(), status_str, count])

    print(tabulate(val_table, headers=["Validation Dimension", "Status", "Issue Count"], tablefmt="grid"))
    print(f"\nTotal Checks: {meta['total_checks_evaluated']} | Passed: {meta['passed_checks_count']} | Discrepant: {meta['failed_checks_count']}")

    print("\n2. OPERATIONAL ANOMALY DETECTION REPORT:")
    table_data = [
        ["Scenario 1 (Premature Payout)", summary["anomaly_1_count"], "CRITICAL"],
        ["Scenario 2 (Double Commission)", summary["anomaly_2_count"], "HIGH"],
        ["Scenario 3 (Suspended Seller Active)", summary["anomaly_3_count"], "CRITICAL"],
        ["Scenario 4 (Unclawbacked Dispute)", summary["anomaly_4_count"], "HIGH"],
        ["Scenario 5 (Payout Total Mismatch)", summary["anomaly_5_count"], "CRITICAL"],
    ]
    print(tabulate(table_data, headers=["Scenario", "Count Detected", "Severity"], tablefmt="grid"))

    print(f"\n3. BENCHMARK METRICS AGAINST SCENARIO GROUND TRUTH:")
    print(f"   • Detection Precision : {summary['precision'] * 100:.2f}%")
    print(f"   • Detection Recall    : {summary['recall'] * 100:.2f}%")
    print(f"   • F1 Score            : {summary['f1_score'] * 100:.2f}%")
    print(f"   • False Positives     : {summary['false_positives']}")
    print(f"   • False Negatives     : {summary['false_negatives']}\n")

    print(f"📄 Machine-readable report saved to: {args.output_json}\n")


if __name__ == "__main__":
    main()
