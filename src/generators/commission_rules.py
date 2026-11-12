"""Deterministic Commission Rules Generator."""

from typing import List, Dict, Any
from src.config import PlatformConfig


def generate_commission_rules(config: PlatformConfig) -> List[Dict[str, Any]]:
    """Generate canonical effective-dated commission rules across categories and tiers."""
    rules = []
    rule_idx = 1
    tiers = ["ENTERPRISE", "PREFERRED", "STANDARD", "PROBATION"]

    for cat in config.categories:
        base_bps = int(cat.base_commission_rate * 10000)  # e.g. 0.08 -> 800 bps
        min_cents = int(cat.min_commission * 100)        # e.g. $0.50 -> 50 cents
        fixed_cents = 30                                 # $0.30 -> 30 cents

        for tier in tiers:
            tier_cfg = config.seller_tiers.get(tier)
            discount_bps = int((tier_cfg.commission_discount if tier_cfg else 0.0) * 10000)
            effective_bps = max(100, base_bps - discount_bps)

            rules.append({
                "rule_id": f"CR-{rule_idx:06d}",
                "category": cat.name,
                "seller_tier": tier,
                "base_rate_basis_points": effective_bps,
                "min_commission_cents": min_cents,
                "fixed_fee_cents": fixed_cents,
                "effective_from": "2024-01-01 00:00:00",
                "effective_to": "2027-12-31 23:59:59",
                "is_active": 1,
                "created_at": "2024-01-01 00:00:00",
            })
            rule_idx += 1

    return rules
