"""Test suite for canonical ID format conventions."""

import re
import pytest
from src.database.connection import get_db

ID_PATTERNS = {
    "sellers": ("seller_id", r"^SLR-\d{5}$"),
    "customers": ("customer_id", r"^CST-\d{5}$"),
    "listings": ("listing_id", r"^LST-\d{6}$"),
    "orders": ("order_id", r"^ORD-\d{6}$"),
    "fulfillments": ("fulfillment_id", r"^FLF-\d{6}$"),
    "reviews": ("review_id", r"^REV-\d{6}$"),
    "disputes": ("dispute_id", r"^DSP-\d{6}$"),
    "payout_batches": ("payout_id", r"^PO-(PREM-)?\d{4,6}$"),
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
