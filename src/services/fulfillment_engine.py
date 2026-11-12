"""Fulfillment Tracking and SLA Calculation Engine for SellerOps Intelligence Platform."""

from datetime import datetime, timedelta
from typing import Dict, Optional
from src.config import PlatformConfig, load_config


class FulfillmentEngine:
    """Computes fulfillment transit metrics and SLA compliance status."""

    def __init__(self, config: Optional[PlatformConfig] = None):
        self.config = config or load_config()
        self.dispatch_limit_hours = int(self.config.sla_thresholds.get("dispatch_window_hours", 48))

    def evaluate_sla(
        self,
        order_date: datetime,
        dispatched_at: Optional[datetime],
        delivered_at: Optional[datetime],
        is_cancelled: bool = False,
    ) -> Dict[str, any]:
        """
        Evaluate fulfillment SLA against standard 48h dispatch window.
        """
        if is_cancelled or dispatched_at is None:
            return {
                "sla_status": "CANCELLED" if is_cancelled else "IN_TRANSIT",
                "dispatch_delay_hours": None,
                "transit_days": None,
                "is_late": False,
            }

        dispatch_delta = dispatched_at - order_date
        dispatch_delay_hours = round(dispatch_delta.total_seconds() / 3600.0, 1)

        is_late = dispatch_delay_hours > self.dispatch_limit_hours

        transit_days = None
        if delivered_at and delivered_at >= dispatched_at:
            transit_delta = delivered_at - dispatched_at
            transit_days = max(1, int(transit_delta.total_seconds() / 86400.0))

        sla_status = "LATE" if is_late else "ON_TIME"
        if not delivered_at and not is_late:
            sla_status = "IN_TRANSIT"

        return {
            "sla_status": sla_status,
            "dispatch_delay_hours": dispatch_delay_hours,
            "transit_days": transit_days,
            "is_late": is_late,
        }
