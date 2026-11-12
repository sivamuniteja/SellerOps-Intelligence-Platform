"""Deterministic Dispute & Adjudication Event Generator with Anomaly 4 Injection."""

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
    order_lines: List[Dict[str, Any]],
    orders: List[Dict[str, Any]],
    seed: int = 20261022,
    anomaly_count: int = 25,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generate customer disputes linked to order lines with immutable dispute events.
    Injects Anomaly 4: Dispute resolved in buyer favor without clawback applied.
    Returns (disputes, dispute_events, ground_truth_anomalies).
    """
    rng = random.Random(seed)
    disputes = []
    dispute_events = []
    ground_truth = []

    order_map = {o["order_id"]: o for o in orders}

    # Candidate lines: prefer delivered, shipped, or returned
    candidate_lines = [l for l in order_lines if l["line_status"] in ("DELIVERED", "RETURNED", "SHIPPED")]
    if len(candidate_lines) < count:
        candidate_lines = order_lines

    sampled_lines = rng.sample(candidate_lines, min(count, len(candidate_lines)))
    injected_count = 0
    event_idx = 1

    for idx, line in enumerate(sampled_lines):
        disp_id = f"DSP-2026-{idx+1:06d}"
        order = order_map[line["order_id"]]
        order_dt = datetime.strptime(order["order_date"], "%Y-%m-%d %H:%M:%S")

        dispute_dt = order_dt + timedelta(days=rng.randint(3, 25), hours=rng.randint(1, 12))
        dispute_dt_str = dispute_dt.strftime("%Y-%m-%d %H:%M:%S")

        gross_cents = line["gross_amount_cents"]
        reason = rng.choice(DISPUTE_REASONS)

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

        resolved_dt_str = resolved_dt.strftime("%Y-%m-%d %H:%M:%S") if resolved_dt else None

        # Anomaly 4: Unclawbacked Dispute
        if status in ("RESOLVED_BUYER_FAVOR", "CHARGEBACK_LOST") and injected_count < anomaly_count:
            clawback = 0  # Bug: clawback was never applied
            injected_count += 1
            ground_truth.append({
                "anomaly_id": f"ANO-4-{injected_count:04d}",
                "anomaly_type": "UNCLAWBACKED_DISPUTE",
                "entity_type": "DISPUTE",
                "entity_id": disp_id,
                "description": f"Dispute {disp_id} status {status} was never deducted from seller balance",
                "severity": "HIGH",
                "detected": 0,
                "created_at": dispute_dt_str,
            })

        disputes.append({
            "dispute_id": disp_id,
            "order_id": line["order_id"],
            "order_line_id": line["order_line_id"],
            "seller_id": line["seller_id"],
            "customer_id": order["customer_id"],
            "dispute_date": dispute_dt_str,
            "dispute_reason": reason,
            "disputed_amount_cents": gross_cents,
            "status": status,
            "resolution_date": resolved_dt_str,
            "clawback_applied": clawback,
            "created_at": dispute_dt_str,
        })

        # Event 1: Dispute Opening
        dispute_events.append({
            "event_id": f"DSE-{event_idx:06d}",
            "dispute_id": disp_id,
            "previous_status": None,
            "new_status": "OPEN",
            "actor": "BUYER",
            "notes": f"Buyer opened claim regarding {reason}",
            "created_at": dispute_dt_str,
        })
        event_idx += 1

        # Event 2: Adjudication Decision if resolved
        if status not in ("OPEN", "UNDER_REVIEW") and resolved_dt_str:
            dispute_events.append({
                "event_id": f"DSE-{event_idx:06d}",
                "dispute_id": disp_id,
                "previous_status": "UNDER_REVIEW",
                "new_status": status,
                "actor": "ARBITRATOR",
                "notes": f"Arbitration decision finalized: {status}",
                "created_at": resolved_dt_str,
            })
            event_idx += 1

    return disputes, dispute_events, ground_truth
