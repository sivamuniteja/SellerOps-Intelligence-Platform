"""Deterministic Product Listing Generator with Canonical ID & Integer Cents."""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from src.config import PlatformConfig

CATEGORY_TEMPLATES = {
    "Electronics": [
        ("Wireless Noise-Canceling Headphones 4K", 7999, 29999),
        ("Ultra-HD Smart Monitor 27-inch IPS", 19999, 44999),
        ("Mechanical Gaming Keyboard RGB Backlit", 4999, 13999),
        ("Fast Wireless Charging Dock 3-in-1", 2499, 5999),
        ("USB-C Multi-Port Aluminum Hub Adapter", 1999, 4999),
    ],
    "Fashion & Apparel": [
        ("Classic Premium Cotton Crewneck Tee", 1800, 3800),
        ("All-Weather Waterproof Trail Jacket", 6500, 16000),
        ("Slim-Fit Stretch Denim Jeans", 3500, 8500),
        ("Breathable Athletic Running Shoes", 4500, 12000),
        ("Polarized Classic Sunglasses UV400", 2200, 5500),
    ],
    "Home & Kitchen": [
        ("Stainless Steel Chef Knife 8-Inch", 2999, 8999),
        ("Programmable Digital Air Fryer 5.8Qt", 5999, 14999),
        ("Organic Bamboo Ergonomic Cutting Board", 1999, 4499),
        ("Cold Brew Iced Coffee Maker 1L", 2199, 3999),
        ("Memory Foam Ergonomic Contour Pillow", 2800, 6500),
    ],
    "Beauty & Personal Care": [
        ("Hydrating Vitamin C Facial Serum 50ml", 1650, 4200),
        ("Ionic Hair Dryer with Diffuser", 3999, 9999),
        ("Organic Botanical Body Wash 500ml", 1200, 2400),
        ("Charcoal Teeth Whitening Kit", 1800, 3500),
    ],
    "Sports & Outdoors": [
        ("Non-Slip High Density Yoga Mat 6mm", 2200, 5500),
        ("Insulated Stainless Water Bottle 32oz", 1699, 3499),
        ("Adjustable Quick-Select Dumbbell Set 50lbs", 12000, 28000),
        ("Ultralight Backpacking Tent 2-Person", 7500, 19500),
    ],
    "Books & Media": [
        ("Hardcover Collector Edition Best-Seller", 1899, 3500),
        ("Modern Software Architecture Handbook", 3999, 6499),
        ("World History Illustrated Almanac", 2499, 4500),
    ],
    "Automotive": [
        ("Digital Tire Pressure Gauge & Inflator", 2199, 4999),
        ("Ceramic Coating Car Wax Hydrophobic Spray", 1599, 3299),
        ("Magnetic Dashboard Phone Car Mount", 1299, 2499),
    ],
    "Health & Wellness": [
        ("Daily Multivitamin Herbal Supplement 90ct", 1499, 2999),
        ("Deep Tissue Percussion Massage Gun", 4999, 12999),
        ("Aromatherapy Essential Oil Ultrasonic Diffuser", 1999, 3999),
    ]
}


def generate_listings(
    count: int,
    sellers: List[Dict[str, Any]],
    config: PlatformConfig,
    seed: int = 20261022,
    anomaly_count: int = 20,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generate product listings adhering to LIST-{seller_id}-000001 pattern and integer cents.
    Injects Anomaly 3: Suspended sellers having ACTIVE listings.
    Returns (listings, ground_truth_anomalies).
    """
    rng = random.Random(seed)
    listings = []
    ground_truth = []
    base_date = datetime(2024, 2, 1, 0, 0, 0)

    active_sellers = [s for s in sellers if s["status"] != "SUSPENDED"]
    suspended_sellers = [s for s in sellers if s["status"] == "SUSPENDED"]

    categories = [cat.name for cat in config.categories]
    seller_item_seq: Dict[str, int] = {}
    injected_count = 0

    for i in range(1, count + 1):
        category = rng.choice(categories)
        templates = CATEGORY_TEMPLATES.get(category, CATEGORY_TEMPLATES["Electronics"])
        title_base, min_cents, max_cents = rng.choice(templates)
        title = f"{title_base} - Series {rng.randint(100, 999)}"
        price_cents = rng.randint(min_cents, max_cents)
        inv = rng.randint(10, 500)

        # Decide seller & status
        if suspended_sellers and injected_count < anomaly_count and rng.random() < 0.05:
            seller = rng.choice(suspended_sellers)
            seller_id = seller["seller_id"]
            seq = seller_item_seq.get(seller_id, 0) + 1
            seller_item_seq[seller_id] = seq
            listing_id = f"LIST-{seller_id}-{seq:06d}"

            # Anomaly 3: Suspended seller listing is ACTIVE
            status = "ACTIVE"
            injected_count += 1
            created_at = base_date + timedelta(days=rng.randint(0, 450), hours=rng.randint(0, 23))
            created_str = created_at.strftime("%Y-%m-%d %H:%M:%S")

            ground_truth.append({
                "anomaly_id": f"ANO-3-{injected_count:04d}",
                "anomaly_type": "SUSPENDED_SELLER_ACTIVE",
                "entity_type": "LISTING",
                "entity_id": listing_id,
                "description": f"Listing {listing_id} is ACTIVE under suspended seller {seller_id}",
                "severity": "CRITICAL",
                "detected": 0,
                "created_at": created_str,
            })
        else:
            seller = rng.choice(active_sellers) if active_sellers else rng.choice(sellers)
            seller_id = seller["seller_id"]
            seq = seller_item_seq.get(seller_id, 0) + 1
            seller_item_seq[seller_id] = seq
            listing_id = f"LIST-{seller_id}-{seq:06d}"

            if seller["status"] == "SUSPENDED":
                status = "SUSPENDED"
            else:
                status = "ACTIVE" if rng.random() > 0.08 else "OUT_OF_STOCK"

            created_at = base_date + timedelta(days=rng.randint(0, 450), hours=rng.randint(0, 23))
            created_str = created_at.strftime("%Y-%m-%d %H:%M:%S")

        listings.append({
            "listing_id": listing_id,
            "seller_id": seller_id,
            "title": title,
            "category": category,
            "price_cents": price_cents,
            "inventory_count": inv,
            "status": status,
            "created_at": created_str,
            "updated_at": created_str,
        })

    return listings, ground_truth
