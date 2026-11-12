"""Deterministic Customer Review Generator for Delivered OrderLines."""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any

POSITIVE_COMMENTS = [
    "Item arrived faster than expected and in pristine condition!",
    "Exceptional build quality. Exactly as described by the seller.",
    "Very satisfied with this purchase, would definitely buy again.",
    "Seamless shopping experience, packaged securely.",
    "High quality product, works flawlessly right out of the box."
]

NEUTRAL_COMMENTS = [
    "Decent product for the price. Packaging had minor dents.",
    "Works fine, shipping took a couple days longer than estimated.",
    "Average quality, does the job as expected."
]

NEGATIVE_COMMENTS = [
    "Arrived very late, missed my event deadline. Unacceptable.",
    "Packaging was damaged upon arrival. Expected much better handling.",
    "Product does not match the description. Disappointed.",
    "Poor seller communication regarding dispatch delays."
]


def generate_reviews(
    order_lines: List[Dict[str, Any]],
    orders: List[Dict[str, Any]],
    fulfillments: List[Dict[str, Any]],
    seed: int = 20261022,
) -> List[Dict[str, Any]]:
    """
    Generate customer reviews exclusively for delivered order lines.
    Correlates review ratings with carrier fulfillment SLA performance.
    """
    rng = random.Random(seed)
    reviews = []

    # Map fulfillment SLA by order_line_id
    flf_map = {f["order_line_id"]: f for f in fulfillments}
    order_map = {o["order_id"]: o for o in orders}

    delivered_lines = [l for l in order_lines if l["line_status"] in ("DELIVERED", "RETURNED")]

    rev_idx = 1
    for line in delivered_lines:
        # Sample ~35% of delivered lines to leave a review
        if rng.random() > 0.35:
            continue

        flf = flf_map.get(line["order_line_id"])
        order = order_map[line["order_id"]]
        is_late = flf and flf.get("sla_status") == "LATE"

        if is_late:
            roll = rng.random()
            if roll < 0.45:
                rating = 1
                comment = rng.choice(NEGATIVE_COMMENTS)
            elif roll < 0.75:
                rating = 2
                comment = rng.choice(NEGATIVE_COMMENTS)
            elif roll < 0.90:
                rating = 3
                comment = rng.choice(NEUTRAL_COMMENTS)
            else:
                rating = 4
                comment = rng.choice(POSITIVE_COMMENTS)
        else:
            roll = rng.random()
            if roll < 0.70:
                rating = 5
                comment = rng.choice(POSITIVE_COMMENTS)
            elif roll < 0.90:
                rating = 4
                comment = rng.choice(POSITIVE_COMMENTS)
            elif roll < 0.96:
                rating = 3
                comment = rng.choice(NEUTRAL_COMMENTS)
            else:
                rating = rng.choice([1, 2])
                comment = rng.choice(NEGATIVE_COMMENTS)

        deliv_str = flf.get("delivered_at") if flf and flf.get("delivered_at") else order["order_date"]
        deliv_dt = datetime.strptime(deliv_str, "%Y-%m-%d %H:%M:%S")
        review_dt = deliv_dt + timedelta(days=rng.randint(1, 10), hours=rng.randint(0, 23))

        reviews.append({
            "review_id": f"REV-2026-{rev_idx:06d}",
            "order_line_id": line["order_line_id"],
            "order_id": line["order_id"],
            "seller_id": line["seller_id"],
            "customer_id": order["customer_id"],
            "rating": rating,
            "comment": comment,
            "created_at": review_dt.strftime("%Y-%m-%d %H:%M:%S"),
        })
        rev_idx += 1

    return reviews
