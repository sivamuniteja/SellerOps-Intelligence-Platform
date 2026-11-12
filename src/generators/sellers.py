"""Deterministic Seller & Status Event Generator for SellerOps Intelligence Platform."""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from src.config import PlatformConfig

try:
    from faker import Faker
    _HAS_FAKER = True
except ImportError:
    _HAS_FAKER = False


FIRST_NAMES = [
    "Apex", "Prime", "Summit", "Nexus", "Beacon", "Vanguard", "Horizon", "Pinnacle",
    "Atlas", "Sterling", "Quantum", "Zenith", "Crestview", "TrueNorth", "Starlight",
    "Silverline", "Ironclad", "BlueWave", "GoldenGate", "Echo", "Timber", "Breeze"
]

LAST_NAMES = [
    "Retail", "Direct", "Logistics", "Enterprises", "Trading", "Supplies", "Goods",
    "Market", "Outlet", "Brands", "Wholesale", "Global", "Solutions", "Depot", "Hub"
]


def generate_sellers(count: int, config: PlatformConfig, seed: int = 20261022) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generate deterministic seller records and immutable status audit events.
    Returns (sellers, seller_status_events).
    """
    rng = random.Random(seed)
    fake = None
    if _HAS_FAKER:
        Faker.seed(seed)
        fake = Faker()

    sellers = []
    status_events = []
    base_date = datetime(2024, 1, 1, 0, 0, 0)
    event_idx = 1

    for i in range(1, count + 1):
        seller_id = f"SELL-{i:06d}"
        if fake:
            company_name = f"{fake.company()} {rng.randint(10, 99)}"
        else:
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

        onboarding_days = rng.randint(0, 500)
        onboarding_date = base_date + timedelta(days=onboarding_days, hours=rng.randint(8, 17))
        onboarding_str = onboarding_date.strftime("%Y-%m-%d %H:%M:%S")

        sellers.append({
            "seller_id": seller_id,
            "name": company_name,
            "tier": tier,
            "status": status,
            "risk_score": risk_score,
            "rating": rating,
            "onboarding_date": onboarding_str,
            "bank_account_verified": 1,
            "country": "USA",
            "created_at": onboarding_str,
            "updated_at": onboarding_str,
        })

        # Event 1: Initial KYC & Onboarding Event
        status_events.append({
            "event_id": f"SSE-{event_idx:06d}",
            "seller_id": seller_id,
            "previous_status": "UNDER_REVIEW",
            "new_status": "ACTIVE",
            "reason": "Completed initial merchant KYC and banking verification",
            "created_at": onboarding_str,
        })
        event_idx += 1

        # Event 2: If currently PROBATION or SUSPENDED, record transition event
        if status in ("PROBATION", "SUSPENDED"):
            transition_dt = onboarding_date + timedelta(days=rng.randint(30, 90), hours=rng.randint(1, 10))
            reason = "Late shipment rate exceeded threshold 4.0%" if status == "PROBATION" else "Order defect rate exceeded 1.0%; repeated customer chargebacks"
            status_events.append({
                "event_id": f"SSE-{event_idx:06d}",
                "seller_id": seller_id,
                "previous_status": "ACTIVE",
                "new_status": status,
                "reason": reason,
                "created_at": transition_dt.strftime("%Y-%m-%d %H:%M:%S"),
            })
            event_idx += 1

    return sellers, status_events
