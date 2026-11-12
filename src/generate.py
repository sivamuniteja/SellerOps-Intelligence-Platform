"""Master Synthetic Data Generator Pipeline for SellerOps Intelligence Platform."""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import PlatformConfig, load_config
from src.database.connection import DatabaseManager
from src.generators.sellers import generate_sellers
from src.generators.customers import generate_customers
from src.generators.listings import generate_listings
from src.generators.orders import generate_orders
from src.generators.fulfillments import generate_fulfillments
from src.generators.reviews import generate_reviews
from src.generators.disputes import generate_disputes
from src.generators.payouts import generate_settlements_and_payouts
from src.services.fulfillment_engine import FulfillmentEngine


def run_pipeline(
    target_mode: str = "starter",
    db_path: Optional[str] = None,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Execute end-to-end data generation pipeline.
    target_mode: 'starter' (fast dev/test) or 'full' (2k sellers, 20k listings, 100k orders, 10k disputes).
    """
    start_time = time.time()
    config = load_config()

    chosen_seed = seed if seed is not None else config.seed
    target_cfg = config.dataset_targets.get(target_mode)
    if not target_cfg:
        raise ValueError(f"Unknown target mode: {target_mode}. Choose 'starter' or 'full'.")

    # Determine database path
    if db_path is None:
        db_path = config.starter_db_path if target_mode == "starter" else config.full_db_path

    # Ensure default data/sellerops.db is updated too for the dashboard
    default_db_path = config.default_db_path

    print(f"\n=======================================================")
    print(f"🚀 Launching SellerOps Synthetic Pipeline [{target_mode.upper()} MODE]")
    print(f"Target DB: {db_path}")
    print(f"Seed: {chosen_seed}")
    print(f"Targets: {target_cfg.sellers} sellers, {target_cfg.listings} listings, {target_cfg.orders} orders, {target_cfg.disputes} disputes")
    print(f"=======================================================\n")

    # Initialize DB schema
    db = DatabaseManager(db_path)
    db.init_schema()

    # 1. Sellers
    print(f"[-] Generating {target_cfg.sellers} sellers...")
    sellers = generate_sellers(target_cfg.sellers, config, seed=chosen_seed)

    # 2. Customers
    print(f"[-] Generating {target_cfg.customers} customers...")
    customers = generate_customers(target_cfg.customers, seed=chosen_seed)

    # 3. Listings (with Anomaly 3)
    print(f"[-] Generating {target_cfg.listings} listings...")
    listings, ano3 = generate_listings(target_cfg.listings, sellers, config, seed=chosen_seed)

    # 4. Orders
    print(f"[-] Generating {target_cfg.orders} orders...")
    orders = generate_orders(target_cfg.orders, customers, sellers, listings, seed=chosen_seed)

    # 5. Fulfillments
    print(f"[-] Generating fulfillments & tracking SLAs...")
    flf_engine = FulfillmentEngine(config)
    fulfillments = generate_fulfillments(orders, flf_engine, seed=chosen_seed)

    # 6. Customer Reviews
    print(f"[-] Generating correlated customer reviews...")
    reviews = generate_reviews(orders, fulfillments, seed=chosen_seed)

    # 7. Disputes (with Anomaly 4)
    print(f"[-] Generating {target_cfg.disputes} disputes & chargebacks...")
    disputes, ano4 = generate_disputes(target_cfg.disputes, orders, seed=chosen_seed)

    # 8. Settlements & Payouts (with Anomalies 1, 2, and 5)
    print(f"[-] Calculating commissions, reserves, payouts & injecting anomalies...")
    settlements, payout_batches, payout_lines, ano125 = generate_settlements_and_payouts(
        orders=orders,
        sellers=sellers,
        listings=listings,
        fulfillments=fulfillments,
        disputes=disputes,
        config=config,
        seed=chosen_seed,
    )

    all_ground_truth = ano3 + ano4 + ano125

    # 9. Batch DB Ingestion
    print(f"[-] Committing records to SQLite database via WAL...")
    with db.session() as conn:
        # Clear existing data
        conn.execute("DELETE FROM payout_lines;")
        conn.execute("DELETE FROM payout_batches;")
        conn.execute("DELETE FROM order_settlements;")
        conn.execute("DELETE FROM disputes;")
        conn.execute("DELETE FROM reviews;")
        conn.execute("DELETE FROM fulfillments;")
        conn.execute("DELETE FROM orders;")
        conn.execute("DELETE FROM listings;")
        conn.execute("DELETE FROM customers;")
        conn.execute("DELETE FROM sellers;")
        conn.execute("DELETE FROM anomalies_ground_truth;")

        # Ingest sellers
        conn.executemany(
            """INSERT INTO sellers VALUES (
                :seller_id, :name, :tier, :status, :risk_score, :rating,
                :onboarding_date, :bank_account_verified, :country, :created_at
            )""",
            sellers,
        )

        # Ingest customers
        conn.executemany(
            """INSERT INTO customers VALUES (
                :customer_id, :name, :email, :city, :state, :country, :created_at
            )""",
            customers,
        )

        # Ingest listings
        conn.executemany(
            """INSERT INTO listings VALUES (
                :listing_id, :seller_id, :title, :category, :price, :inventory_count, :status, :created_at
            )""",
            listings,
        )

        # Ingest orders
        conn.executemany(
            """INSERT INTO orders VALUES (
                :order_id, :customer_id, :seller_id, :listing_id, :order_date,
                :quantity, :unit_price, :gross_amount, :currency, :payment_method, :order_status
            )""",
            orders,
        )

        # Ingest fulfillments
        conn.executemany(
            """INSERT INTO fulfillments VALUES (
                :fulfillment_id, :order_id, :carrier, :tracking_number,
                :dispatched_at, :expected_delivery_at, :delivered_at, :sla_status, :transit_days
            )""",
            fulfillments,
        )

        # Ingest reviews
        conn.executemany(
            """INSERT INTO reviews VALUES (
                :review_id, :order_id, :rating, :comment, :created_at
            )""",
            reviews,
        )

        # Ingest disputes
        conn.executemany(
            """INSERT INTO disputes VALUES (
                :dispute_id, :order_id, :seller_id, :customer_id, :dispute_date,
                :dispute_reason, :disputed_amount, :status, :resolution_date, :clawback_applied
            )""",
            disputes,
        )

        # Ingest order settlements
        conn.executemany(
            """INSERT INTO order_settlements VALUES (
                :settlement_id, :order_id, :seller_id, :gross_amount,
                :commission_rate, :commission_amount, :reserve_rate, :reserve_amount,
                :reserve_release_date, :reserve_released, :net_seller_amount,
                :is_eligible_for_payout, :created_at
            )""",
            settlements,
        )

        # Ingest payout batches
        conn.executemany(
            """INSERT INTO payout_batches VALUES (
                :payout_id, :seller_id, :batch_date, :total_orders_count,
                :gross_sales, :total_commission, :total_reserve_held, :total_disputes_deducted,
                :net_payout_amount, :payout_status, :reconciliation_status, :created_at
            )""",
            payout_batches,
        )

        # Ingest payout lines
        conn.executemany(
            """INSERT INTO payout_lines VALUES (
                :line_id, :payout_id, :order_id, :order_amount,
                :commission_deducted, :reserve_deducted, :dispute_deducted,
                :net_line_amount, :created_at
            )""",
            payout_lines,
        )

        # Ingest ground truth anomalies
        conn.executemany(
            """INSERT INTO anomalies_ground_truth VALUES (
                :anomaly_id, :anomaly_type, :entity_type, :entity_id,
                :description, :severity, :detected, :created_at
            )""",
            all_ground_truth,
        )

    # Also mirror to default_db_path if different
    if Path(db_path).resolve() != Path(default_db_path).resolve():
        Path(default_db_path).parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(db_path, default_db_path)

    elapsed = round(time.time() - start_time, 2)
    print(f"\n✅ Pipeline completed successfully in {elapsed} seconds!")

    # 10. Generate Manifests
    manifest_dir = Path(__file__).parent.parent / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    summary_data = {
        "generated_at": datetime.now().isoformat(),
        "target_mode": target_mode,
        "seed": chosen_seed,
        "execution_seconds": elapsed,
        "counts": {
            "sellers": len(sellers),
            "customers": len(customers),
            "listings": len(listings),
            "orders": len(orders),
            "fulfillments": len(fulfillments),
            "reviews": len(reviews),
            "disputes": len(disputes),
            "settlements": len(settlements),
            "payout_batches": len(payout_batches),
            "payout_lines": len(payout_lines),
            "ground_truth_anomalies": len(all_ground_truth),
        },
        "anomalies_breakdown": {
            "anomaly_1_premature_payout": sum(1 for a in all_ground_truth if a["anomaly_type"] == "PREMATURE_PAYOUT"),
            "anomaly_2_double_commission": sum(1 for a in all_ground_truth if a["anomaly_type"] == "DOUBLE_COMMISSION"),
            "anomaly_3_suspended_seller_active": sum(1 for a in all_ground_truth if a["anomaly_type"] == "SUSPENDED_SELLER_ACTIVE"),
            "anomaly_4_unclawbacked_dispute": sum(1 for a in all_ground_truth if a["anomaly_type"] == "UNCLAWBACKED_DISPUTE"),
            "anomaly_5_payout_total_mismatch": sum(1 for a in all_ground_truth if a["anomaly_type"] == "PAYOUT_TOTAL_MISMATCH"),
        }
    }

    with open(manifest_dir / "generation_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    source_manifest = {
        "project": config.project_name,
        "version": config.version,
        "environment": {
            "python_version": sys.version,
            "sqlite_version": "3",
        },
        "generators": {
            "sellers": "src.generators.sellers",
            "customers": "src.generators.customers",
            "listings": "src.generators.listings",
            "orders": "src.generators.orders",
            "fulfillments": "src.generators.fulfillments",
            "reviews": "src.generators.reviews",
            "disputes": "src.generators.disputes",
            "payouts": "src.generators.payouts",
        },
        "config_snapshot": {
            "categories_count": len(config.categories),
            "tiers": list(config.seller_tiers.keys()),
            "sla_thresholds": config.sla_thresholds,
            "seed": chosen_seed,
        }
    }

    with open(manifest_dir / "source_manifest.json", "w", encoding="utf-8") as f:
        json.dump(source_manifest, f, indent=2)

    print(f"Manifests successfully written to {manifest_dir}")
    return summary_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic data for SellerOps platform.")
    parser.add_argument("--target", choices=["starter", "full"], default="starter", help="Target dataset scale.")
    parser.add_argument("--db-path", type=str, default=None, help="Custom SQLite DB path.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility.")
    args = parser.parse_args()

    run_pipeline(target_mode=args.target, db_path=args.db_path, seed=args.seed)
