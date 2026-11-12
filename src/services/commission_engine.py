"""Commission Calculation Engine for SellerOps Intelligence Platform."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional
from src.config import PlatformConfig, load_config


class CommissionEngine:
    """Computes marketplace commissions and transaction fees by category and seller tier."""

    def __init__(self, config: Optional[PlatformConfig] = None):
        self.config = config or load_config()
        self.category_rates: Dict[str, float] = {
            cat.name: cat.base_commission_rate for cat in self.config.categories
        }
        self.category_mins: Dict[str, float] = {
            cat.name: cat.min_commission for cat in self.config.categories
        }
        self.fixed_fee = float(self.config.payout_rules.get("fixed_transaction_fee", 0.30))

    def calculate_commission(
        self,
        gross_amount: float,
        category: str,
        seller_tier: str,
    ) -> Dict[str, float]:
        """
        Calculate commission rate and amount for an order.
        Returns dict with effective_rate, variable_commission, fixed_fee, total_commission.
        """
        base_rate = self.category_rates.get(category, 0.12)
        min_comm = self.category_mins.get(category, 0.50)

        tier_config = self.config.seller_tiers.get(seller_tier)
        tier_discount = tier_config.commission_discount if tier_config else 0.0

        effective_rate = max(0.01, round(base_rate - tier_discount, 4))

        # Precision calculation
        gross_dec = Decimal(str(round(gross_amount, 2)))
        rate_dec = Decimal(str(effective_rate))
        raw_commission = float((gross_dec * rate_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

        variable_commission = max(raw_commission, min_comm)
        total_commission = round(variable_commission + self.fixed_fee, 2)

        return {
            "effective_rate": effective_rate,
            "variable_commission": variable_commission,
            "fixed_fee": self.fixed_fee,
            "total_commission": total_commission,
        }
