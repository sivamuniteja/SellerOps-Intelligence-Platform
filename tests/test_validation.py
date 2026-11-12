"""Test suite for full platform data validation dimensions and reporting."""

from pathlib import Path
import pytest
from src.database.connection import get_db
from src.validation.integrity import IntegrityValidator
from src.validation.lifecycle import LifecycleValidator
from src.validation.reconciliation import FinancialReconciliation
from src.validation.validator import FullPlatformValidator


@pytest.fixture(scope="module")
def baseline_db():
    return get_db("data/scenarios/sellerops_baseline.db")


@pytest.fixture(scope="module")
def full_db():
    return get_db("data/sellerops.db")


def test_baseline_passes_all_validations(baseline_db, tmp_path):
    """Verify that a clean baseline dataset passes 100% of all 14 validation dimensions."""
    validator = FullPlatformValidator(baseline_db)
    report_file = tmp_path / "test_baseline_report.json"
    report = validator.run_validation(export_path=str(report_file))

    meta = report["metadata"]
    assert meta["core_integrity_valid"] is True
    assert meta["failed_checks_count"] == 0
    assert meta["passed_checks_count"] == 14

    dims = report["validation_dimensions"]
    assert dims["primary_key_uniqueness"]["passed"] is True
    assert dims["foreign_key_integrity"]["passed"] is True
    assert dims["id_formats"]["passed"] is True
    assert dims["required_values"]["passed"] is True
    assert dims["enum_validation"]["passed"] is True
    assert dims["date_ordering"]["passed"] is True
    assert dims["order_total_reconciliation"]["passed"] is True
    assert dims["commission_correctness"]["passed"] is True
    assert dims["reserve_reconciliation"]["passed"] is True
    assert dims["dispute_deductions"]["passed"] is True
    assert dims["payout_reconciliation"]["passed"] is True
    assert dims["duplicate_detection"]["passed"] is True
    assert dims["lifecycle_transitions"]["passed"] is True
    assert dims["reproducibility"]["passed"] is True


def test_integrity_validator_checks(full_db):
    """Verify primary keys, foreign keys, ID formats, and enum values."""
    iv = IntegrityValidator(full_db)

    # 1. Foreign keys
    fk_res = iv.check_foreign_keys()
    assert fk_res["valid"] is True
    assert fk_res["violations_count"] == 0

    # 2. Primary keys
    pk_res = iv.check_primary_keys()
    assert pk_res["valid"] is True

    # 3. ID formats
    id_res = iv.check_id_formats()
    assert id_res["valid"] is True

    # 4. Null constraints
    null_res = iv.check_null_constraints()
    assert null_res["valid"] is True

    # 5. Enum validation
    enum_res = iv.check_enum_constraints()
    assert enum_res["valid"] is True


def test_lifecycle_chronology_checks(full_db):
    """Verify chronological sequence of fulfillment and dispute events."""
    lv = LifecycleValidator(full_db)

    # 1. Fulfillment chronology
    flf_res = lv.check_fulfillment_chronology()
    assert flf_res["valid"] is True

    # 2. Dispute chronology
    disp_res = lv.check_dispute_chronology()
    assert disp_res["valid"] is True

    # 3. Reserve hold chronology
    res_res = lv.check_reserve_hold_chronology()
    assert res_res["valid"] is True


def test_financial_reconciliation_checks(baseline_db):
    """Verify exact ledger reconciliation on baseline data."""
    fr = FinancialReconciliation(baseline_db)
    rec = fr.reconcile_all()

    assert rec["is_fully_reconciled"] is True
    assert rec["order_lines"]["valid"] is True
    assert rec["payouts"]["valid"] is True
    assert rec["commissions"]["valid"] is True
    assert rec["reserves"]["valid"] is True
    assert rec["disputes"]["valid"] is True


def test_machine_readable_report_generation(full_db, tmp_path):
    """Verify that FullPlatformValidator creates an actual valid JSON report."""
    report_file = tmp_path / "val_report.json"
    validator = FullPlatformValidator(full_db)
    report = validator.run_validation(export_path=str(report_file))

    assert report_file.exists()
    assert "metadata" in report
    assert "validation_dimensions" in report
    assert "anomaly_detection" in report
    assert report["metadata"]["total_checks_evaluated"] == 14
