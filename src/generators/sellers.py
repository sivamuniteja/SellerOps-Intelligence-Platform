"""Deterministic Seller Generator for SellerOps Intelligence Platform."""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
from src.config import PlatformConfig


FIRST_NAMES = [
    "Apex", "Prime", "Summit", "Nexus", "Beacon", "Vanguard", "Horizon", "Pinnacle",
    "Atlas", "Sterling", "Quantum", "Zenith", "Crestview", "TrueNorth", "Starlight",
    "Silverline", "Ironclad", "BlueWave", "GoldenGate", "Echo", "Timber", "Breeze"
]

LAST_NAMES = [
    "Retail", "Direct", "Logistics", "Enterprises", "Trading", "Supplies", "Goods",
    "Market", "Outlet", "Brands", "Wholesale", "Global", "Solutions", "Depot", "Hub"
]

CITIES = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "Dallas", "Austin"]
STATES = ["NY", "CA", "IL", "TX", "AZ", "PA", "TX", "TX"]


def generate_sellers(count: int, config: PlatformConfig, seed: int = 42) -> List[Dict[str, Any]]:
    """
    Generate deterministic seller records.
    Tiers: ENTERPRISE (10%), PREFERRED (25%), STANDARD (58%), PROBATION (4%), SUSPENDED (3%).
    """
    rng = random.Random(seed)
    sellers = []
    base_date = datetime(2024, 1, 1, 0, 0, 0)

    for i in range(1, count + 1):
        seller_id = f"SLR-{i:05d}"
        company_name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)} {rng.randint(10, 99)}"

        roll = rng.random()
        if roll < 0.10:
            tier = "ENTERPRISE"
            status = "ACTIVE"
            risk_score = round(rng.uniform(5.0, 22.0), 1)
            rating = round(rng.uniform(4.5, 5.0), 2)
        elif roll < 0.35:
            tier = "PREFERRED"
            status = "ACTIVE"
            risk_score = round(rng.uniform(15.0, 35.0), 1)
            rating = round(rng.uniform(4.2, 4.8), 2)
        elif roll < 0.93:
            tier = "STANDARD"
            status = "ACTIVE"
            risk_score = round(rng.uniform(20.0, 48.0), 1)
            rating = round(rng.uniform(3.8, 4.6), 2)
        elif roll < 0.97:
            tier = "PROBATION"
            status = "PROBATION"
            risk_score = round(rng.uniform(55.0, 78.0), 1)
            rating = round(rng.uniform(3.2, 4.1), 2)
        else:
            tier = "SUSPENDED"
            status = "SUSPENDED"
            risk_score = round(rng.uniform(75.0, 98.0), 1)
            rating = round(rng.uniform(2.4, 3.8), 2)

        onboarding_days = rng.randint(0, 700)
        onboarding_date = base_date + timedelta(days=onboarding_days)

        sellers.append({
            "seller_id": seller_id,
            "name": company_name,
            "tier": tier,
            "status": status,
            "risk_score": risk_score,
            "rating": rating,
            "onboarding_date": onboarding_date.strftime("%Y-%m-%d %H:%M:%S"),
            "bank_account_verified": 1,
            "country": "USA",
            "created_at": onboarding_date.strftime("%Y-%m-%d %H:%M:%S"),
        })

    return sellers
