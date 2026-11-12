"""Payout Calculation and Disbursement Eligibility Engine."""

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
import pandas as pd
from src.config import PlatformConfig, load_config


class PayoutEngine:
    """Calculates seller payout batches, disbursements, line items, and hold enforcement."""

    def __init__(self, config: Optional[PlatformConfig] = None):
        self.config = config or load_config()
        self.min_threshold = float(self.config.payout_rules.get("min_payout_threshold", 25.00))

    def evaluate_order_payout_eligibility(
        self,
        order_status: str,
        reserve_released: bool,
        seller_status: str,
        has_unresolved_dispute: bool = False,
    ) -> bool:
        """
        Determines whether an individual order settlement is eligible for payout inclusion.
        Conditions:
        1. Order must be DELIVERED.
        2. Rolling reserve must be released.
        3. Seller must not be SUSPENDED.
        4. No open/unresolved disputes.
        """
        if order_status != "DELIVERED":
            return False
        if not reserve_released:
            return False
        if seller_status == "SUSPENDED":
            return False
        if has_unresolved_dispute:
            return False
        return True

    def build_payout_batch(
        self,
        payout_id: str,
        seller_id: str,
        batch_date: datetime,
        eligible_items: List[Dict[str, any]],
        seller_status: str,
        inject_mismatch: bool = False,
    ) -> Dict[str, any]:
        """
        Builds a payout batch header and corresponding line items.
        If inject_mismatch is True (Anomaly 5), creates an artificial delta between
        the header total and the line items sum.
        """
        if not eligible_items:
            return None

        total_gross = Decimal("0.00")
        total_comm = Decimal("0.00")
        total_reserve = Decimal("0.00")
        total_disputes = Decimal("0.00")
        total_net = Decimal("0.00")

        lines = []
        for idx, item in enumerate(eligible_items):
            line_id = f"LN-{payout_id[3:]}-{idx+1:04d}"
            gross = Decimal(str(round(item["gross_amount"], 2)))
            comm = Decimal(str(round(item["commission_amount"], 2)))
            res = Decimal(str(round(item.get("reserve_held", 0.0), 2)))
            disp = Decimal(str(round(item.get("dispute_deducted", 0.0), 2)))
            net = gross - comm - res - disp

            total_gross += gross
            total_comm += comm
            total_reserve += res
            total_disputes += disp
            total_net += net

            lines.append({
                "line_id": line_id,
                "payout_id": payout_id,
                "order_id": item["order_id"],
                "order_amount": float(gross),
                "commission_deducted": float(comm),
                "reserve_deducted": float(res),
                "dispute_deducted": float(disp),
                "net_line_amount": float(net),
                "created_at": batch_date.isoformat(),
            })

        # Net payout amount
        final_net = total_net
        reconciliation_status = "MATCHED"

        if inject_mismatch:
            # Artificially alter the header total by +$125.00 to simulate Anomaly 5
            final_net = total_net + Decimal("125.00")
            reconciliation_status = "DISCREPANCY"

        payout_status = "PAID"
        if seller_status == "SUSPENDED" or final_net < Decimal(str(self.min_threshold)):
            payout_status = "HELD"

        batch_header = {
            "payout_id": payout_id,
            "seller_id": seller_id,
            "batch_date": batch_date.isoformat(),
            "total_orders_count": len(lines),
            "gross_sales": float(total_gross),
            "total_commission": float(total_comm),
            "total_reserve_held": float(total_reserve),
            "total_disputes_deducted": float(total_disputes),
            "net_payout_amount": float(final_net),
            "payout_status": payout_status,
            "reconciliation_status": reconciliation_status,
            "created_at": batch_date.isoformat(),
        }

        return {
            "header": batch_header,
            "lines": lines,
        }
