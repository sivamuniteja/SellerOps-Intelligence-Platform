"""Deterministic Customer Review Generator."""

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
    orders: List[Dict[str, Any]],
    fulfillments: List[Dict[str, Any]],
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """
    Generate customer reviews for delivered orders, correlated with fulfillment SLA.
    """
    rng = random.Random(seed)
    reviews = []

    # Map fulfillment SLA by order_id
    flf_map = {f["order_id"]: f for f in fulfillments}

    delivered_orders = [o for o in orders if o["order_status"] in ("DELIVERED", "RETURNED")]

    rev_idx = 1
    for order in delivered_orders:
        # Sample ~40% of delivered orders to leave a review
        if rng.random() > 0.40:
            continue

        flf = flf_map.get(order["order_id"])
        is_late = flf and flf.get("sla_status") == "LATE"

        if is_late:
            # Skewed low rating
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
            # Skewed high rating
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

        delivered_at_str = flf.get("delivered_at") if flf else order["order_date"]
        deliv_dt = datetime.strptime(delivered_at_str, "%Y-%m-%d %H:%M:%S") if delivered_at_str else datetime.strptime(order["order_date"], "%Y-%m-%d %H:%M:%S")
        review_dt = deliv_dt + timedelta(days=rng.randint(1, 10), hours=rng.randint(0, 23))

        reviews.append({
            "review_id": f"REV-{rev_idx:06d}",
            "order_id": order["order_id"],
            "rating": rating,
            "comment": comment,
            "created_at": review_dt.strftime("%Y-%m-%d %H:%M:%S"),
        })
        rev_idx += 1

    return reviews
