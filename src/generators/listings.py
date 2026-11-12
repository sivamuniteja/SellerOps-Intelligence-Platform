"""Deterministic Product Listing Generator with Anomaly 3 Injection."""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from src.config import PlatformConfig


CATEGORY_TEMPLATES = {
    "Electronics": [
        ("Wireless Noise-Canceling Headphones", 79.99, 299.99),
        ("Ultra-HD 4K Smart Monitor 27-inch", 199.99, 449.99),
        ("Mechanical Gaming Keyboard RGB", 49.99, 139.99),
        ("Fast Wireless Charging Dock 3-in-1", 24.99, 59.99),
        ("USB-C Multi-Port Hub Adapter", 19.99, 49.99),
    ],
    "Fashion & Apparel": [
        ("Classic Premium Cotton Crewneck Tee", 18.00, 38.00),
        ("All-Weather Waterproof Trail Jacket", 65.00, 160.00),
        ("Slim-Fit Stretch Denim Jeans", 35.00, 85.00),
        ("Breathable Athletic Running Shoes", 45.00, 120.00),
        ("Polarized Classic Sunglasses UV400", 22.00, 55.00),
    ],
    "Home & Kitchen": [
        ("Stainless Steel Chef Knife 8-Inch", 29.99, 89.99),
        ("Programmable Digital Air Fryer 5.8Qt", 59.99, 149.99),
        ("Organic Bamboo Cutting Board Set", 19.99, 44.99),
        ("Cold Brew Iced Coffee Maker 1L", 21.99, 39.99),
        ("Memory Foam Ergonomic Pillow", 28.00, 65.00),
    ],
    "Beauty & Personal Care": [
        ("Hydrating Vitamin C Facial Serum", 16.50, 42.00),
        ("Ionic Hair Dryer with Diffuser", 39.99, 99.99),
        ("Organic Botanical Body Wash 500ml", 12.00, 24.00),
        ("Charcoal Teeth Whitening Kit", 18.00, 35.00),
    ],
    "Sports & Outdoors": [
        ("Non-Slip High Density Yoga Mat", 22.00, 55.00),
        ("Insulated Stainless Water Bottle 32oz", 16.99, 34.99),
        ("Adjustable Dumbbell Set 50lbs", 120.00, 280.00),
        ("Ultralight Backpacking Tent 2-Person", 75.00, 195.00),
    ],
    "Books & Media": [
        ("Hardcover Collector Edition Best-Seller", 18.99, 35.00),
        ("Modern Software Architecture Handbook", 39.99, 64.99),
        ("World History Illustrated Almanac", 24.99, 45.00),
    ],
    "Automotive": [
        ("Digital Tire Pressure Gauge & Inflator", 21.99, 49.99),
        ("Ceramic Coating Car Wax Spray", 15.99, 32.99),
        ("Magnetic Dashboard Phone Car Mount", 12.99, 24.99),
    ],
    "Health & Wellness": [
        ("Daily Multivitamin Herbal Supplement", 14.99, 29.99),
        ("Deep Tissue Percussion Massage Gun", 49.99, 129.99),
        ("Aromatherapy Essential Oil Diffuser", 19.99, 39.99),
    ]
}


def generate_listings(
    count: int,
    sellers: List[Dict[str, Any]],
    config: PlatformConfig,
    seed: int = 42,
    anomaly_count: int = 20,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generate product listings.
    Injects Anomaly 3: Suspended sellers having active listings.
    Returns (listings, ground_truth_anomalies).
    """
    rng = random.Random(seed)
    listings = []
    ground_truth = []
    base_date = datetime(2024, 2, 1, 0, 0, 0)

    # Separate active vs suspended sellers
    active_sellers = [s for s in sellers if s["status"] != "SUSPENDED"]
    suspended_sellers = [s for s in sellers if s["status"] == "SUSPENDED"]

    categories = [cat.name for cat in config.categories]

    # Pre-select listings to be injected with Anomaly 3
    injected_count = 0

    for i in range(1, count + 1):
        listing_id = f"LST-{i:06d}"
        category = rng.choice(categories)
        templates = CATEGORY_TEMPLATES.get(category, CATEGORY_TEMPLATES["Electronics"])
        title_base, min_p, max_p = rng.choice(templates)
        title = f"{title_base} - Model {rng.randint(100, 999)}"
        price = round(rng.uniform(min_p, max_p), 2)
        inv = rng.randint(5, 500)

        # Decide seller
        if suspended_sellers and injected_count < anomaly_count and rng.random() < 0.05:
            # Inject Anomaly 3: Suspended seller listing active inventory
            seller = rng.choice(suspended_sellers)
            status = "ACTIVE"
            injected_count += 1
            ground_truth.append({
                "anomaly_id": f"ANO-3-{injected_count:04d}",
                "anomaly_type": "SUSPENDED_SELLER_ACTIVE",
                "entity_type": "LISTING",
                "entity_id": listing_id,
                "description": f"Listing {listing_id} is ACTIVE under suspended seller {seller['seller_id']}",
                "severity": "CRITICAL",
                "detected": 0,
                "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
            })
        else:
            seller = rng.choice(active_sellers) if active_sellers else rng.choice(sellers)
            status = "ACTIVE" if rng.random() > 0.08 else "OUT_OF_STOCK"

        created_at = base_date + timedelta(days=rng.randint(0, 500), hours=rng.randint(0, 23))

        listings.append({
            "listing_id": listing_id,
            "seller_id": seller["seller_id"],
            "title": title,
            "category": category,
            "price": price,
            "inventory_count": inv,
            "status": status,
            "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
        })

    return listings, ground_truth
