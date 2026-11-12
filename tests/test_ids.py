"""Test suite for canonical ID format conventions."""

import re
import pytest
from src.database.connection import get_db

ID_PATTERNS = {
    "sellers": ("seller_id", r"^SELL-\d{6}$"),
    "customers": ("customer_id", r"^CUST-\d{6}$"),
    "listings": ("listing_id", r"^LIST-SELL-\d{6}-\d{6}$"),
    "orders": ("order_id", r"^ORD-\d{4}-\d{6}$"),
    "order_lines": ("order_line_id", r"^ORDLN-\d{4}-\d{6}-\d{2}$"),
    "fulfillments": ("fulfillment_id", r"^FUL-ORDLN-\d{4}-\d{6}-\d{2}(-\d{2})?$"),
    "customer_reviews": ("review_id", r"^REV-\d{4}-\d{6}$"),
    "disputes": ("dispute_id", r"^DSP-\d{4}-\d{6}$"),
    "payouts": ("payout_id", r"^PAYOUT-(PREM-)?(\d{4}-)?\d{4,6}$"),
}


@pytest.fixture(scope="module")
def db():
    return get_db("data/sellerops.db")


@pytest.mark.parametrize("table,col_and_pattern", ID_PATTERNS.items())
def test_id_format(db, table, col_and_pattern):
    col, pattern = col_and_pattern
    df = db.query_df(f"SELECT {col} FROM {table} LIMIT 500;")
    assert not df.empty, f"Table {table} is empty"

    compiled = re.compile(pattern)
    for val in df[col]:
        assert compiled.match(val), f"Invalid ID format in {table}.{col}: '{val}' does not match '{pattern}'"
