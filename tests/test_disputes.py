"""Test suite for dispute reasons and chargeback processing."""

import pytest
from src.database.connection import get_db


@pytest.fixture(scope="module")
def db():
    return get_db("data/sellerops.db")


def test_disputes_count_and_reasons(db):
    df = db.query_df("SELECT dispute_reason, COUNT(*) as c FROM disputes GROUP BY dispute_reason;")
    assert not df.empty
    reasons = set(df["dispute_reason"])
    expected_reasons = {
        "ITEM_NOT_RECEIVED",
        "SIGNIFICANTLY_NOT_AS_DESCRIBED",
        "UNAUTHORIZED_TRANSACTION",
        "DAMAGED_IN_TRANSIT",
        "DUPLICATE_CHARGE"
    }
    assert expected_reasons.issubset(reasons)


def test_dispute_amounts_positive(db):
    df = db.query_df("SELECT COUNT(*) as invalid_count FROM disputes WHERE disputed_amount <= 0.0;")
    assert df["invalid_count"].iloc[0] == 0
