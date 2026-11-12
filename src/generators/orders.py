"""Deterministic Order Generator."""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any


PAYMENT_METHODS = ["CREDIT_CARD", "PAYPAL", "APPLE_PAY", "DEBIT_CARD", "BNPL_AFFIRM"]


def generate_orders(
    count: int,
    customers: List[Dict[str, Any]],
    sellers: List[Dict[str, Any]],
    listings: List[Dict[str, Any]],
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """
    Generate orders mapped to customers, sellers, and active listings.
    """
    rng = random.Random(seed)
    orders = []

    # Map listings by listing_id for rapid price and seller lookup
    listing_lookup = {item["listing_id"]: item for item in listings}
    listing_ids = list(listing_lookup.keys())
    customer_ids = [c["customer_id"] for c in customers]

    start_date = datetime(2025, 1, 1, 0, 0, 0)
    end_date = datetime(2026, 11, 1, 0, 0, 0)
    total_seconds = int((end_date - start_date).total_seconds())

    for i in range(1, count + 1):
        order_id = f"ORD-{i:06d}"
        cust_id = rng.choice(customer_ids)
        lst_id = rng.choice(listing_ids)
        listing = listing_lookup[lst_id]
        seller_id = listing["seller_id"]

        qty = 1 if rng.random() < 0.85 else rng.randint(2, 4)
        unit_price = round(listing["price"], 2)
        gross_amount = round(qty * unit_price, 2)

        order_seconds = rng.randint(0, total_seconds)
        order_date = start_date + timedelta(seconds=order_seconds)

        # Status distribution:
        # Deliberate status based on recency: very recent orders might be PLACED/CONFIRMED/SHIPPED
        days_from_end = (end_date - order_date).days
        if days_from_end < 3:
            status_roll = rng.random()
            if status_roll < 0.40:
                status = "PLACED"
            elif status_roll < 0.75:
                status = "CONFIRMED"
            else:
                status = "SHIPPED"
        elif days_from_end < 7:
            status = "SHIPPED" if rng.random() < 0.60 else "DELIVERED"
        else:
            roll = rng.random()
            if roll < 0.86:
                status = "DELIVERED"
            elif roll < 0.90:
                status = "RETURNED"
            elif roll < 0.94:
                status = "CANCELLED"
            elif roll < 0.98:
                status = "SHIPPED"
            else:
                status = "CONFIRMED"

        orders.append({
            "order_id": order_id,
            "customer_id": cust_id,
            "seller_id": seller_id,
            "listing_id": lst_id,
            "order_date": order_date.strftime("%Y-%m-%d %H:%M:%S"),
            "quantity": qty,
            "unit_price": unit_price,
            "gross_amount": gross_amount,
            "currency": "USD",
            "payment_method": rng.choice(PAYMENT_METHODS),
            "order_status": status,
        })

    return orders
