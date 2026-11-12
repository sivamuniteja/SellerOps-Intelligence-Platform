"""Test suite for deterministic synthetic data generation."""

import hashlib
from src.database.connection import get_db
from src.generate import run_pipeline


def compute_table_hash(db, table_name: str) -> str:
    with db.session() as conn:
        cursor = conn.execute(f"SELECT * FROM {table_name} ORDER BY 1;")
        hasher = hashlib.sha256()
        for row in cursor.fetchall():
            row_str = "|".join(str(val) for val in row)
            hasher.update(row_str.encode("utf-8"))
        return hasher.hexdigest()


def test_generation_reproducibility(tmp_path):
    db1_path = str(tmp_path / "test_run1.db")
    db2_path = str(tmp_path / "test_run2.db")

    # Generate two starter datasets with the same seed
    run_pipeline(target_mode="starter", db_path=db1_path, seed=42)
    run_pipeline(target_mode="starter", db_path=db2_path, seed=42)

    db1 = get_db(db1_path)
    db2 = get_db(db2_path)

    for table in ["sellers", "customers", "listings", "orders", "anomalies_ground_truth"]:
        h1 = compute_table_hash(db1, table)
        h2 = compute_table_hash(db2, table)
        assert h1 == h2, f"Table {table} differed between deterministic runs"
