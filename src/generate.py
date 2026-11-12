"""Master Synthetic Marketplace Data Generation Pipeline."""

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import PlatformConfig, load_config
from src.database.connection import DatabaseManager
from src.generators.sellers import generate_sellers
from src.generators.customers import generate_customers
from src.generators.listings import generate_listings
from src.generators.commission_rules import generate_commission_rules
from src.generators.orders import generate_orders
from src.generators.fulfillments import generate_fulfillments
from src.generators.reviews import generate_reviews
from src.generators.disputes import generate_disputes
from src.generators.payouts import generate_settlements_and_payouts
from src.services.fulfillment_engine import FulfillmentEngine


def compute_table_checksum(db: DatabaseManager, table_name: str) -> str:
    """Compute deterministic SHA-256 hash across sorted table rows."""
    with db.session() as conn:
        cursor = conn.execute(f"SELECT * FROM {table_name} ORDER BY 1;")
        hasher = hashlib.sha256()
        for row in cursor.fetchall():
            row_str = "|".join(str(val) for val in row)
            hasher.update(row_str.encode("utf-8"))
        return hasher.hexdigest()


def run_pipeline(
    target_mode: str = "starter",
    db_path: Optional[str] = None,
    seed: Optional[int] = None,
    inject_anomalies: bool = True,
) -> Dict[str, Any]:
    """
    Execute full synthetic marketplace data generation pipeline.
    target_mode: 'starter' (50 sellers, 500 listings, 2,000 orders, 200 disputes)
                 'full' (2,000 sellers, 20,000 listings, 100,000 orders, 10,000 disputes)
    inject_anomalies: True to inject controlled anomalies (Workflow B), False for baseline (Workflow A).
    """
    start_time = time.time()
    config = load_config()

    chosen_seed = seed if seed is not None else config.seed
    target_cfg = config.dataset_targets.get(target_mode)
    if not target_cfg:
        raise ValueError(f"Unknown target mode: '{target_mode}'. Choose 'starter' or 'full'.")

    # Determine database path
    should_mirror = (db_path is None)
    if db_path is None:
        db_path = config.starter_db_path if target_mode == "starter" else config.full_db_path

    default_db_path = config.default_db_path

    print(f"\n=======================================================")
    print(f"🚀 Launching SellerOps Synthetic Pipeline [{target_mode.upper()} MODE]")
    print(f"Target DB: {db_path}")
    print(f"Deterministic Seed: {chosen_seed}")
    print(f"Workflow: {'Controlled Anomaly Injection (Workflow B)' if inject_anomalies else 'Clean Baseline (Workflow A)'}")
    print(f"Targets: {target_cfg.sellers} sellers, {target_cfg.listings} listings, {target_cfg.orders} orders, {target_cfg.disputes} disputes")
    print(f"=======================================================\n")

    # 0. Initialize DB Schema with versioning
    db = DatabaseManager(db_path)
    db.init_schema()

    # 1. Sellers & Status Audit Events
    print(f"[-] 1/14 Generating {target_cfg.sellers} sellers & status events...")
    sellers, status_events = generate_sellers(target_cfg.sellers, config, seed=chosen_seed)

    # 2. Customers
    print(f"[-] 2/14 Generating {target_cfg.customers} customers...")
    customers = generate_customers(target_cfg.customers, seed=chosen_seed)

    # 3. Product Listings (+ Anomaly 3)
    if inject_anomalies:
        ano3_count = 5 if target_mode == "starter" else 20
    else:
        ano3_count = 0
    print(f"[-] 3/14 Generating {target_cfg.listings} product listings...")
    listings, ano3 = generate_listings(target_cfg.listings, sellers, config, seed=chosen_seed, anomaly_count=ano3_count)

    # 4. Commission Rules
    print(f"[-] 4/14 Generating category & tier commission rules...")
    comm_rules = generate_commission_rules(config)

    # 5 & 6. Orders & Order Lines (Multi-Seller supported)
    print(f"[-] 5/14 & 6/14 Generating {target_cfg.orders} orders and item lines...")
    orders, order_lines = generate_orders(target_cfg.orders, customers, sellers, listings, seed=chosen_seed)

    # 7 & 8. Fulfillments & Fulfillment Events (Split fulfillment supported)
    print(f"[-] 7/14 & 8/14 Generating fulfillments & tracking events...")
    flf_engine = FulfillmentEngine(config)
    fulfillments, flf_events = generate_fulfillments(order_lines, orders, flf_engine, seed=chosen_seed)

    # 9. Customer Reviews
    print(f"[-] 9/14 Generating customer reviews for delivered lines...")
    reviews = generate_reviews(order_lines, orders, fulfillments, seed=chosen_seed)

    # 10. Disputes & Events (+ Anomaly 4)
    if inject_anomalies:
        ano4_count = 5 if target_mode == "starter" else 25
    else:
        ano4_count = 0
    print(f"[-] 10/14 Generating {target_cfg.disputes} disputes & adjudication events...")
    disputes, disp_events, ano4 = generate_disputes(target_cfg.disputes, order_lines, orders, seed=chosen_seed, anomaly_count=ano4_count)

    # 11, 12, 13, 14. Ledgers, Payouts & Payout Lines (+ Anomalies 1, 2, 5)
    if inject_anomalies:
        ano1_count = 5 if target_mode == "starter" else 25
        ano2_count = 5 if target_mode == "starter" else 25
        ano5_count = 5 if target_mode == "starter" else 20
    else:
        ano1_count = 0
        ano2_count = 0
        ano5_count = 0
    print(f"[-] 11-14/14 Generating ledgers, payout batches & events...")
    cml_entries, rsv_entries, payouts, payout_lines, po_events, ano125 = generate_settlements_and_payouts(
        order_lines=order_lines,
        orders=orders,
        sellers=sellers,
        listings=listings,
        fulfillments=fulfillments,
        disputes=disputes,
        commission_rules=comm_rules,
        config=config,
        seed=chosen_seed,
        anomaly_1_count=ano1_count,
        anomaly_2_count=ano2_count,
        anomaly_5_count=ano5_count,
    )

    all_ground_truth = ano3 + ano4 + ano125

    # Batch Insert into SQLite via WAL
    print(f"[-] Committing records to SQLite database via WAL transactions...")
    with db.session() as conn:
        # Clear existing rows
        tables_to_clear = [
            "ground_truth", "payout_events", "payout_lines", "payouts",
            "refunds", "reserve_ledger", "commission_ledger",
            "dispute_events", "disputes", "customer_reviews",
            "fulfillment_events", "fulfillments", "order_lines", "orders",
            "commission_rules", "listings", "customers",
            "seller_status_events", "sellers"
        ]
        for t in tables_to_clear:
            conn.execute(f"DELETE FROM {t};")

        # 1. Sellers
        conn.executemany(
            """INSERT INTO sellers VALUES (
                :seller_id, :name, :tier, :status, :risk_score, :rating,
                :onboarding_date, :bank_account_verified, :country, :created_at, :updated_at
            )""", sellers
        )

        # 2. Seller Status Events
        conn.executemany(
            """INSERT INTO seller_status_events VALUES (
                :event_id, :seller_id, :previous_status, :new_status, :reason, :created_at
            )""", status_events
        )

        # 3. Customers
        conn.executemany(
            """INSERT INTO customers VALUES (
                :customer_id, :name, :email, :city, :state, :country, :created_at
            )""", customers
        )

        # 4. Listings
        conn.executemany(
            """INSERT INTO listings VALUES (
                :listing_id, :seller_id, :title, :category, :price_cents,
                :inventory_count, :status, :created_at, :updated_at
            )""", listings
        )

        # 5. Commission Rules
        conn.executemany(
            """INSERT INTO commission_rules VALUES (
                :rule_id, :category, :seller_tier, :base_rate_basis_points,
                :min_commission_cents, :fixed_fee_cents, :effective_from, :effective_to,
                :is_active, :created_at
            )""", comm_rules
        )

        # 6. Orders
        conn.executemany(
            """INSERT INTO orders VALUES (
                :order_id, :customer_id, :order_date, :total_amount_cents,
                :currency, :payment_method, :order_status, :created_at, :updated_at
            )""", orders
        )

        # 7. Order Lines
        conn.executemany(
            """INSERT INTO order_lines VALUES (
                :order_line_id, :order_id, :seller_id, :listing_id, :line_number,
                :quantity, :unit_price_cents, :gross_amount_cents, :line_status, :created_at
            )""", order_lines
        )

        # 8. Fulfillments
        conn.executemany(
            """INSERT INTO fulfillments VALUES (
                :fulfillment_id, :order_line_id, :order_id, :seller_id, :carrier,
                :tracking_number, :quantity_fulfilled, :dispatched_at, :expected_delivery_at,
                :delivered_at, :sla_status, :transit_days, :created_at
            )""", fulfillments
        )

        # 9. Fulfillment Events
        conn.executemany(
            """INSERT INTO fulfillment_events VALUES (
                :event_id, :fulfillment_id, :event_type, :event_timestamp,
                :location, :notes, :created_at
            )""", flf_events
        )

        # 10. Reviews
        conn.executemany(
            """INSERT INTO customer_reviews VALUES (
                :review_id, :order_line_id, :order_id, :seller_id, :customer_id,
                :rating, :comment, :created_at
            )""", reviews
        )

        # 11. Disputes
        conn.executemany(
            """INSERT INTO disputes VALUES (
                :dispute_id, :order_id, :order_line_id, :seller_id, :customer_id,
                :dispute_date, :dispute_reason, :disputed_amount_cents, :status,
                :resolution_date, :clawback_applied, :created_at
            )""", disputes
        )

        # 12. Dispute Events
        conn.executemany(
            """INSERT INTO dispute_events VALUES (
                :event_id, :dispute_id, :previous_status, :new_status, :actor,
                :notes, :created_at
            )""", disp_events
        )

        # 13. Commission Ledger
        conn.executemany(
            """INSERT INTO commission_ledger VALUES (
                :entry_id, :order_line_id, :seller_id, :rule_id, :gross_amount_cents,
                :rate_basis_points, :variable_fee_cents, :fixed_fee_cents,
                :total_commission_cents, :created_at
            )""", cml_entries
        )

        # 14. Reserve Ledger
        conn.executemany(
            """INSERT INTO reserve_ledger VALUES (
                :entry_id, :order_line_id, :seller_id, :reserve_rate_basis_points,
                :reserve_amount_cents, :hold_days, :release_scheduled_date,
                :status, :released_at, :created_at
            )""", rsv_entries
        )

        # 15. Payouts
        conn.executemany(
            """INSERT INTO payouts VALUES (
                :payout_id, :seller_id, :batch_date, :total_lines_count,
                :gross_sales_cents, :total_commission_cents, :total_reserve_held_cents,
                :total_disputes_deducted_cents, :net_payout_amount_cents,
                :payout_status, :reconciliation_status, :created_at
            )""", payouts
        )

        # 16. Payout Lines
        conn.executemany(
            """INSERT INTO payout_lines VALUES (
                :line_id, :payout_id, :order_line_id, :gross_amount_cents,
                :commission_deducted_cents, :reserve_deducted_cents,
                :dispute_deducted_cents, :net_line_amount_cents, :created_at
            )""", payout_lines
        )

        # 17. Payout Events
        conn.executemany(
            """INSERT INTO payout_events VALUES (
                :event_id, :payout_id, :previous_status, :new_status,
                :gateway_reference, :notes, :created_at
            )""", po_events
        )

        # 18. Ground Truth
        conn.executemany(
            """INSERT INTO ground_truth VALUES (
                :anomaly_id, :anomaly_type, :entity_type, :entity_id,
                :description, :severity, :detected, :created_at
            )""", all_ground_truth
        )

    # Mirror to default DB path if not custom path
    if should_mirror and Path(db_path).resolve() != Path(default_db_path).resolve():
        Path(default_db_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_path, default_db_path)

    elapsed = round(time.time() - start_time, 2)
    print(f"\n✅ Pipeline completed successfully in {elapsed} seconds!")

    # 15. Generate Standalone Ground Truth Exports (ground_truth.csv and ground_truth.json)
    if db_path is not None and Path(db_path).resolve() != Path(default_db_path).resolve():
        data_dir = Path(db_path).parent
    else:
        data_dir = Path(__file__).parent.parent / "data"
    gt_df = pd.DataFrame(all_ground_truth)
    gt_df.to_csv(data_dir / "ground_truth.csv", index=False)
    with open(data_dir / "ground_truth.json", "w", encoding="utf-8") as f:
        json.dump(all_ground_truth, f, indent=2)

    # Also mirror into data/scenarios/
    scenarios_dir = data_dir / "scenarios"
    scenarios_dir.mkdir(parents=True, exist_ok=True)
    gt_df.to_csv(scenarios_dir / "ground_truth.csv", index=False)
    with open(scenarios_dir / "ground_truth.json", "w", encoding="utf-8") as f:
        json.dump(all_ground_truth, f, indent=2)

    # 16. Compute Table Checksums for Manifest
    print(f"[-] Calculating table checksums for generation manifest...")
    table_checksums = {}
    core_tables = [
        "sellers", "customers", "listings", "commission_rules",
        "orders", "order_lines", "fulfillments", "customer_reviews",
        "disputes", "commission_ledger", "reserve_ledger", "payouts", "payout_lines"
    ]
    for ct in core_tables:
        table_checksums[ct] = compute_table_checksum(db, ct)[:16]

    # 17. Manifests
    if db_path is not None and Path(db_path).resolve() != Path(default_db_path).resolve():
        manifest_dir = Path(db_path).parent / "manifests"
    else:
        manifest_dir = Path(__file__).parent.parent / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    summary_data = {
        "generated_at": datetime.now().isoformat(),
        "target_mode": target_mode,
        "seed": chosen_seed,
        "execution_seconds": elapsed,
        "counts": {
            "sellers": len(sellers),
            "seller_status_events": len(status_events),
            "customers": len(customers),
            "listings": len(listings),
            "commission_rules": len(comm_rules),
            "orders": len(orders),
            "order_lines": len(order_lines),
            "fulfillments": len(fulfillments),
            "fulfillment_events": len(flf_events),
            "customer_reviews": len(reviews),
            "disputes": len(disputes),
            "dispute_events": len(disp_events),
            "commission_ledger": len(cml_entries),
            "reserve_ledger": len(rsv_entries),
            "payouts": len(payouts),
            "payout_lines": len(payout_lines),
            "payout_events": len(po_events),
            "ground_truth_anomalies": len(all_ground_truth),
        },
        "anomalies_breakdown": {
            "anomaly_1_premature_payout": sum(1 for a in all_ground_truth if a["anomaly_type"] == "PREMATURE_PAYOUT"),
            "anomaly_2_double_commission": sum(1 for a in all_ground_truth if a["anomaly_type"] == "DOUBLE_COMMISSION"),
            "anomaly_3_suspended_seller_active": sum(1 for a in all_ground_truth if a["anomaly_type"] == "SUSPENDED_SELLER_ACTIVE"),
            "anomaly_4_unclawbacked_dispute": sum(1 for a in all_ground_truth if a["anomaly_type"] == "UNCLAWBACKED_DISPUTE"),
            "anomaly_5_payout_total_mismatch": sum(1 for a in all_ground_truth if a["anomaly_type"] == "PAYOUT_TOTAL_MISMATCH"),
        },
        "table_checksums": table_checksums,
    }

    with open(manifest_dir / "generation_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    source_manifest = {
        "project": config.project_name,
        "version": config.version,
        "seed": chosen_seed,
        "environment": {
            "python_version": sys.version,
            "sqlite_version": "3",
        },
        "pipeline_sequence": [
            "1. sellers",
            "2. customers",
            "3. product listings",
            "4. commission rules",
            "5. orders",
            "6. order lines",
            "7. fulfillments",
            "8. fulfillment events",
            "9. customer reviews",
            "10. disputes",
            "11. commission ledger",
            "12. reserve ledger",
            "13. payouts",
            "14. payout lines",
        ],
        "table_checksums": table_checksums,
    }

    with open(manifest_dir / "source_manifest.json", "w", encoding="utf-8") as f:
        json.dump(source_manifest, f, indent=2)

    print(f"Manifests successfully generated at {manifest_dir}")
    return summary_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic data for SellerOps platform.")
    parser.add_argument("--target", choices=["starter", "full"], default="starter", help="Target scale: starter or full.")
    parser.add_argument("--db-path", type=str, default=None, help="Custom SQLite DB path.")
    parser.add_argument("--seed", type=int, default=None, help="Deterministic random seed.")
    args = parser.parse_args()

    run_pipeline(target_mode=args.target, db_path=args.db_path, seed=args.seed)
