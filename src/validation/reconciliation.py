"""Financial Reconciliation and Ledger Consistency Validator."""

from typing import Dict, List, Any
import pandas as pd
from src.database.connection import DatabaseManager


class FinancialReconciliation:
    """
    Verifies:
    - Order header total vs sum of order lines (Multi-seller reconciliation)
    - Payout batch header net vs sum of payout lines (Disbursement reconciliation)
    - Commission fee calculation correctness against ledger entries
    - Reserve hold calculation correctness against ledger entries
    - Dispute deductions and clawback enforcement
    """

    def __init__(self, db: DatabaseManager):
        self.db = db

    def reconcile_all(self) -> Dict[str, Any]:
        """Run all financial reconciliation checks."""
        order_line_rec = self.reconcile_order_lines_sum()
        payout_rec = self.reconcile_payout_batches()
        commission_rec = self.reconcile_commissions()
        reserve_rec = self.reconcile_reserves()
        dispute_rec = self.reconcile_dispute_deductions()

        total_discrepancies = (
            order_line_rec["discrepancy_count"]
            + payout_rec["discrepancy_count"]
            + commission_rec["discrepancy_count"]
            + reserve_rec["discrepancy_count"]
            + dispute_rec["discrepancy_count"]
        )

        return {
            "is_fully_reconciled": total_discrepancies == 0,
            "total_discrepancies": total_discrepancies,
            "order_lines": order_line_rec,
            "payouts": payout_rec,
            "commissions": commission_rec,
            "reserves": reserve_rec,
            "disputes": dispute_rec,
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
            "valid": len(discrepancies) == 0,
            "discrepancy_count": len(discrepancies),
            "discrepancies": discrepancies,
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
            "valid": len(discrepancies) == 0,
            "total_batches_checked": total_batches,
            "total_disbursed_cents": total_cents,
            "discrepancy_count": len(discrepancies),
            "discrepancies": discrepancies,
            "matched_count": total_batches - len(discrepancies),
        }

    def reconcile_commissions(self) -> Dict[str, Any]:
        """
        Verify that commission_ledger entries match expected variable fee + fixed fee formulas.
        Flags inflated/double fees (such as Anomaly 2).
        """
        q = """
            SELECT
                c.entry_id,
                c.order_line_id,
                c.seller_id,
                c.gross_amount_cents,
                c.rate_basis_points,
                c.variable_fee_cents,
                c.fixed_fee_cents,
                c.total_commission_cents,
                (c.variable_fee_cents + c.fixed_fee_cents) as expected_total_cents,
                (c.total_commission_cents - (c.variable_fee_cents + c.fixed_fee_cents)) as variance_cents
            FROM commission_ledger c
            WHERE c.total_commission_cents != (c.variable_fee_cents + c.fixed_fee_cents)
               OR c.variable_fee_cents < ((c.gross_amount_cents * c.rate_basis_points) / 10000);
        """
        df = self.db.query_df(q)
        discrepancies = df.to_dict(orient="records")
        return {
            "valid": len(discrepancies) == 0,
            "discrepancy_count": len(discrepancies),
            "discrepancies": discrepancies,
        }

    def reconcile_reserves(self) -> Dict[str, Any]:
        """Verify reserve hold arithmetic: reserve_amount_cents = (gross_amount_cents * reserve_rate_basis_points) // 10000."""
        q = """
            SELECT
                r.entry_id,
                r.order_line_id,
                r.seller_id,
                ol.gross_amount_cents,
                r.reserve_rate_basis_points,
                r.reserve_amount_cents,
                ((ol.gross_amount_cents * r.reserve_rate_basis_points) / 10000) as expected_reserve_cents,
                (r.reserve_amount_cents - ((ol.gross_amount_cents * r.reserve_rate_basis_points) / 10000)) as variance_cents
            FROM reserve_ledger r
            JOIN order_lines ol ON r.order_line_id = ol.order_line_id
            WHERE ABS(r.reserve_amount_cents - ((ol.gross_amount_cents * r.reserve_rate_basis_points) / 10000)) > 1;
        """
        df = self.db.query_df(q)
        discrepancies = df.to_dict(orient="records")
        return {
            "valid": len(discrepancies) == 0,
            "discrepancy_count": len(discrepancies),
            "discrepancies": discrepancies,
        }

    def reconcile_dispute_deductions(self) -> Dict[str, Any]:
        """
        Verify that all finalized buyer-favor disputes or lost chargebacks have been deducted/clawed back.
        Flags unclawbacked disputes (Anomaly 4).
        """
        q = """
            SELECT
                d.dispute_id,
                d.order_id,
                d.order_line_id,
                d.seller_id,
                d.disputed_amount_cents,
                d.status as dispute_status,
                d.clawback_applied
            FROM disputes d
            WHERE d.status IN ('RESOLVED_BUYER_FAVOR', 'CHARGEBACK_LOST')
              AND d.clawback_applied = 0;
        """
        df = self.db.query_df(q)
        discrepancies = df.to_dict(orient="records")
        return {
            "valid": len(discrepancies) == 0,
            "discrepancy_count": len(discrepancies),
            "discrepancies": discrepancies,
        }
