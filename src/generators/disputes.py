"""Deterministic Dispute and Chargeback Generator with Anomaly 4 Injection."""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple


DISPUTE_REASONS = [
    "ITEM_NOT_RECEIVED",
    "SIGNIFICANTLY_NOT_AS_DESCRIBED",
    "UNAUTHORIZED_TRANSACTION",
    "DAMAGED_IN_TRANSIT",
    "DUPLICATE_CHARGE"
]


def generate_disputes(
    count: int,
    orders: List[Dict[str, Any]],
    seed: int = 42,
    anomaly_count: int = 25,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generate disputes linked to orders.
    Injects Anomaly 4: Resolved dispute without clawback applied.
    Returns (disputes, ground_truth_anomalies).
    """
    rng = random.Random(seed)
    disputes = []
    ground_truth = []

    # Pick candidate orders (prefer delivered, late, or returned orders)
    candidate_orders = [o for o in orders if o["order_status"] in ("DELIVERED", "RETURNED", "SHIPPED")]
    if len(candidate_orders) < count:
        candidate_orders = orders

    sampled_orders = rng.sample(candidate_orders, min(count, len(candidate_orders)))
    injected_count = 0

    for idx, order in enumerate(sampled_orders):
        disp_id = f"DSP-{idx+1:06d}"
        order_id = order["order_id"]
        seller_id = order["seller_id"]
        cust_id = order["customer_id"]
        gross = order["gross_amount"]

        order_dt = datetime.strptime(order["order_date"], "%Y-%m-%d %H:%M:%S")
        dispute_dt = order_dt + timedelta(days=rng.randint(3, 30), hours=rng.randint(1, 12))

        # Status distribution
        roll = rng.random()
        if roll < 0.45:
            status = "RESOLVED_BUYER_FAVOR"
            resolved_dt = dispute_dt + timedelta(days=rng.randint(2, 7))
            clawback = 1
        elif roll < 0.75:
            status = "RESOLVED_SELLER_FAVOR"
            resolved_dt = dispute_dt + timedelta(days=rng.randint(3, 10))
            clawback = 0
        elif roll < 0.90:
            status = "UNDER_REVIEW"
            resolved_dt = None
            clawback = 0
        elif roll < 0.95:
            status = "OPEN"
            resolved_dt = None
            clawback = 0
        else:
            status = "CHARGEBACK_LOST"
            resolved_dt = dispute_dt + timedelta(days=rng.randint(5, 14))
            clawback = 1

        # Check for Anomaly 4 injection
        if status in ("RESOLVED_BUYER_FAVOR", "CHARGEBACK_LOST") and injected_count < anomaly_count:
            clawback = 0  # Bug: dispute won by buyer was never clawed back!
            injected_count += 1
            ground_truth.append({
                "anomaly_id": f"ANO-4-{injected_count:04d}",
                "anomaly_type": "UNCLAWBACKED_DISPUTE",
                "entity_type": "DISPUTE",
                "entity_id": disp_id,
                "description": f"Dispute {disp_id} with status {status} was never deducted/clawed back from seller",
                "severity": "HIGH",
                "detected": 0,
                "created_at": dispute_dt.strftime("%Y-%m-%d %H:%M:%S"),
            })

        disputes.append({
            "dispute_id": disp_id,
            "order_id": order_id,
            "seller_id": seller_id,
            "customer_id": cust_id,
            "dispute_date": dispute_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "dispute_reason": rng.choice(DISPUTE_REASONS),
            "disputed_amount": gross,
            "status": status,
            "resolution_date": resolved_dt.strftime("%Y-%m-%d %H:%M:%S") if resolved_dt else None,
            "clawback_applied": clawback,
        })

    return disputes, ground_truth
