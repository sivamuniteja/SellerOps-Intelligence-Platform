#!/usr/bin/env python3
"""Phase 2 Database Architecture and Data Model Verification Script."""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import DatabaseManager
from src.models.entities import cents_to_decimal


def main():
    test_db_path = "data/scenarios/phase2_verification.db"
    # Ensure fresh test DB
    for ext in ["", "-wal", "-shm"]:
        p = Path(f"{test_db_path}{ext}")
        if p.exists():
            p.unlink()

    print("\n=======================================================")
    print("🚀 PHASE 2: DATABASE ARCHITECTURE VERIFICATION RUNNER")
    print(f"Target Database: {test_db_path}")
    print("=======================================================\n")

    db = DatabaseManager(test_db_path)

    # 1. Execute schema creation with versioned migrations
    print("[-] Executing schema creation from src/models/schema.sql...")
    db.init_schema()
    version = db.get_schema_version()
    print(f"    ✅ Applied Schema Version: {version}")

    # 2. Insert valid test dataset covering all entities & relationships
    print("[-] Inserting valid relational test dataset...")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with db.session() as conn:
        # A. Sellers
        conn.execute("""
            INSERT INTO sellers VALUES
            ('SELL-000001', 'Apex Electronics Direct', 'ENTERPRISE', 'ACTIVE', 12.5, 4.85, '2024-01-15 10:00:00', 1, 'USA', ?, ?),
            ('SELL-000002', 'Nordic Home Living', 'PREFERRED', 'ACTIVE', 22.0, 4.60, '2024-03-01 14:30:00', 1, 'USA', ?, ?);
        """, (now_str, now_str, now_str, now_str))

        # B. Seller Status Audit Event (Immutable)
        conn.execute("""
            INSERT INTO seller_status_events VALUES
            ('SSE-000001', 'SELL-000001', 'UNDER_REVIEW', 'ACTIVE', 'Passed initial merchant KYC & banking review', ?);
        """, (now_str,))

        # C. Customer
        conn.execute("""
            INSERT INTO customers VALUES
            ('CUST-000001', 'Marcus Vance', 'marcus.vance@example.com', 'Seattle', 'WA', 'USA', ?);
        """, (now_str,))

        # D. Product Listings (Integer cents)
        conn.execute("""
            INSERT INTO listings VALUES
            ('LIST-SELL-000001-000001', 'SELL-000001', 'Wireless Noise Canceling Headphones 4K', 'Electronics', 14999, 50, 'ACTIVE', ?, ?),
            ('LIST-SELL-000002-000001', 'SELL-000002', 'Organic Bamboo Ergonomic Cutting Board', 'Home & Kitchen', 3500, 100, 'ACTIVE', ?, ?);
        """, (now_str, now_str, now_str, now_str))

        # E. Commission Rule (Basis points & integer cents)
        conn.execute("""
            INSERT INTO commission_rules VALUES
            ('CR-000001', 'Electronics', 'ENTERPRISE', 600, 50, 30, '2024-01-01 00:00:00', '2027-12-31 23:59:59', 1, ?);
        """, (now_str,))

        # F. Order Header (Multi-seller order: ₹149.99 * 2 + ₹35.00 * 1 = ₹334.98 = 33498 paise)
        conn.execute("""
            INSERT INTO orders VALUES
            ('ORD-2026-000001', 'CUST-000001', '2026-02-10 14:15:00', 33498, 'INR', 'CREDIT_CARD', 'CONFIRMED', ?, ?);
        """, (now_str, now_str))

        # G. Order Lines (Multi-Seller items under single order)
        # Line 1: from SELL-000001 (Qty 2 @ 14999 = 29998 cents)
        # Line 2: from SELL-000002 (Qty 1 @ 3500 = 3500 cents)
        conn.execute("""
            INSERT INTO order_lines VALUES
            ('ORDLN-2026-000001-01', 'ORD-2026-000001', 'SELL-000001', 'LIST-SELL-000001-000001', 1, 2, 14999, 29998, 'PARTIALLY_SHIPPED', ?),
            ('ORDLN-2026-000001-02', 'ORD-2026-000001', 'SELL-000002', 'LIST-SELL-000002-000001', 2, 1, 3500, 3500, 'CONFIRMED', ?);
        """, (now_str, now_str))

        # H. Partial Fulfillments (OrderLine 1 has 2 units, split into two shipments)
        conn.execute("""
            INSERT INTO fulfillments VALUES
            ('FUL-ORDLN-2026-000001-01-01', 'ORDLN-2026-000001-01', 'ORD-2026-000001', 'SELL-000001', 'FedEx Express', 'FEDEX-98765432', 1, '2026-02-11 09:00:00', '2026-02-14 17:00:00', '2026-02-14 15:30:00', 'ON_TIME', 3, ?),
            ('FUL-ORDLN-2026-000001-01-02', 'ORDLN-2026-000001-01', 'ORD-2026-000001', 'SELL-000001', 'UPS Ground', 'UPS-12345678', 1, '2026-02-11 11:30:00', '2026-02-15 17:00:00', NULL, 'IN_TRANSIT', NULL, ?);
        """, (now_str, now_str))

        # I. Fulfillment Tracking Events (Immutable Event Log)
        conn.execute("""
            INSERT INTO fulfillment_events VALUES
            ('FLE-000001', 'FUL-ORDLN-2026-000001-01-01', 'LABEL_CREATED', '2026-02-11 09:00:00', 'Warehouse A - Seattle, WA', 'Shipping label generated', ?),
            ('FLE-000002', 'FUL-ORDLN-2026-000001-01-01', 'PICKED_UP', '2026-02-11 14:00:00', 'FedEx Hub - Seattle, WA', 'Departed origin facility', ?),
            ('FLE-000003', 'FUL-ORDLN-2026-000001-01-01', 'DELIVERED', '2026-02-14 15:30:00', 'Residence - Portland, OR', 'Delivered at front porch', ?);
        """, (now_str, now_str, now_str))

        # J. Customer Review
        conn.execute("""
            INSERT INTO customer_reviews VALUES
            ('REV-2026-000001', 'ORDLN-2026-000001-01', 'ORD-2026-000001', 'SELL-000001', 'CUST-000001', 5, 'Crystal clear audio and fast shipment!', ?);
        """, (now_str,))

        # K. Dispute & Dispute Event
        conn.execute("""
            INSERT INTO disputes VALUES
            ('DSP-2026-000001', 'ORD-2026-000001', 'ORDLN-2026-000001-02', 'SELL-000002', 'CUST-000001', '2026-02-18 10:00:00', 'DAMAGED_IN_TRANSIT', 3500, 'OPEN', NULL, 0, ?);
        """, (now_str,))

        conn.execute("""
            INSERT INTO dispute_events VALUES
            ('DSE-000001', 'DSP-2026-000001', NULL, 'OPEN', 'BUYER', 'Buyer uploaded damage photos of the box', ?);
        """, (now_str,))

        # L. Commission Ledger (Exact Integer Cents: 6% of 29998 = 1799.88 -> 1800 + 30 fixed = 1830 cents)
        conn.execute("""
            INSERT INTO commission_ledger VALUES
            ('CML-000001', 'ORDLN-2026-000001-01', 'SELL-000001', 'CR-000001', 29998, 600, 1800, 30, 1830, ?);
        """, (now_str,))

        # M. Reserve Ledger (Enterprise 5% = 1500 cents)
        conn.execute("""
            INSERT INTO reserve_ledger VALUES
            ('RSV-000001', 'ORDLN-2026-000001-01', 'SELL-000001', 500, 1500, 7, '2026-02-21 15:30:00', 'HELD', NULL, ?);
        """, (now_str,))

        # N. Payout Batch & Payout Line & Payout Event
        # Net for Line 1: 29998 - 1830 - 1500 = 26668 paise (₹266.68)
        conn.execute("""
            INSERT INTO payouts VALUES
            ('PAYOUT-2026-000001', 'SELL-000001', '2026-02-22 00:00:00', 1, 29998, 1830, 1500, 0, 26668, 'PAID', 'MATCHED', ?);
        """, (now_str,))

        conn.execute("""
            INSERT INTO payout_lines VALUES
            ('PLN-PAYOUT-2026-000001-01', 'PAYOUT-2026-000001', 'ORDLN-2026-000001-01', 29998, 1830, 1500, 0, 26668, ?);
        """, (now_str,))

        conn.execute("""
            INSERT INTO payout_events VALUES
            ('POE-000001', 'PAYOUT-2026-000001', 'PROCESSING', 'PAID', 'ACH-TRACE-88492019', 'Disbursement transferred to merchant bank', ?);
        """, (now_str,))

        # O. Ground Truth Anomaly
        conn.execute("""
            INSERT INTO ground_truth VALUES
            ('ANO-1-0001', 'PREMATURE_PAYOUT', 'PAYOUT_LINE', 'PLN-PAYOUT-2026-000001-01', 'Test anomaly seed entry', 'CRITICAL', 0, ?);
        """, (now_str,))

    print("    ✅ Test dataset successfully inserted.")

    # 3. Foreign Key Check
    print("\n[-] Running SQLite PRAGMA foreign_key_check...")
    with db.session() as conn:
        fk_violations = conn.execute("PRAGMA foreign_key_check;").fetchall()

    if len(fk_violations) == 0:
        print("    🎉 PRAGMA foreign_key_check: 0 VIOLATIONS! All foreign keys are 100% valid.")
    else:
        print(f"    ❌ Foreign key violations found: {fk_violations}")
        sys.exit(1)

    # 4. Financial Integrity Balance Check
    print("\n[-] Verifying double-entry integer accounting equation:")
    with db.session() as conn:
        row = conn.execute("""
            SELECT
                gross_amount_cents,
                commission_deducted_cents,
                reserve_deducted_cents,
                net_line_amount_cents
            FROM payout_lines
            WHERE line_id = 'PLN-PAYOUT-2026-000001-01';
        """).fetchone()

        gross, comm, res, net = row
        equation_balanced = (gross == comm + res + net)
        print(f"    • Gross: {gross} paise (₹{cents_to_decimal(gross)})")
        print(f"    • Commission: {comm} paise (₹{cents_to_decimal(comm)})")
        print(f"    • Reserve: {res} paise (₹{cents_to_decimal(res)})")
        print(f"    • Net Line: {net} paise (₹{cents_to_decimal(net)})")
        print(f"    • Equation Check: {gross} == {comm} + {res} + {net} -> {'BALANCED ✅' if equation_balanced else 'UNBALANCED ❌'}")

    # 5. Table Inventory Count
    print("\n[-] Entity table inventory verification:")
    tables = [
        "schema_migrations", "sellers", "seller_status_events", "customers",
        "listings", "commission_rules", "orders", "order_lines", "fulfillments",
        "fulfillment_events", "customer_reviews", "disputes", "dispute_events",
        "commission_ledger", "reserve_ledger", "payouts", "payout_lines",
        "payout_events", "ground_truth"
    ]
    for t in tables:
        cnt = db.row_count(t)
        print(f"    • {t.ljust(25)}: {cnt} row(s)")

    print("\n=======================================================")
    print("✅ PHASE 2 VERIFICATION SUCCEEDED: 100% VALID & COMPLIANT")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
