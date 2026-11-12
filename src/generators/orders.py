"""Deterministic Order & OrderLine Generator Supporting Multi-Seller Baskets."""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple


PAYMENT_METHODS = ["CREDIT_CARD", "PAYPAL", "APPLE_PAY", "DEBIT_CARD", "BNPL_AFFIRM"]


def generate_orders(
    order_count: int,
    customers: List[Dict[str, Any]],
    sellers: List[Dict[str, Any]],
    listings: List[Dict[str, Any]],
    seed: int = 20261022,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generate orders and itemized order lines.
    Supports multi-seller orders where an order groups lines from different merchants.
    Financial totals are derived directly from order lines.
    Returns (orders, order_lines).
    """
    rng = random.Random(seed)
    orders = []
    order_lines = []

    listing_lookup = {item["listing_id"]: item for item in listings}
    listing_ids = list(listing_lookup.keys())
    customer_ids = [c["customer_id"] for c in customers]

    start_date = datetime(2025, 1, 1, 0, 0, 0)
    end_date = datetime(2026, 11, 1, 0, 0, 0)
    total_seconds = int((end_date - start_date).total_seconds())

    for i in range(1, order_count + 1):
        order_id = f"ORD-2026-{i:06d}"
        cust_id = rng.choice(customer_ids)

        order_seconds = rng.randint(0, total_seconds)
        order_date = start_date + timedelta(seconds=order_seconds)
        order_date_str = order_date.strftime("%Y-%m-%d %H:%M:%S")

        # Determine line count: 80% 1 item, 15% 2 items, 5% 3 items
        roll_lines = rng.random()
        if roll_lines < 0.80:
            num_lines = 1
        elif roll_lines < 0.95:
            num_lines = 2
        else:
            num_lines = 3

        # Base status by recency
        days_from_end = (end_date - order_date).days
        if days_from_end < 3:
            sroll = rng.random()
            default_line_status = "PLACED" if sroll < 0.40 else ("CONFIRMED" if sroll < 0.75 else "SHIPPED")
        elif days_from_end < 7:
            default_line_status = "SHIPPED" if rng.random() < 0.60 else "DELIVERED"
        else:
            lroll = rng.random()
            if lroll < 0.85:
                default_line_status = "DELIVERED"
            elif lroll < 0.89:
                default_line_status = "RETURNED"
            elif lroll < 0.93:
                default_line_status = "CANCELLED"
            elif lroll < 0.97:
                default_line_status = "SHIPPED"
            else:
                default_line_status = "CONFIRMED"

        order_gross_cents = 0
        line_statuses = []

        for line_idx in range(1, num_lines + 1):
            line_id = f"ORDLN-2026-{i:06d}-{line_idx:02d}"
            chosen_lst_id = rng.choice(listing_ids)
            listing = listing_lookup[chosen_lst_id]
            seller_id = listing["seller_id"]

            qty = 1 if rng.random() < 0.85 else rng.randint(2, 4)
            unit_price_cents = listing["price_cents"]
            line_gross_cents = qty * unit_price_cents
            order_gross_cents += line_gross_cents

            line_status = default_line_status
            line_statuses.append(line_status)

            order_lines.append({
                "order_line_id": line_id,
                "order_id": order_id,
                "seller_id": seller_id,
                "listing_id": chosen_lst_id,
                "line_number": line_idx,
                "quantity": qty,
                "unit_price_cents": unit_price_cents,
                "gross_amount_cents": line_gross_cents,
                "line_status": line_status,
                "created_at": order_date_str,
            })

        # Derive order-level status
        if all(s == "DELIVERED" for s in line_statuses):
            derived_order_status = "DELIVERED"
        elif all(s == "CANCELLED" for s in line_statuses):
            derived_order_status = "CANCELLED"
        elif any(s == "SHIPPED" for s in line_statuses) and any(s in ("DELIVERED", "CONFIRMED") for s in line_statuses):
            derived_order_status = "PARTIALLY_SHIPPED"
        elif all(s in ("SHIPPED", "DELIVERED") for s in line_statuses):
            derived_order_status = "SHIPPED"
        elif all(s == "CONFIRMED" for s in line_statuses):
            derived_order_status = "CONFIRMED"
        elif all(s == "RETURNED" for s in line_statuses):
            derived_order_status = "RETURNED"
        else:
            derived_order_status = line_statuses[0]

        orders.append({
            "order_id": order_id,
            "customer_id": cust_id,
            "order_date": order_date_str,
            "total_amount_cents": order_gross_cents,
            "currency": "INR",
            "payment_method": rng.choice(PAYMENT_METHODS),
            "order_status": derived_order_status,
            "created_at": order_date_str,
            "updated_at": order_date_str,
        })

    return orders, order_lines
