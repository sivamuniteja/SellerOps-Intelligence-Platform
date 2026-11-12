"""Test suite for operational exceptions and anomaly detection."""

import pytest
from src.database.connection import get_db
from src.validation.anomaly_detection import AnomalyDetectionEngine


@pytest.fixture(scope="module")
def anomaly_engine():
    db = get_db("data/sellerops.db")
    return AnomalyDetectionEngine(db)


def test_detect_all_anomalies(anomaly_engine):
    report = anomaly_engine.run_all_detectors()
    summary = report["summary"]

    assert summary["anomaly_1_count"] == 25, "Anomaly 1 (Premature Payout) count mismatch"
    assert summary["anomaly_2_count"] == 25, "Anomaly 2 (Double Commission) count mismatch"
    assert summary["anomaly_3_count"] == 20, "Anomaly 3 (Suspended Seller Active) count mismatch"
    assert summary["anomaly_4_count"] == 25, "Anomaly 4 (Unclawbacked Dispute) count mismatch"
    assert summary["anomaly_5_count"] == 20, "Anomaly 5 (Payout Total Mismatch) count mismatch"

    assert summary["precision"] >= 0.99, f"Precision was {summary['precision']}"
    assert summary["recall"] >= 0.99, f"Recall was {summary['recall']}"
    assert summary["f1_score"] >= 0.99, f"F1 score was {summary['f1_score']}"
