"""Seller Performance Scorecard and SLA Monitoring Service."""

from typing import Dict, List, Optional
import pandas as pd
from src.config import PlatformConfig, load_config


class SellerMetricsEngine:
    """Calculates seller SLA metrics, defect rates, cancellation rates, and risk scores."""

    def __init__(self, config: Optional[PlatformConfig] = None):
        self.config = config or load_config()
        self.max_lsr = float(self.config.sla_thresholds.get("max_late_shipment_rate", 0.04))
        self.max_cr = float(self.config.sla_thresholds.get("max_cancellation_rate", 0.025))
        self.max_odr = float(self.config.sla_thresholds.get("max_order_defect_rate", 0.01))

    def compute_seller_scorecard(
        self,
        total_orders: int,
        late_shipments: int,
        cancelled_orders: int,
        disputed_orders: int,
        avg_rating: float,
        gmv: float,
    ) -> Dict[str, any]:
        """
        Compute SLA percentages, risk score (0-100), and policy compliance recommendation.
        """
        if total_orders == 0:
            return {
                "total_orders": 0,
                "gmv": 0.0,
                "late_shipment_rate": 0.0,
                "cancellation_rate": 0.0,
                "order_defect_rate": 0.0,
                "avg_rating": avg_rating,
                "risk_score": 10.0,
                "compliance_status": "COMPLIANT",
                "recommended_tier": "STANDARD",
            }

        lsr = round(late_shipments / total_orders, 4)
        cr = round(cancelled_orders / total_orders, 4)
        odr = round(disputed_orders / total_orders, 4)

        # Risk scoring algorithm: weights late shipments, cancels, disputes, and ratings
        # Base risk: 10
        # ODR penalty: up to 40 pts
        # LSR penalty: up to 25 pts
        # CR penalty: up to 15 pts
        # Rating penalty: up to 20 pts
        rating_penalty = max(0.0, (5.0 - avg_rating) * 5.0)
        odr_penalty = min(40.0, (odr / 0.05) * 40.0)
        lsr_penalty = min(25.0, (lsr / 0.10) * 25.0)
        cr_penalty = min(15.0, (cr / 0.08) * 15.0)

        raw_risk = 10.0 + rating_penalty + odr_penalty + lsr_penalty + cr_penalty
        risk_score = round(min(100.0, max(0.0, raw_risk)), 1)

        # Compliance evaluation
        is_breaching = (lsr > self.max_lsr) or (cr > self.max_cr) or (odr > self.max_odr)

        if risk_score >= 80.0 or odr > 0.05:
            compliance_status = "CRITICAL_ACTION_REQUIRED"
            recommended_tier = "SUSPENDED"
        elif is_breaching or risk_score >= 50.0:
            compliance_status = "PROBATION_WARNING"
            recommended_tier = "PROBATION"
        elif gmv >= 50000.0 and risk_score < 25.0:
            compliance_status = "COMPLIANT"
            recommended_tier = "ENTERPRISE"
        elif gmv >= 10000.0 and risk_score < 35.0:
            compliance_status = "COMPLIANT"
            recommended_tier = "PREFERRED"
        else:
            compliance_status = "COMPLIANT"
            recommended_tier = "STANDARD"

        return {
            "total_orders": total_orders,
            "gmv": round(gmv, 2),
            "late_shipment_rate": lsr,
            "cancellation_rate": cr,
            "order_defect_rate": odr,
            "avg_rating": round(avg_rating, 2),
            "risk_score": risk_score,
            "compliance_status": compliance_status,
            "recommended_tier": recommended_tier,
        }
