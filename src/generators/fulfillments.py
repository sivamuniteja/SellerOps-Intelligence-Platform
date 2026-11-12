"""Deterministic Fulfillment and Carrier Tracking Generator."""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
from src.services.fulfillment_engine import FulfillmentEngine


CARRIERS = ["FedEx Express", "UPS Ground", "USPS Priority", "DHL eCommerce"]


def generate_fulfillments(
    orders: List[Dict[str, Any]],
    fulfillment_engine: FulfillmentEngine,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """
    Generate fulfillment lifecycles for orders.
    Enforces chronological consistency: order_date <= dispatched_at <= delivered_at.
    """
    rng = random.Random(seed)
    fulfillments = []

    for idx, order in enumerate(orders):
        flf_id = f"FLF-{idx+1:06d}"
        order_id = order["order_id"]
        status = order["order_status"]
        order_dt = datetime.strptime(order["order_date"], "%Y-%m-%d %H:%M:%S")

        carrier = rng.choice(CARRIERS)
        prefix = carrier.split()[0].upper()
        tracking = f"{prefix}-{rng.randint(10000000, 99999999)}"

        if status == "CANCELLED":
            # Cancelled order
            res = fulfillment_engine.evaluate_sla(order_dt, None, None, is_cancelled=True)
            fulfillments.append({
                "fulfillment_id": flf_id,
                "order_id": order_id,
                "carrier": carrier,
                "tracking_number": tracking,
                "dispatched_at": None,
                "expected_delivery_at": None,
                "delivered_at": None,
                "sla_status": "CANCELLED",
                "transit_days": None,
            })
            continue

        if status == "PLACED":
            # Still awaiting fulfillment
            fulfillments.append({
                "fulfillment_id": flf_id,
                "order_id": order_id,
                "carrier": carrier,
                "tracking_number": tracking,
                "dispatched_at": None,
                "expected_delivery_at": (order_dt + timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
                "delivered_at": None,
                "sla_status": "IN_TRANSIT",
                "transit_days": None,
            })
            continue

        # Dispatched scenario
        # 95% on-time dispatch (8 to 44 hours), 5% late dispatch (50 to 96 hours)
        is_late_dispatch = rng.random() < 0.05
        if is_late_dispatch:
            dispatch_hours = rng.randint(50, 110)
        else:
            dispatch_hours = rng.randint(8, 44)

        dispatched_dt = order_dt + timedelta(hours=dispatch_hours)
        expected_delivery_dt = dispatched_dt + timedelta(days=rng.randint(3, 5))

        if status in ("DELIVERED", "RETURNED"):
            transit_days = rng.randint(2, 5)
            delivered_dt = dispatched_dt + timedelta(days=transit_days, hours=rng.randint(2, 10))
            eval_res = fulfillment_engine.evaluate_sla(order_dt, dispatched_dt, delivered_dt)

            fulfillments.append({
                "fulfillment_id": flf_id,
                "order_id": order_id,
                "carrier": carrier,
                "tracking_number": tracking,
                "dispatched_at": dispatched_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "expected_delivery_at": expected_delivery_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "delivered_at": delivered_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "sla_status": eval_res["sla_status"],
                "transit_days": transit_days,
            })
        else:
            # SHIPPED or CONFIRMED in transit
            eval_res = fulfillment_engine.evaluate_sla(order_dt, dispatched_dt, None)
            fulfillments.append({
                "fulfillment_id": flf_id,
                "order_id": order_id,
                "carrier": carrier,
                "tracking_number": tracking,
                "dispatched_at": dispatched_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "expected_delivery_at": expected_delivery_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "delivered_at": None,
                "sla_status": eval_res["sla_status"],
                "transit_days": None,
            })

    return fulfillments
