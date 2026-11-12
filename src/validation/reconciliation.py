"""Financial Reconciliation and Ledger Consistency Validator."""

from decimal import Decimal
from typing import Dict, List, Any
import pandas as pd
from src.database.connection import DatabaseManager


class FinancialReconciliation:
    """Verifies ledger balance, payout header vs line item matching, and fee accuracy."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def reconcile_all(self) -> Dict[str, Any]:
        """Run all financial reconciliation checks."""
        payout_reconciliation = self.reconcile_payout_batches()
        settlement_reconciliation = self.reconcile_settlements()

        return {
            "payouts": payout_reconciliation,
            "settlements": settlement_reconciliation,
            "is_fully_reconciled": (
                payout_reconciliation["discrepancy_count"] == 0
                and settlement_reconciliation["discrepancy_count"] == 0
            ),
        }

    def reconcile_payout_batches(self) -> Dict[str, Any]:
        """
        Compare batch header net_payout_amount with SUM(payout_lines.net_line_amount).
        Flags discrepancies (such as Anomaly 5).
        """
        q = """
            SELECT
                p.payout_id,
                p.seller_id,
                p.batch_date,
                ROUND(p.net_payout_amount, 2) as header_net,
                ROUND(COALESCE(SUM(l.net_line_amount), 0.0), 2) as lines_net_sum,
                ROUND(p.net_payout_amount - COALESCE(SUM(l.net_line_amount), 0.0), 2) as variance,
                COUNT(l.line_id) as line_count
            FROM payout_batches p
            LEFT JOIN payout_lines l ON p.payout_id = l.payout_id
            GROUP BY p.payout_id
            HAVING ABS(header_net - lines_net_sum) > 0.01;
        """
        df = self.db.query_df(q)
        discrepancies = df.to_dict(orient="records")

        # Total summary across all batches
        summary_q = """
            SELECT
                COUNT(*) as total_batches,
                ROUND(SUM(net_payout_amount), 2) as total_disbursed_headers
            FROM payout_batches;
        """
        summary_df = self.db.query_df(summary_q)
        total_batches = int(summary_df["total_batches"].iloc[0]) if not summary_df.empty else 0
        total_headers = float(summary_df["total_disbursed_headers"].iloc[0]) if not summary_df.empty and summary_df["total_disbursed_headers"].iloc[0] is not None else 0.0

        return {
            "total_batches_checked": total_batches,
            "total_disbursed_headers": total_headers,
            "discrepancy_count": len(discrepancies),
            "discrepancies": discrepancies,
            "matched_count": total_batches - len(discrepancies),
        }

    def reconcile_settlements(self) -> Dict[str, Any]:
        """
        Verify: gross_amount = commission_amount + reserve_amount + net_seller_amount.
        """
        q = """
            SELECT
                settlement_id,
                order_id,
                ROUND(gross_amount, 2) as gross,
                ROUND(commission_amount, 2) as commission,
                ROUND(reserve_amount, 2) as reserve,
                ROUND(net_seller_amount, 2) as net,
                ROUND(gross_amount - (commission_amount + reserve_amount + net_seller_amount), 2) as delta
            FROM order_settlements
            WHERE ABS(gross_amount - (commission_amount + reserve_amount + net_seller_amount)) > 0.02;
        """
        df = self.db.query_df(q)
        discrepancies = df.to_dict(orient="records")
        return {
            "discrepancy_count": len(discrepancies),
            "discrepancies": discrepancies,
        }
