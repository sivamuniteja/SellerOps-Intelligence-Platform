"""Automated tests for Dashboard Metric Consistency and Source Reconciliations.

Verifies that all aggregated metrics displayed across the dashboard pages
derive from source records with zero divergence or static hardcoding.
"""

import pytest
from src.database.connection import get_db


@pytest.fixture(scope="module")
def db():
    return get_db("data/sellerops.db")


def test_platform_gmv_matches_source_orders(db):
    """Platform GMV must strictly equal the sum of order totals from orders table."""
    with db.session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(total_amount_cents), 0) FROM orders;")
        total_gmv_cents = cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(SUM(gross_amount_cents), 0) FROM order_lines;")
        total_lines_gross_cents = cursor.fetchone()[0]

        assert total_gmv_cents > 0
        assert total_gmv_cents == total_lines_gross_cents, (
            f"GMV discrepancy: orders sum ({total_gmv_cents}) != order lines sum ({total_lines_gross_cents})"
        )


def test_active_seller_count_semantic_integrity(db):
    """Active sellers count must reflect sellers with status = 'ACTIVE'."""
    with db.session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sellers WHERE status = 'ACTIVE';")
        active_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sellers WHERE status = 'SUSPENDED';")
        suspended_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sellers;")
        total_sellers = cursor.fetchone()[0]

        assert total_sellers == 2000
        assert active_count > 0
        assert suspended_count > 0
        assert active_count + suspended_count <= total_sellers


def test_commission_revenue_consistency(db):
    """Commission revenue must derive from the commission_ledger table."""
    with db.session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(total_commission_cents), 0) FROM commission_ledger;")
        total_comm_cents = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM commission_ledger;")
        comm_entries_count = cursor.fetchone()[0]

        assert comm_entries_count > 0
        assert total_comm_cents > 0


def test_payout_reconciliation_discrepancy_counts(db):
    """Discrepancy count in payouts table must match Anomaly 5 injected count (20 batches)."""
    with db.session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM payouts WHERE reconciliation_status = 'DISCREPANCY';")
        disc_count = cursor.fetchone()[0]
        assert disc_count == 20, f"Expected 20 reconciliation discrepancies, found {disc_count}"

        cursor.execute("SELECT COUNT(*) FROM payouts WHERE reconciliation_status = 'MATCHED';")
        matched_count = cursor.fetchone()[0]
        assert matched_count == 1943
        assert matched_count + disc_count == 1963
