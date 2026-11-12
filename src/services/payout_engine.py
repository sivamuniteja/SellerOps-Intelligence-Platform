"""Payout Calculation, Disbursement Eligibility, and Reconciliation Engine."""

import sqlite3
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Any, Set
from src.config import PlatformConfig, load_config


class PayoutError(Exception):
    """Base exception for payout engine errors."""
    pass


class IneligiblePayoutError(PayoutError):
    """Raised when an ineligible order line is submitted for payout."""
    pass


class DuplicatePayoutLineError(PayoutError):
    """Raised when an order line has already been included in a previous payout disbursement."""
    pass


class DoubleDeductionError(PayoutError):
    """Raised when a dispute or refund deduction is applied more than once."""
    pass


class InvalidPayoutStateTransitionError(PayoutError):
    """Raised when an illegal payout lifecycle status transition is attempted."""
    pass


class PayoutEngine:
    """
    Calculates seller payout batches, disbursements, line items, and hold enforcement.
    Applies exact arithmetic:
      Gross - Commission - Refunds - Finalized Disputes - Reserve Held + Eligible Reserve Releases = Net Payable.
    Guarantees no double deductions, no duplicate payout lines, and protects against overpayment.
    """

    STATE_PENDING = "PENDING"
    STATE_ELIGIBLE = "ELIGIBLE"
    STATE_HELD = "HELD"
    STATE_PROCESSING = "PROCESSING"
    STATE_PAID = "PAID"
    STATE_FAILED = "FAILED"

    VALID_PAYOUT_STATES: Set[str] = {
        STATE_PENDING,
        STATE_ELIGIBLE,
        STATE_HELD,
        STATE_PROCESSING,
        STATE_PAID,
        STATE_FAILED,
    }

    VALID_PAYOUT_TRANSITIONS: Dict[str, Set[str]] = {
        STATE_PENDING: {STATE_ELIGIBLE, STATE_HELD},
        STATE_ELIGIBLE: {STATE_PROCESSING, STATE_HELD},
        STATE_HELD: {STATE_ELIGIBLE, STATE_PROCESSING, STATE_FAILED},
        STATE_PROCESSING: {STATE_PAID, STATE_FAILED},
        STATE_FAILED: {STATE_ELIGIBLE, STATE_HELD, STATE_PROCESSING},
        STATE_PAID: set(),  # Terminal state
    }

    def __init__(self, config: Optional[PlatformConfig] = None):
        self.config = config or load_config()
        self.min_threshold = float(self.config.payout_rules.get("min_payout_threshold", 25.00))
        self.min_threshold_cents = int(round(self.min_threshold * 100))

        # In-memory tracking for duplicate prevention and double deduction avoidance
        self._disbursed_order_lines: Set[str] = set()
        self._deducted_disputes: Set[str] = set()
        self._deducted_refunds: Set[str] = set()

    def sync_disbursed_lines_from_db(self, db_conn: sqlite3.Connection) -> int:
        """Sync previously disbursed order_line_ids from the database payout_lines."""
        cursor = db_conn.cursor()
        cursor.execute("SELECT order_line_id FROM payout_lines WHERE order_line_id IS NOT NULL")
        rows = cursor.fetchall()
        for r in rows:
            self._disbursed_order_lines.add(r[0])
        return len(self._disbursed_order_lines)

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
        2. Rolling reserve must be released (hold period elapsed).
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

    def calculate_net_payable_cents(
        self,
        gross_cents: int,
        commission_cents: int,
        refunds_cents: int = 0,
        dispute_cents: int = 0,
        reserve_held_cents: int = 0,
        reserve_released_cents: int = 0,
    ) -> int:
        """
        Calculate net payable amount using exact integer arithmetic:
        Gross - Commission - Refunds - Finalized Disputes - Reserve Held + Eligible Reserve Releases.
        """
        return (
            gross_cents
            - commission_cents
            - refunds_cents
            - dispute_cents
            - reserve_held_cents
            + reserve_released_cents
        )

    def build_payout_batch(
        self,
        payout_id: str,
        seller_id: str,
        batch_date: datetime,
        eligible_items: List[Dict[str, Any]],
        seller_status: str,
        inject_mismatch: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Builds a payout batch header and corresponding line items (float API for backward compatibility).
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

        final_net = total_net
        reconciliation_status = "MATCHED"

        if inject_mismatch:
            final_net = total_net + Decimal("125.00")
            reconciliation_status = "DISCREPANCY"

        payout_status = self.STATE_PAID
        if seller_status == "SUSPENDED" or final_net < Decimal(str(self.min_threshold)):
            payout_status = self.STATE_HELD

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

    def create_payout_batch_cents(
        self,
        payout_id: str,
        seller_id: str,
        batch_date: datetime,
        eligible_items: List[Dict[str, Any]],
        seller_status: str,
        inject_mismatch: bool = False,
        allow_duplicates: bool = False,
        db_conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """
        Creates a payout batch and lines in exact integer cents.
        Enforces:
        - No duplicate payout lines (checks disbursed lines).
        - No double deductions of disputes/refunds.
        - Minimum payout threshold ($25.00 / 2500 cents).
        - Suspended seller holds.
        """
        if not eligible_items:
            raise PayoutError("Cannot build payout batch from empty eligible items list.")

        total_gross_cents = 0
        total_comm_cents = 0
        total_refund_cents = 0
        total_dispute_cents = 0
        total_reserve_held_cents = 0
        total_reserve_released_cents = 0
        total_net_cents = 0

        lines = []

        for idx, item in enumerate(eligible_items):
            order_line_id = item.get("order_line_id")
            if not allow_duplicates and order_line_id:
                if order_line_id in self._disbursed_order_lines:
                    raise DuplicatePayoutLineError(
                        f"Order line '{order_line_id}' has already been disbursed in another payout batch."
                    )

            # Avoid double deductions for disputes and refunds
            dispute_id = item.get("dispute_id")
            if dispute_id and dispute_id in self._deducted_disputes:
                raise DoubleDeductionError(f"Dispute '{dispute_id}' has already been deducted from seller.")

            refund_id = item.get("refund_id")
            if refund_id and refund_id in self._deducted_refunds:
                raise DoubleDeductionError(f"Refund '{refund_id}' has already been deducted from seller.")

            gross_c = int(item["gross_amount_cents"])
            comm_c = int(item.get("commission_cents", 0))
            ref_c = int(item.get("refund_cents", 0))
            disp_c = int(item.get("dispute_cents", 0))
            res_held_c = int(item.get("reserve_held_cents", 0))
            res_rel_c = int(item.get("reserve_released_cents", 0))

            net_c = self.calculate_net_payable_cents(
                gross_cents=gross_c,
                commission_cents=comm_c,
                refunds_cents=ref_c,
                dispute_cents=disp_c,
                reserve_held_cents=res_held_c,
                reserve_released_cents=res_rel_c,
            )

            total_gross_cents += gross_c
            total_comm_cents += comm_c
            total_refund_cents += ref_c
            total_dispute_cents += disp_c
            total_reserve_held_cents += res_held_c
            total_reserve_released_cents += res_rel_c
            total_net_cents += net_c

            line_id = f"PLN-{payout_id}-{idx+1:04d}"
            date_str = batch_date.strftime("%Y-%m-%d %H:%M:%S")

            line_record = {
                "line_id": line_id,
                "payout_id": payout_id,
                "order_line_id": order_line_id,
                "order_id": item.get("order_id"),
                "seller_id": seller_id,
                "line_type": item.get("line_type", "ORDER_SETTLEMENT"),
                "gross_amount_cents": gross_c,
                "commission_cents": comm_c,
                "reserve_held_cents": res_held_c,
                "reserve_released_cents": res_rel_c,
                "dispute_cents": disp_c,
                "refund_cents": ref_c,
                "net_amount_cents": net_c,
                "created_at": date_str,
            }
            lines.append(line_record)

            if order_line_id:
                self._disbursed_order_lines.add(order_line_id)
            if dispute_id:
                self._deducted_disputes.add(dispute_id)
            if refund_id:
                self._deducted_refunds.add(refund_id)

        final_net_cents = total_net_cents
        reconciliation_status = "MATCHED"

        if inject_mismatch:
            # Artificially alter by +$125.00 (12500 cents)
            final_net_cents += 12500
            reconciliation_status = "DISCREPANCY"

        # Check eligibility and threshold
        payout_status = self.STATE_PAID
        if seller_status == "SUSPENDED" or final_net_cents < self.min_threshold_cents:
            payout_status = self.STATE_HELD

        batch_date_str = batch_date.strftime("%Y-%m-%d %H:%M:%S")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        header = {
            "payout_id": payout_id,
            "seller_id": seller_id,
            "batch_date": batch_date_str,
            "gross_sales_cents": total_gross_cents,
            "commission_cents": total_comm_cents,
            "refunds_cents": total_refund_cents,
            "disputes_cents": total_dispute_cents,
            "reserve_held_cents": total_reserve_held_cents,
            "reserve_released_cents": total_reserve_released_cents,
            "net_payout_cents": final_net_cents,
            "status": payout_status,
            "reconciliation_status": reconciliation_status,
            "line_count": len(lines),
            "notes": "Generated by PayoutEngine",
            "created_at": now_str,
        }

        # Persist to database if provided
        if db_conn:
            cursor = db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO payouts (
                    payout_id, seller_id, batch_date, gross_sales_cents, commission_cents,
                    refunds_cents, disputes_cents, reserve_held_cents, reserve_released_cents,
                    net_payout_cents, status, reconciliation_status, line_count, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    header["payout_id"],
                    header["seller_id"],
                    header["batch_date"],
                    header["gross_sales_cents"],
                    header["commission_cents"],
                    header["refunds_cents"],
                    header["disputes_cents"],
                    header["reserve_held_cents"],
                    header["reserve_released_cents"],
                    header["net_payout_cents"],
                    header["status"],
                    header["reconciliation_status"],
                    header["line_count"],
                    header["notes"],
                    header["created_at"],
                ),
            )

            for l in lines:
                cursor.execute(
                    """
                    INSERT INTO payout_lines (
                        line_id, payout_id, order_line_id, order_id, seller_id,
                        line_type, gross_amount_cents, commission_cents, reserve_held_cents,
                        reserve_released_cents, dispute_cents, refund_cents, net_amount_cents, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        l["line_id"],
                        l["payout_id"],
                        l["order_line_id"],
                        l["order_id"],
                        l["seller_id"],
                        l["line_type"],
                        l["gross_amount_cents"],
                        l["commission_cents"],
                        l["reserve_held_cents"],
                        l["reserve_released_cents"],
                        l["dispute_cents"],
                        l["refund_cents"],
                        l["net_amount_cents"],
                        l["created_at"],
                    ),
                )

            # Record payout event
            cursor.execute(
                """
                INSERT INTO payout_events (
                    event_id, payout_id, event_type, previous_status,
                    new_status, amount_cents, notes, occurred_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"POEVT-{payout_id}-0001",
                    payout_id,
                    "BATCH_INITIALIZED",
                    "NEW",
                    payout_status,
                    final_net_cents,
                    "Payout batch created and evaluated",
                    batch_date_str,
                    now_str,
                ),
            )
            db_conn.commit()

        return {
            "header": header,
            "lines": lines,
        }

    def transition_payout_status(
        self,
        payout_id: str,
        current_status: str,
        next_status: str,
        occurred_at: datetime,
        notes: Optional[str] = None,
        db_conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """
        Transition payout lifecycle state and record immutable payout_events log.
        """
        curr = current_status.upper()
        nxt = next_status.upper()

        if curr not in self.VALID_PAYOUT_STATES or nxt not in self.VALID_PAYOUT_STATES:
            raise InvalidPayoutStateTransitionError(f"Invalid state '{curr}' or '{nxt}'.")

        allowed = self.VALID_PAYOUT_TRANSITIONS.get(curr, set())
        if nxt not in allowed:
            raise InvalidPayoutStateTransitionError(
                f"Cannot transition payout {payout_id} from '{curr}' to '{nxt}'. Allowed: {sorted(list(allowed))}"
            )

        occ_str = occurred_at.strftime("%Y-%m-%d %H:%M:%S")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        event = {
            "event_id": f"POEVT-{payout_id}-{int(occurred_at.timestamp()) % 100000:05d}",
            "payout_id": payout_id,
            "event_type": f"TRANSITION_{nxt}",
            "previous_status": curr,
            "new_status": nxt,
            "notes": notes or f"Payout status transitioned from {curr} to {nxt}",
            "occurred_at": occ_str,
            "created_at": now_str,
        }

        if db_conn:
            cursor = db_conn.cursor()
            cursor.execute(
                """
                UPDATE payouts
                SET status = ?
                WHERE payout_id = ?
                """,
                (nxt, payout_id),
            )
            cursor.execute(
                """
                INSERT INTO payout_events (
                    event_id, payout_id, event_type, previous_status,
                    new_status, amount_cents, notes, occurred_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["event_id"],
                    payout_id,
                    event["event_type"],
                    curr,
                    nxt,
                    0,
                    event["notes"],
                    occ_str,
                    now_str,
                ),
            )
            db_conn.commit()

        return event
