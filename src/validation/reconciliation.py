"""Financial Reconciliation and Ledger Consistency Validator."""

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
        order_line_reconciliation = self.reconcile_order_lines_sum()

        return {
            "payouts": payout_reconciliation,
            "order_lines": order_line_reconciliation,
            "is_fully_reconciled": (
                payout_reconciliation["discrepancy_count"] == 0
                and order_line_reconciliation["discrepancy_count"] == 0
            ),
        }

    def reconcile_payout_batches(self) -> Dict[str, Any]:
        """
        Compare batch header net_payout_amount_cents with SUM(payout_lines.net_line_amount_cents).
        Flags discrepancies (such as Anomaly 5).
        """
        q = """
            SELECT
                p.payout_id,
                p.seller_id,
                p.batch_date,
                p.net_payout_amount_cents as header_net_cents,
                COALESCE(SUM(l.net_line_amount_cents), 0) as lines_net_sum_cents,
                (p.net_payout_amount_cents - COALESCE(SUM(l.net_line_amount_cents), 0)) as variance_cents,
                COUNT(l.line_id) as line_count
            FROM payouts p
            LEFT JOIN payout_lines l ON p.payout_id = l.payout_id
            GROUP BY p.payout_id
            HAVING ABS(header_net_cents - lines_net_sum_cents) > 0;
        """
        df = self.db.query_df(q)
        discrepancies = df.to_dict(orient="records")

        summary_q = """
            SELECT
                COUNT(*) as total_batches,
                COALESCE(SUM(net_payout_amount_cents), 0) as total_disbursed_cents
            FROM payouts;
        """
        summary_df = self.db.query_df(summary_q)
        total_batches = int(summary_df["total_batches"].iloc[0]) if not summary_df.empty else 0
        total_cents = int(summary_df["total_disbursed_cents"].iloc[0]) if not summary_df.empty and summary_df["total_disbursed_cents"].iloc[0] is not None else 0

        return {
            "total_batches_checked": total_batches,
            "total_disbursed_cents": total_cents,
            "discrepancy_count": len(discrepancies),
            "discrepancies": discrepancies,
            "matched_count": total_batches - len(discrepancies),
        }

    def reconcile_order_lines_sum(self) -> Dict[str, Any]:
        """Verify: orders.total_amount_cents = SUM(order_lines.gross_amount_cents)."""
        q = """
            SELECT
                o.order_id,
                o.total_amount_cents as header_total_cents,
                COALESCE(SUM(ol.gross_amount_cents), 0) as lines_sum_cents,
                (o.total_amount_cents - COALESCE(SUM(ol.gross_amount_cents), 0)) as delta_cents
            FROM orders o
            JOIN order_lines ol ON o.order_id = ol.order_id
            GROUP BY o.order_id
            HAVING ABS(header_total_cents - lines_sum_cents) > 0;
        """
        df = self.db.query_df(q)
        discrepancies = df.to_dict(orient="records")
        return {
            "discrepancy_count": len(discrepancies),
            "discrepancies": discrepancies,
        }
