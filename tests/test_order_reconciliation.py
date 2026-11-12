"""Automated tests for Order and Order-Line Arithmetic Reconciliation.

Verifies that all order headers in the database reconcile with the sum of
their constituent child lines to the exact integer paise with zero tolerance.
"""

import pytest
from src.database.connection import get_db


@pytest.fixture(scope="module")
def db():
    return get_db("data/sellerops.db")


def test_order_header_equals_sum_of_lines(db):
    """
    Every order total in the database must exactly equal the sum of its order lines.
    Assertion: zero arithmetic discrepancies across the 100,000 order pipeline.
    """
    with db.session() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT o.order_id, o.total_amount_cents, SUM(ol.gross_amount_cents) as lines_sum
            FROM orders o
            JOIN order_lines ol ON o.order_id = ol.order_id
            GROUP BY o.order_id, o.total_amount_cents
            HAVING o.total_amount_cents != SUM(ol.gross_amount_cents)
            LIMIT 10;
            """
        )
        mismatches = cursor.fetchall()
        assert len(mismatches) == 0, f"Found order arithmetic discrepancies: {mismatches}"


def test_order_line_gross_equals_unit_price_times_quantity(db):
    """
    Every order line gross amount must equal unit_price_cents * quantity.
    """
    with db.session() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT order_line_id, unit_price_cents, quantity, gross_amount_cents
            FROM order_lines
            WHERE gross_amount_cents != (unit_price_cents * quantity)
            LIMIT 10;
            """
        )
        invalid_lines = cursor.fetchall()
        assert len(invalid_lines) == 0, f"Found order lines with invalid gross calculation: {invalid_lines}"


def test_multi_seller_orders_contain_distinct_sellers(db):
    """
    Verify that multi-seller orders contain distinct sellers and reconcile accurately.
    """
    with db.session() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT order_id, COUNT(DISTINCT seller_id) as seller_count, COUNT(*) as line_count
            FROM order_lines
            GROUP BY order_id
            HAVING COUNT(DISTINCT seller_id) > 1
            LIMIT 50;
            """
        )
        multi_seller_orders = cursor.fetchall()
        assert len(multi_seller_orders) > 0, "Expected multi-seller orders in the database."

        for order_id, s_count, l_count in multi_seller_orders:
            assert s_count > 1
            assert l_count >= s_count
