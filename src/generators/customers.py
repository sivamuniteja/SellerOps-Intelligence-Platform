"""Deterministic Customer Pool Generator."""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any

try:
    from faker import Faker
    _HAS_FAKER = True
except ImportError:
    _HAS_FAKER = False


FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White"
]

CITIES_STATES = [
    ("Seattle", "WA"), ("San Francisco", "CA"), ("Denver", "CO"), ("Austin", "TX"),
    ("Chicago", "IL"), ("Boston", "MA"), ("Atlanta", "GA"), ("Miami", "FL"),
    ("New York", "NY"), ("Los Angeles", "CA"), ("Phoenix", "AZ"), ("Philadelphia", "PA")
]


def generate_customers(count: int, seed: int = 42) -> List[Dict[str, Any]]:
    """Generate realistic customer records."""
    rng = random.Random(seed)
    fake = None
    if _HAS_FAKER:
        Faker.seed(seed)
        fake = Faker()

    customers = []
    base_date = datetime(2024, 1, 1, 0, 0, 0)

    for i in range(1, count + 1):
        cust_id = f"CST-{i:05d}"
        if fake:
            name = fake.name()
            email = f"user_{i}_{fake.user_name()}@example.com"
            city = fake.city()
            state = fake.state_abbr()
        else:
            fname = rng.choice(FIRST_NAMES)
            lname = rng.choice(LAST_NAMES)
            name = f"{fname} {lname}"
            email = f"{fname.lower()}.{lname.lower()}{rng.randint(10, 999)}@example.com"
            city, state = rng.choice(CITIES_STATES)

        created_at = base_date + timedelta(days=rng.randint(0, 600), hours=rng.randint(0, 23))

        customers.append({
            "customer_id": cust_id,
            "name": name,
            "email": email,
            "city": city,
            "state": state,
            "country": "USA",
            "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
        })

    return customers
