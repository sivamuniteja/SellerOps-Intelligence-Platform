"""Rolling Reserve Calculation Engine for SellerOps Intelligence Platform."""

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional
from src.config import PlatformConfig, load_config


class ReserveEngine:
    """Manages risk-based rolling reserve percentages and release schedules."""

    def __init__(self, config: Optional[PlatformConfig] = None):
        self.config = config or load_config()

    def calculate_reserve(
        self,
        gross_amount: float,
        seller_tier: str,
        risk_score: float,
        delivery_date: datetime,
    ) -> Dict[str, any]:
        """
        Calculate rolling reserve hold amount and release target date based on tier and risk score.
        """
        tier_cfg = self.config.seller_tiers.get(seller_tier)
        base_rate = tier_cfg.reserve_rate if tier_cfg else 0.10
        base_hold_days = tier_cfg.hold_days if tier_cfg else 14

        # Risk score modifier: sellers with risk > 65 incur an additional 5% reserve hold and 7 days delay
        risk_surcharge = 0.05 if risk_score > 65.0 else 0.0
        extra_days = 7 if risk_score > 65.0 else 0

        effective_rate = min(1.00, round(base_rate + risk_surcharge, 4))
        hold_days = base_hold_days + extra_days

        gross_dec = Decimal(str(round(gross_amount, 2)))
        rate_dec = Decimal(str(effective_rate))
        reserve_amount = float((gross_dec * rate_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

        release_date = delivery_date + timedelta(days=hold_days)

        return {
            "reserve_rate": effective_rate,
            "reserve_amount": reserve_amount,
            "hold_days": hold_days,
            "release_date": release_date,
        }

    def is_reserve_eligible_for_release(
        self,
        delivery_date: datetime,
        hold_days: int,
        as_of_date: datetime,
        seller_status: str,
    ) -> bool:
        """Reserve can be released if hold duration has elapsed and seller is not SUSPENDED."""
        if seller_status == "SUSPENDED":
            return False
        release_date = delivery_date + timedelta(days=hold_days)
        return as_of_date >= release_date
