"""Test suite for Phase 8 Data Export and Reporting Engine."""

import hashlib
import json
import sqlite3
from pathlib import Path
import pytest
from src.database.connection import get_db
from src.exports.csv_export import CsvExporter, ORDERED_TABLES
from src.exports.json_export import JsonExporter
from src.exports.sql_export import SqlExporter
from src.exports.manager import ExportManager


@pytest.fixture(scope="module")
def db():
    return get_db("data/sellerops.db")


def test_csv_export_structure_and_headers(db, tmp_path):
    exporter = CsvExporter(db)
    csv_file = tmp_path / "sellers_test.csv"
    res = exporter.export_table("sellers", csv_file)

    assert res["status"] == "SUCCESS"
    assert res["row_count"] == 2000
    assert csv_file.exists()

    with open(csv_file, "r", encoding="utf-8") as f:
        header = f.readline().strip().split(",")
    assert "seller_id" in header
    assert "tier" in header
    assert "status" in header
    assert "risk_score" in header


def test_json_export_structure_and_types(db, tmp_path):
    exporter = JsonExporter(db)
    json_file = tmp_path / "listings_test.json"
    res = exporter.export_table("listings", json_file, limit=100)

    assert res["status"] == "SUCCESS"
    assert res["row_count"] == 100
    assert json_file.exists()

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list)
    assert len(data) == 100
    item = data[0]
    assert "listing_id" in item
    assert "price_cents" in item
    assert isinstance(item["price_cents"], int)  # Preserves integer cents


def test_sql_seed_data_syntax_and_dependencies(db, tmp_path):
    exporter = SqlExporter(db)
    sql_file = tmp_path / "seed_test.sql"
    res = exporter.export_seed_data(
        sql_file,
        seller_id="SELL-000001",
        include_schema=True,
    )

    assert res["status"] == "SUCCESS"
    assert res["total_rows"] > 0
    assert sql_file.exists()

    with open(sql_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert "PRAGMA foreign_keys = OFF;" in content
    assert "BEGIN TRANSACTION;" in content
    assert "INSERT INTO" in content
    assert "COMMIT;" in content
    assert "PRAGMA foreign_key_check;" in content


def test_isolated_ground_truth_export(db, tmp_path):
    csv_exp = CsvExporter(db)
    json_exp = JsonExporter(db)
    sql_exp = SqlExporter(db)

    csv_path = tmp_path / "gt.csv"
    json_path = tmp_path / "gt.json"
    sql_path = tmp_path / "gt.sql"

    c_res = csv_exp.export_ground_truth(csv_path)
    j_res = json_exp.export_ground_truth(json_path)
    s_res = sql_exp.export_ground_truth_sql(sql_path)

    assert c_res["row_count"] == 115
    assert j_res["row_count"] == 115
    assert s_res["total_rows"] == 115

    with open(json_path, "r", encoding="utf-8") as f:
        gt_data = json.load(f)
    assert "records" in gt_data
    assert len(gt_data["records"]) == 115


def test_seller_and_date_filtering(db, tmp_path):
    exporter = CsvExporter(db)

    # Seller filter
    seller_orders_path = tmp_path / "seller_orders.csv"
    res_seller = exporter.export_table("orders", seller_orders_path, seller_id="SELL-000001")
    assert res_seller["row_count"] == 44

    # Date filter
    date_orders_path = tmp_path / "date_orders.csv"
    res_date = exporter.export_table(
        "orders", date_orders_path, start_date="2026-01-01", end_date="2026-01-31"
    )
    assert res_date["row_count"] > 0
    assert res_date["row_count"] < 100000


def test_sha256_checksums_integrity():
    checksums_file = Path("data/exports/checksums.json")
    assert checksums_file.exists(), "Checksums JSON manifest missing"

    with open(checksums_file, "r", encoding="utf-8") as f:
        meta = json.load(f)

    base_dir = Path("data/exports")
    # Verify sample files
    sample_keys = [
        "csv/sellers.csv",
        "csv/orders.csv",
        "json/listings.json",
        "ground_truth/ground_truth.csv",
    ]

    for rel_k in sample_keys:
        assert rel_k in meta["files"]
        target_path = base_dir / rel_k
        assert target_path.exists()

        hasher = hashlib.sha256()
        with open(target_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        assert hasher.hexdigest() == meta["files"][rel_k]["sha256"]


def test_reimport_round_trip_and_financial_accuracy(db, tmp_path):
    sql_exp = SqlExporter(db)
    test_sql_file = tmp_path / "filtered_seed.sql"
    target_db = tmp_path / "reimport_verification.db"

    # Export a representative seller dataset
    sql_exp.export_seed_data(
        test_sql_file,
        seller_id="SELL-000001",
        include_schema=True,
    )

    # Re-import and verify
    reimport_res = sql_exp.verify_reimport_sql(test_sql_file, target_db, seller_id="SELL-000001")
    assert reimport_res["valid"] is True
    assert reimport_res["foreign_key_violations_count"] == 0
    assert reimport_res["financial_accuracy"]["gmv_matched"] is True
    assert reimport_res["financial_accuracy"]["payout_matched"] is True


def test_no_credentials_leaked():
    base_dir = Path("data/exports/csv")
    sensitive_keywords = ["password", "secret", "private_key", "api_key", "auth_token"]

    for csv_file in base_dir.glob("*.csv"):
        with open(csv_file, "r", encoding="utf-8") as f:
            header = f.readline().lower()
            for kw in sensitive_keywords:
                assert kw not in header, f"Sensitive column {kw} found in {csv_file.name}"
