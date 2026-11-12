"""Deterministic Fulfillment & Milestone Event Generator Supporting Split Shipments."""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from src.services.fulfillment_engine import FulfillmentEngine

CARRIERS = ["FedEx Express", "UPS Ground", "USPS Priority", "DHL eCommerce"]


def generate_fulfillments(
    order_lines: List[Dict[str, Any]],
    orders: List[Dict[str, Any]],
    fulfillment_engine: FulfillmentEngine,
    seed: int = 20261022,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generate fulfillments and immutable tracking events.
    Supports split/partial fulfillment when line quantity > 1.
    Evaluates 48-hour dispatch SLA.
    Returns (fulfillments, fulfillment_events).
    """
    rng = random.Random(seed)
    fulfillments = []
    fulfillment_events = []

    order_map = {o["order_id"]: o for o in orders}
    event_idx = 1

    for line in order_lines:
        line_id = line["order_line_id"]
        order = order_map[line["order_id"]]
        order_dt = datetime.strptime(order["order_date"], "%Y-%m-%d %H:%M:%S")
        status = line["line_status"]
        qty = line["quantity"]

        # Determine if split fulfillment occurs (only if qty >= 2 and line is fulfilled)
        should_split = (qty >= 2 and status in ("DELIVERED", "SHIPPED") and rng.random() < 0.08)

        if should_split:
            splits = [(f"{line_id}-01", qty // 2), (f"{line_id}-02", qty - (qty // 2))]
        else:
            splits = [(line_id, qty)]

        for split_suffix, split_qty in splits:
            flf_id = f"FUL-{split_suffix}"
            carrier = rng.choice(CARRIERS)
            prefix = carrier.split()[0].upper()
            tracking = f"{prefix}-{rng.randint(10000000, 99999999)}"

            if status == "CANCELLED":
                fulfillments.append({
                    "fulfillment_id": flf_id,
                    "order_line_id": line_id,
                    "order_id": line["order_id"],
                    "seller_id": line["seller_id"],
                    "carrier": carrier,
                    "tracking_number": tracking,
                    "quantity_fulfilled": split_qty,
                    "dispatched_at": None,
                    "expected_delivery_at": None,
                    "delivered_at": None,
                    "sla_status": "CANCELLED",
                    "transit_days": None,
                    "created_at": order["order_date"],
                })
                continue

            if status in ("PLACED", "CONFIRMED"):
                fulfillments.append({
                    "fulfillment_id": flf_id,
                    "order_line_id": line_id,
                    "order_id": line["order_id"],
                    "seller_id": line["seller_id"],
                    "carrier": carrier,
                    "tracking_number": tracking,
                    "quantity_fulfilled": split_qty,
                    "dispatched_at": None,
                    "expected_delivery_at": (order_dt + timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
                    "delivered_at": None,
                    "sla_status": "IN_TRANSIT",
                    "transit_days": None,
                    "created_at": order["order_date"],
                })
                continue

            # Shipped or Delivered
            is_late_dispatch = rng.random() < 0.05
            dispatch_hours = rng.randint(52, 110) if is_late_dispatch else rng.randint(8, 44)
            dispatched_dt = order_dt + timedelta(hours=dispatch_hours)
            expected_deliv_dt = dispatched_dt + timedelta(days=rng.randint(3, 5))

            if status in ("DELIVERED", "RETURNED"):
                transit_days = rng.randint(2, 5)
                delivered_dt = dispatched_dt + timedelta(days=transit_days, hours=rng.randint(2, 10))
                eval_res = fulfillment_engine.evaluate_sla(order_dt, dispatched_dt, delivered_dt)

                fulfillments.append({
                    "fulfillment_id": flf_id,
                    "order_line_id": line_id,
                    "order_id": line["order_id"],
                    "seller_id": line["seller_id"],
                    "carrier": carrier,
                    "tracking_number": tracking,
                    "quantity_fulfilled": split_qty,
                    "dispatched_at": dispatched_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "expected_delivery_at": expected_deliv_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "delivered_at": delivered_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "sla_status": eval_res["sla_status"],
                    "transit_days": transit_days,
                    "created_at": order["order_date"],
                })

                # Lifecycle Events: LABEL_CREATED -> PICKED_UP -> IN_TRANSIT -> DELIVERED
                fulfillment_events.append({
                    "event_id": f"FLE-{event_idx:06d}",
                    "fulfillment_id": flf_id,
                    "event_type": "LABEL_CREATED",
                    "event_timestamp": (dispatched_dt - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
                    "location": "Warehouse Origin Facility",
                    "notes": "Shipping manifest & electronic label created",
                    "created_at": (dispatched_dt - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
                })
                event_idx += 1

                fulfillment_events.append({
                    "event_id": f"FLE-{event_idx:06d}",
                    "fulfillment_id": flf_id,
                    "event_type": "PICKED_UP",
                    "event_timestamp": dispatched_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "location": f"{carrier} Sorting Center",
                    "notes": "Package scanned and accepted into sorting hub",
                    "created_at": dispatched_dt.strftime("%Y-%m-%d %H:%M:%S"),
                })
                event_idx += 1

                fulfillment_events.append({
                    "event_id": f"FLE-{event_idx:06d}",
                    "fulfillment_id": flf_id,
                    "event_type": "DELIVERED",
                    "event_timestamp": delivered_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "location": "Destination Customer Address",
                    "notes": "Delivered and signature verified",
                    "created_at": delivered_dt.strftime("%Y-%m-%d %H:%M:%S"),
                })
                event_idx += 1

            else:
                # In Transit
                eval_res = fulfillment_engine.evaluate_sla(order_dt, dispatched_dt, None)
                fulfillments.append({
                    "fulfillment_id": flf_id,
                    "order_line_id": line_id,
                    "order_id": line["order_id"],
                    "seller_id": line["seller_id"],
                    "carrier": carrier,
                    "tracking_number": tracking,
                    "quantity_fulfilled": split_qty,
                    "dispatched_at": dispatched_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "expected_delivery_at": expected_deliv_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "delivered_at": None,
                    "sla_status": eval_res["sla_status"],
                    "transit_days": None,
                    "created_at": order["order_date"],
                })

                fulfillment_events.append({
                    "event_id": f"FLE-{event_idx:06d}",
                    "fulfillment_id": flf_id,
                    "event_type": "IN_TRANSIT",
                    "event_timestamp": dispatched_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "location": f"{carrier} Transit Hub",
                    "notes": "In transit to delivery distribution center",
                    "created_at": dispatched_dt.strftime("%Y-%m-%d %H:%M:%S"),
                })
                event_idx += 1

    return fulfillments, fulfillment_events
