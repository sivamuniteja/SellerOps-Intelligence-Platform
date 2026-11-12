"""Test suite for operational exceptions, anomaly detection rules, and benchmark metrics."""

import pytest
from src.database.connection import get_db
from src.validation.anomaly_detection import AnomalyDetectionEngine


@pytest.fixture(scope="module")
def anomaly_engine():
    db = get_db("data/sellerops.db")
    return AnomalyDetectionEngine(db)


@pytest.fixture(scope="module")
def baseline_engine():
    db = get_db("data/scenarios/sellerops_baseline.db")
    return AnomalyDetectionEngine(db)


def test_detect_all_anomalies(anomaly_engine):
    """Verify counts and 100% benchmark metrics on full scenario database."""
    report = anomaly_engine.run_all_detectors()
    summary = report["summary"]

    assert summary["anomaly_1_count"] == 25, "Anomaly 1 (Premature Payout) count mismatch"
    assert summary["anomaly_2_count"] == 25, "Anomaly 2 (Double Commission) count mismatch"
    assert summary["anomaly_3_count"] == 20, "Anomaly 3 (Suspended Seller Active) count mismatch"
    assert summary["anomaly_4_count"] == 25, "Anomaly 4 (Unclawbacked Dispute) count mismatch"
    assert summary["anomaly_5_count"] == 20, "Anomaly 5 (Payout Total Mismatch) count mismatch"

    assert summary["precision"] == 1.0, f"Precision was {summary['precision']}"
    assert summary["recall"] == 1.0, f"Recall was {summary['recall']}"
    assert summary["f1_score"] == 1.0, f"F1 score was {summary['f1_score']}"
    assert summary["false_positives"] == 0


def test_anomaly_record_structure(anomaly_engine):
    """Verify all detected anomaly records include required metadata fields."""
    report = anomaly_engine.run_all_detectors()
    all_records = report["all_detected_list"]
    assert len(all_records) == 115

    required_fields = [
        "scenario_id",
        "entity_id",
        "entity_type",
        "issue_type",
        "ground_truth_label",
        "expected_result",
        "expected_corrective_action",
        "actual_detection_result",
        "severity",
        "description",
    ]

    for rec in all_records:
        for f in required_fields:
            assert f in rec, f"Missing field '{f}' in anomaly record: {rec}"
        assert rec["actual_detection_result"] == "DETECTED_ANOMALY"
        assert rec["scenario_id"] in ["SCENARIO-1", "SCENARIO-2", "SCENARIO-3", "SCENARIO-4", "SCENARIO-5"]


def test_individual_anomaly_scenarios(anomaly_engine):
    """Test each scenario detector independently."""
    # Scenario 1: Premature Payouts
    a1 = anomaly_engine.detect_premature_payouts()
    assert len(a1) == 25
    assert all(r["issue_type"] == "PREMATURE_PAYOUT" for r in a1)

    # Scenario 2: Double Commission
    a2 = anomaly_engine.detect_double_commissions()
    assert len(a2) == 25
    assert all(r["issue_type"] == "DOUBLE_COMMISSION" for r in a2)

    # Scenario 3: Suspended Seller Active
    a3 = anomaly_engine.detect_suspended_seller_activity()
    assert len(a3) == 20
    assert all(r["issue_type"] == "SUSPENDED_SELLER_ACTIVE" for r in a3)

    # Scenario 4: Unclawbacked Disputes
    a4 = anomaly_engine.detect_unclawbacked_disputes()
    assert len(a4) == 25
    assert all(r["issue_type"] == "UNCLAWBACKED_DISPUTE" for r in a4)

    # Scenario 5: Payout Total Mismatch
    a5 = anomaly_engine.detect_payout_total_mismatches()
    assert len(a5) == 20
    assert all(r["issue_type"] == "PAYOUT_TOTAL_MISMATCH" for r in a5)


def test_baseline_has_zero_anomalies(baseline_engine):
    """Verify that a clean baseline dataset yields 0 detected anomalies and 0 false positives."""
    report = baseline_engine.run_all_detectors()
    summary = report["summary"]
    assert summary["total_anomalies_detected"] == 0
    assert summary["false_positives"] == 0
    assert summary["precision"] == 1.0
    assert summary["recall"] == 1.0
