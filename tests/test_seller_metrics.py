"""Test suite for Seller Metrics and Performance Engine (Engine E)."""

import sqlite3
import pytest
from src.config import load_config
from src.services.seller_metrics import (
    SellerMetricsEngine,
    SellerNotFoundError,
)


@pytest.fixture(scope="module")
def metrics_engine():
    config = load_config()
    return SellerMetricsEngine(config)


@pytest.fixture(scope="module")
def db_conn():
    conn = sqlite3.connect("data/sellerops.db")
    yield conn
    conn.close()


def test_scorecard_calculation(metrics_engine):
    """Test standard scorecard calculations from aggregated metrics."""
    res = metrics_engine.compute_seller_scorecard(
        total_orders=100,
        late_shipments=2,
        cancelled_orders=1,
        disputed_orders=0,
        avg_rating=4.8,
        gmv=25000.0,
    )
    assert res["total_orders"] == 100
    assert res["late_shipment_rate"] == 0.02
    assert res["cancellation_rate"] == 0.01
    assert res["order_defect_rate"] == 0.0
    assert res["compliance_status"] == "COMPLIANT"
    assert res["recommended_tier"] == "PREFERRED"


def test_scorecard_breach_detection(metrics_engine):
    """Exceeding SLA thresholds triggers probation warning or suspension."""
    # High late shipment rate: 10 / 100 = 10% (threshold: 4%)
    res_late = metrics_engine.compute_seller_scorecard(
        total_orders=100,
        late_shipments=10,
        cancelled_orders=1,
        disputed_orders=0,
        avg_rating=4.5,
        gmv=5000.0,
    )
    assert res_late["compliance_status"] == "PROBATION_WARNING"
    assert res_late["recommended_tier"] == "PROBATION"

    # Extreme defect rate (> 5%) triggers CRITICAL_ACTION_REQUIRED
    res_critical = metrics_engine.compute_seller_scorecard(
        total_orders=100,
        late_shipments=2,
        cancelled_orders=1,
        disputed_orders=8,  # 8% ODR
        avg_rating=3.0,
        gmv=5000.0,
    )
    assert res_critical["compliance_status"] == "CRITICAL_ACTION_REQUIRED"
    assert res_critical["recommended_tier"] == "SUSPENDED"


def test_calculate_metrics_from_actual_db(metrics_engine, db_conn):
    """Calculate complete metric suite for a real seller in data/sellerops.db."""
    metrics = metrics_engine.calculate_seller_metrics("SELL-000001", db_conn)

    assert metrics["seller_id"] == "SELL-000001"
    assert metrics["total_orders"] > 0
    assert metrics["total_order_lines"] >= metrics["total_orders"]
    assert metrics["gmv_cents"] > 0
    assert metrics["gmv"] == round(metrics["gmv_cents"] / 100.0, 2)
    assert 0.0 <= metrics["fulfillment_rate"] <= 1.0
    assert 0.0 <= metrics["late_shipment_rate"] <= 1.0
    assert 0.0 <= metrics["on_time_delivery_rate"] <= 1.0
    assert 0.0 <= metrics["dispute_rate"] <= 1.0
    assert 0.0 <= metrics["cancellation_rate"] <= 1.0
    assert 1.0 <= metrics["avg_rating"] <= 5.0
    assert 0.0 <= metrics["risk_score"] <= 100.0

    # Denominators documentation must be explicitly present
    denoms = metrics["denominators"]
    assert "fulfillment_rate" in denoms
    assert "late_shipment_rate" in denoms
    assert "on_time_delivery_rate" in denoms
    assert "dispute_rate" in denoms
    assert "cancellation_rate" in denoms


def test_time_window_filtering(metrics_engine, db_conn):
    """Test 30-day time window filtering against all-time metrics."""
    all_time = metrics_engine.calculate_seller_metrics("SELL-000001", db_conn)
    window_30 = metrics_engine.calculate_seller_metrics(
        "SELL-000001", db_conn, as_of_date="2026-11-10 00:00:00", window_days=30
    )

    assert window_30["time_window"] == "30 Days"
    assert window_30["total_orders"] <= all_time["total_orders"]
    assert window_30["gmv_cents"] <= all_time["gmv_cents"]


def test_seller_not_found_raises_error(metrics_engine, db_conn):
    """Non-existent seller ID must raise SellerNotFoundError."""
    with pytest.raises(SellerNotFoundError):
        metrics_engine.calculate_seller_metrics("SELL-NONEXISTENT", db_conn)
