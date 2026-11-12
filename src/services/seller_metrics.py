"""Seller Performance Scorecard, SLA Monitoring, and Financial Health Metrics Engine."""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from src.config import PlatformConfig, load_config


class SellerMetricsError(Exception):
    """Base exception for seller metrics errors."""
    pass


class SellerNotFoundError(SellerMetricsError):
    """Raised when a seller is not found in the database."""
    pass


class SellerMetricsEngine:
    """
    Calculates seller SLA metrics, defect rates, cancellation rates, financial balances,
    and risk indicators from real database records or aggregated inputs.
    Defines every denominator and supports time window filtering.
    """

    def __init__(self, config: Optional[PlatformConfig] = None):
        self.config = config or load_config()
        self.max_lsr = float(self.config.sla_thresholds.get("max_late_shipment_rate", 0.04))
        self.max_cr = float(self.config.sla_thresholds.get("max_cancellation_rate", 0.025))
        self.max_odr = float(self.config.sla_thresholds.get("max_order_defect_rate", 0.01))
        self.min_rating = float(self.config.sla_thresholds.get("min_seller_rating", 4.2))

    def compute_seller_scorecard(
        self,
        total_orders: int,
        late_shipments: int,
        cancelled_orders: int,
        disputed_orders: int,
        avg_rating: float,
        gmv: float,
    ) -> Dict[str, Any]:
        """
        Compute SLA percentages, risk score (0-100), and policy compliance recommendation
        from aggregated counts (backward-compatible API).
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

    def calculate_seller_metrics(
        self,
        seller_id: str,
        db_conn: sqlite3.Connection,
        as_of_date: Optional[Union[str, datetime]] = None,
        window_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Calculate complete metrics suite for a seller directly from database tables.
        Defines every denominator and supports time window filtering.
        """
        cursor = db_conn.cursor()

        # Verify seller exists
        cursor.execute("SELECT seller_id, name, status, tier, risk_score FROM sellers WHERE seller_id = ?", (seller_id,))
        seller_row = cursor.fetchone()
        if not seller_row:
            raise SellerNotFoundError(f"Seller '{seller_id}' not found in database.")

        seller_name, seller_status, seller_tier, db_risk_score = (
            seller_row[1],
            seller_row[2],
            seller_row[3],
            seller_row[4],
        )

        # Date window clause
        date_filter = ""
        params: List[Any] = [seller_id]

        if as_of_date:
            as_of_dt = as_of_date if isinstance(as_of_date, datetime) else datetime.fromisoformat(str(as_of_date))
            as_of_str = as_of_dt.strftime("%Y-%m-%d %H:%M:%S")
            if window_days:
                start_dt = as_of_dt - timedelta(days=window_days)
                start_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
                date_filter = "AND o.order_date BETWEEN ? AND ?"
                params.extend([start_str, as_of_str])
            else:
                date_filter = "AND o.order_date <= ?"
                params.append(as_of_str)

        # 1. Orders and Order Lines
        cursor.execute(
            f"""
            SELECT
                COUNT(DISTINCT ol.order_id) AS total_orders,
                COUNT(ol.order_line_id) AS total_lines,
                COALESCE(SUM(ol.gross_amount_cents), 0) AS total_gmv_cents,
                SUM(CASE WHEN ol.line_status = 'DELIVERED' THEN 1 ELSE 0 END) AS delivered_lines,
                SUM(CASE WHEN ol.line_status = 'CANCELLED' THEN 1 ELSE 0 END) AS cancelled_lines,
                SUM(CASE WHEN ol.line_status IN ('SHIPPED', 'DELIVERED') THEN 1 ELSE 0 END) AS shipped_lines
            FROM order_lines ol
            JOIN orders o ON ol.order_id = o.order_id
            WHERE ol.seller_id = ? {date_filter}
            """,
            params,
        )
        ord_stats = cursor.fetchone()
        total_orders = ord_stats[0] or 0
        total_lines = ord_stats[1] or 0
        gmv_cents = ord_stats[2] or 0
        delivered_lines = ord_stats[3] or 0
        cancelled_lines = ord_stats[4] or 0
        shipped_lines = ord_stats[5] or 0

        # 2. Fulfillment Metrics (Late shipments, SLA breach)
        flf_params = [seller_id]
        flf_date_filter = ""
        if as_of_date:
            if window_days:
                flf_date_filter = "AND o.order_date BETWEEN ? AND ?"
                flf_params.extend([start_str, as_of_str])
            else:
                flf_date_filter = "AND o.order_date <= ?"
                flf_params.append(as_of_str)

        cursor.execute(
            f"""
            SELECT
                SUM(CASE WHEN f.sla_status = 'LATE' THEN 1 ELSE 0 END) AS late_shipments,
                SUM(CASE WHEN f.sla_status = 'ON_TIME' AND f.delivered_at IS NOT NULL THEN 1 ELSE 0 END) AS on_time_deliveries,
                COUNT(f.fulfillment_id) AS total_fulfillments
            FROM fulfillments f
            JOIN orders o ON f.order_id = o.order_id
            WHERE f.seller_id = ? {flf_date_filter}
            """,
            flf_params,
        )
        flf_stats = cursor.fetchone()
        late_shipments = flf_stats[0] or 0
        on_time_deliveries = flf_stats[1] or 0
        total_fulfillments = flf_stats[2] or 0

        # 3. Disputes
        disp_params = [seller_id]
        disp_filter = ""
        if as_of_date:
            if window_days:
                disp_filter = "AND dispute_date BETWEEN ? AND ?"
                disp_params.extend([start_str, as_of_str])
            else:
                disp_filter = "AND dispute_date <= ?"
                disp_params.append(as_of_str)

        cursor.execute(
            f"""
            SELECT COUNT(dispute_id)
            FROM disputes
            WHERE seller_id = ? {disp_filter}
            """,
            disp_params,
        )
        dispute_count = cursor.fetchone()[0] or 0

        # 4. Reviews
        cursor.execute(
            """
            SELECT COUNT(review_id), COALESCE(AVG(rating), 4.5)
            FROM customer_reviews
            WHERE seller_id = ?
            """,
            (seller_id,),
        )
        rev_stats = cursor.fetchone()
        review_count = rev_stats[0] or 0
        avg_rating = round(float(rev_stats[1]), 2) if rev_stats[1] is not None else 4.5

        # 5. Commission Revenue
        cursor.execute(
            """
            SELECT COALESCE(SUM(total_commission_cents), 0)
            FROM commission_ledger
            WHERE seller_id = ?
            """,
            (seller_id,),
        )
        commission_rev_cents = cursor.fetchone()[0] or 0

        # 6. Reserve Balance
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(reserve_amount_cents), 0),
                COALESCE(SUM(CASE WHEN status = 'RELEASED' THEN reserve_amount_cents ELSE 0 END), 0)
            FROM reserve_ledger
            WHERE seller_id = ?
            """,
            (seller_id,),
        )
        res_row = cursor.fetchone()
        total_reserve_held_cents = res_row[0] or 0
        total_reserve_released_cents = res_row[1] or 0
        reserve_balance_cents = total_reserve_held_cents - total_reserve_released_cents

        # 7. Payouts (Pending & Paid)
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN payout_status IN ('PENDING', 'HELD', 'SCHEDULED', 'PROCESSING') THEN net_payout_amount_cents ELSE 0 END), 0) AS pending_amount_cents,
                COALESCE(SUM(CASE WHEN payout_status IN ('PENDING', 'HELD', 'SCHEDULED', 'PROCESSING') THEN 1 ELSE 0 END), 0) AS pending_count,
                COALESCE(SUM(CASE WHEN payout_status = 'PAID' THEN net_payout_amount_cents ELSE 0 END), 0) AS paid_amount_cents,
                COALESCE(SUM(CASE WHEN payout_status = 'PAID' THEN 1 ELSE 0 END), 0) AS paid_count
            FROM payouts
            WHERE seller_id = ?
            """,
            (seller_id,),
        )
        po_row = cursor.fetchone()
        pending_payout_cents = po_row[0] or 0
        pending_payout_count = po_row[1] or 0
        paid_payout_cents = po_row[2] or 0
        paid_payout_count = po_row[3] or 0

        # Exact Rate Calculations with Explicit Denominators
        fulfillment_rate = round(delivered_lines / total_lines, 4) if total_lines > 0 else 1.0
        late_shipment_rate = round(late_shipments / shipped_lines, 4) if shipped_lines > 0 else 0.0
        on_time_delivery_rate = round(on_time_deliveries / delivered_lines, 4) if delivered_lines > 0 else 1.0
        dispute_rate = round(dispute_count / total_orders, 4) if total_orders > 0 else 0.0
        cancellation_rate = round(cancelled_lines / total_lines, 4) if total_lines > 0 else 0.0

        gmv_dollars = round(gmv_cents / 100.0, 2)
        scorecard = self.compute_seller_scorecard(
            total_orders=total_orders,
            late_shipments=late_shipments,
            cancelled_orders=cancelled_lines,
            disputed_orders=dispute_count,
            avg_rating=avg_rating,
            gmv=gmv_dollars,
        )

        return {
            "seller_id": seller_id,
            "seller_name": seller_name,
            "seller_status": seller_status,
            "seller_tier": seller_tier,
            "time_window": f"{window_days} Days" if window_days else "ALL_TIME",
            # Order & Volume Metrics
            "total_orders": total_orders,
            "total_order_lines": total_lines,
            "total_fulfilled_orders": delivered_lines,
            "fulfillment_rate": fulfillment_rate,
            "gmv_cents": gmv_cents,
            "gmv": gmv_dollars,
            # SLA & Defect Rates
            "total_shipped_orders": shipped_lines,
            "late_shipment_count": late_shipments,
            "late_shipment_rate": late_shipment_rate,
            "on_time_delivery_count": on_time_deliveries,
            "on_time_delivery_rate": on_time_delivery_rate,
            "dispute_count": dispute_count,
            "dispute_rate": dispute_rate,
            "cancellation_count": cancelled_lines,
            "cancellation_rate": cancellation_rate,
            "review_count": review_count,
            "avg_rating": avg_rating,
            # Financial Balances
            "commission_revenue_cents": commission_rev_cents,
            "commission_revenue": round(commission_rev_cents / 100.0, 2),
            "reserve_balance_cents": reserve_balance_cents,
            "reserve_balance": round(reserve_balance_cents / 100.0, 2),
            "pending_payouts_cents": pending_payout_cents,
            "pending_payouts_amount": round(pending_payout_cents / 100.0, 2),
            "pending_payouts_count": pending_payout_count,
            "paid_payouts_cents": paid_payout_cents,
            "paid_payouts_amount": round(paid_payout_cents / 100.0, 2),
            "paid_payouts_count": paid_payout_count,
            # Risk Indicators
            "risk_score": scorecard["risk_score"],
            "compliance_status": scorecard["compliance_status"],
            "recommended_tier": scorecard["recommended_tier"],
            # Explicit Denominators Specification
            "denominators": {
                "fulfillment_rate": "Delivered Order Lines / Total Order Lines",
                "late_shipment_rate": "Late Shipments / Total Shipped Lines",
                "on_time_delivery_rate": "On-Time Deliveries / Total Delivered Lines",
                "dispute_rate": "Dispute Count / Total Distinct Orders",
                "cancellation_rate": "Cancelled Order Lines / Total Order Lines",
                "avg_rating": "Sum of Ratings / Total Customer Reviews",
            },
        }

    def compute_all_sellers_metrics(
        self,
        db_conn: sqlite3.Connection,
        as_of_date: Optional[Union[str, datetime]] = None,
        window_days: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Compute metrics for all active sellers in the database."""
        cursor = db_conn.cursor()
        cursor.execute("SELECT seller_id FROM sellers ORDER BY seller_id ASC")
        seller_ids = [row[0] for row in cursor.fetchall()]

        return [
            self.calculate_seller_metrics(sid, db_conn, as_of_date=as_of_date, window_days=window_days)
            for sid in seller_ids
        ]
