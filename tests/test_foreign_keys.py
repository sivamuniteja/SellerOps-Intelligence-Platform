"""Test suite for database foreign key and referential integrity."""

import sqlite3
import pytest
from src.database.connection import get_db
from src.validation.integrity import IntegrityValidator


@pytest.fixture(scope="module")
def db():
    return get_db("data/sellerops.db")


def test_no_foreign_key_violations(db):
    validator = IntegrityValidator(db)
    result = validator.check_foreign_keys()
    assert result["valid"] is True, f"Foreign key check failed: {result['violations']}"
    assert result["violations_count"] == 0


def test_foreign_key_enforcement_prevents_orphan(db):
    """Verify that SQLite raises an IntegrityError when foreign key is violated."""
    with pytest.raises(sqlite3.IntegrityError):
        with db.session() as conn:
            conn.execute(
                """INSERT INTO orders VALUES (
                    'ORD-999999', 'CST-NONEXISTENT', 'SLR-NONEXISTENT', 'LST-NONEXISTENT',
                    '2026-01-01 00:00:00', 1, 50.0, 50.0, 'USD', 'CREDIT_CARD', 'PLACED'
                );"""
            )
