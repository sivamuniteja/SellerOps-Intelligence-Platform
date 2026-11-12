#!/usr/bin/env python3
"""CLI script to verify deterministic dataset reproducibility."""

import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.generate import run_pipeline
from src.database.connection import get_db


def table_hash(db, table_name: str) -> str:
    """Compute deterministic MD5 checksum of all rows in a table."""
    with db.session() as conn:
        cursor = conn.execute(f"SELECT * FROM {table_name} ORDER BY 1;")
        hasher = hashlib.sha256()
        for row in cursor.fetchall():
            row_str = "|".join(str(val) for val in row)
            hasher.update(row_str.encode("utf-8"))
        return hasher.hexdigest()


def main():
    print(f"\n=======================================================")
    print(f"🔄 Deterministic Reproducibility Audit")
    print(f"Generating two independent databases with Seed=42...")
    print(f"=======================================================\n")

    db1_path = "data/scenarios/reproduce_run_1.db"
    db2_path = "data/scenarios/reproduce_run_2.db"

    # Run 1
    print("[-] Executing Run 1 (Seed 42, Starter scale)...")
    run_pipeline(target_mode="starter", db_path=db1_path, seed=42)

    # Run 2
    print("[-] Executing Run 2 (Seed 42, Starter scale)...")
    run_pipeline(target_mode="starter", db_path=db2_path, seed=42)

    db1 = get_db(db1_path)
    db2 = get_db(db2_path)

    tables = [
        "sellers", "customers", "listings", "orders",
        "fulfillments", "reviews", "disputes", "order_settlements",
        "payout_batches", "payout_lines", "anomalies_ground_truth"
    ]

    all_matched = True
    print("\n[-] Comparing cryptographic table checksums:")
    for t in tables:
        h1 = table_hash(db1, t)
        h2 = table_hash(db2, t)
        match = (h1 == h2)
        status = "MATCH ✅" if match else "MISMATCH ❌"
        print(f"   • {t.ljust(24)}: {status} (SHA-256: {h1[:12]}...)")
        if not match:
            all_matched = False

    # Cleanup temporary test DBs
    for p in [db1_path, db2_path]:
        for ext in ["", "-wal", "-shm"]:
            fpath = Path(f"{p}{ext}")
            if fpath.exists():
                fpath.unlink()

    if all_matched:
        print("\n🎉 REPRODUCIBILITY VERIFICATION SUCCEEDED: 100% Deterministic!")
        sys.exit(0)
    else:
        print("\n❌ REPRODUCIBILITY VERIFICATION FAILED: Inconsistencies detected.")
        sys.exit(1)


if __name__ == "__main__":
    main()
