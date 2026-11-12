"""Rolling Reserve Calculation and Balance Tracking Engine for SellerOps Intelligence Platform."""

import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Union
from src.config import PlatformConfig, load_config


class ReserveError(Exception):
    """Base exception for reserve engine errors."""
    pass


class PrematureReserveReleaseError(ReserveError):
    """Raised when reserve release is attempted prior to the expiration of the hold window."""
    pass


class SuspendedSellerReleaseError(ReserveError):
    """Raised when reserve release is attempted for a suspended seller."""
    pass


class ReserveNotFoundError(ReserveError):
    """Raised when a specified reserve entry cannot be found."""
    pass


class ReserveEngine:
    """
    Manages risk-based rolling reserve percentages, hold schedules, and release enforcement.
    Tracks reserve creation, balance, released reserve, and remaining reserve in exact integer cents.
    """

    def __init__(self, config: Optional[PlatformConfig] = None):
        self.config = config or load_config()
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._by_line_id: Dict[str, str] = {}

    def calculate_reserve(
        self,
        gross_amount: float,
        seller_tier: str,
        risk_score: float,
        delivery_date: datetime,
    ) -> Dict[str, Any]:
        """
        Calculate rolling reserve hold amount and release target date based on tier and risk score (float API).
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
            "reserve_rate_bps": int(round(effective_rate * 10000)),
            "reserve_amount": reserve_amount,
            "reserve_amount_cents": int(round(reserve_amount * 100)),
            "hold_days": hold_days,
            "release_date": release_date,
        }

    def calculate_reserve_cents(
        self,
        gross_amount_cents: int,
        seller_tier: str,
        risk_score: float,
        delivery_date: datetime,
    ) -> Dict[str, Any]:
        """
        Calculate rolling reserve hold amount and release target date in exact integer cents.
        """
        tier_cfg = self.config.seller_tiers.get(seller_tier)
        base_rate = tier_cfg.reserve_rate if tier_cfg else 0.10
        base_hold_days = tier_cfg.hold_days if tier_cfg else 14

        risk_surcharge = 0.05 if risk_score > 65.0 else 0.0
        extra_days = 7 if risk_score > 65.0 else 0

        effective_rate = min(1.00, round(base_rate + risk_surcharge, 4))
        rate_bps = int(round(effective_rate * 10000))
        hold_days = base_hold_days + extra_days

        reserve_cents = (gross_amount_cents * rate_bps) // 10000
        release_date = delivery_date + timedelta(days=hold_days)

        return {
            "reserve_rate": effective_rate,
            "reserve_rate_bps": rate_bps,
            "gross_amount_cents": gross_amount_cents,
            "reserve_amount_cents": reserve_cents,
            "hold_days": hold_days,
            "hold_start_date": delivery_date,
            "release_date": release_date,
        }

    def is_reserve_eligible_for_release(
        self,
        delivery_date: datetime,
        hold_days: int,
        as_of_date: datetime,
        seller_status: str,
    ) -> bool:
        """
        Reserve can be released if hold duration has elapsed and seller is not SUSPENDED.
        Strictly prevents release before hold_release_date.
        """
        if seller_status == "SUSPENDED":
            return False
        release_date = delivery_date + timedelta(days=hold_days)
        return as_of_date >= release_date

    def create_reserve_entry(
        self,
        order_line_id: str,
        seller_id: str,
        gross_amount_cents: int,
        seller_tier: str,
        risk_score: float,
        delivery_date: datetime,
        db_conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """
        Create and record a new reserve hold entry.
        """
        calc = self.calculate_reserve_cents(
            gross_amount_cents=gross_amount_cents,
            seller_tier=seller_tier,
            risk_score=risk_score,
            delivery_date=delivery_date,
        )

        reserve_idx = len(self._entries) + 1
        reserve_id = f"RSV-{reserve_idx:06d}"

        deliv_str = delivery_date.strftime("%Y-%m-%d %H:%M:%S")
        rel_str = calc["release_date"].strftime("%Y-%m-%d %H:%M:%S")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        entry = {
            "reserve_id": reserve_id,
            "order_line_id": order_line_id,
            "seller_id": seller_id,
            "reserve_rate": calc["reserve_rate"],
            "reserve_rate_bps": calc["reserve_rate_bps"],
            "reserve_amount_cents": calc["reserve_amount_cents"],
            "hold_days": calc["hold_days"],
            "hold_start_date": deliv_str,
            "hold_release_date": rel_str,
            "status": "HELD",
            "released_amount_cents": 0,
            "released_at": None,
            "created_at": now_str,
        }

        self._entries[reserve_id] = entry
        self._by_line_id[order_line_id] = reserve_id

        if db_conn:
            cursor = db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO reserve_ledger (
                    reserve_id, order_line_id, seller_id, reserve_rate,
                    reserve_amount_cents, hold_days, hold_start_date, hold_release_date,
                    status, released_amount_cents, released_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reserve_id,
                    order_line_id,
                    seller_id,
                    calc["reserve_rate"],
                    calc["reserve_amount_cents"],
                    calc["hold_days"],
                    deliv_str,
                    rel_str,
                    "HELD",
                    0,
                    None,
                    now_str,
                ),
            )
            db_conn.commit()

        return entry

    def release_reserve(
        self,
        reserve_id_or_line_id: str,
        as_of_date: datetime,
        seller_status: str,
        db_conn: Optional[sqlite3.Connection] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Release a held reserve after validating that hold period has expired and seller is active.
        Throws PrematureReserveReleaseError if called before release date.
        Throws SuspendedSellerReleaseError if seller is suspended.
        """
        entry = self._entries.get(reserve_id_or_line_id)
        if not entry:
            rid = self._by_line_id.get(reserve_id_or_line_id)
            if rid:
                entry = self._entries.get(rid)

        # Check DB if not in memory
        if not entry and db_conn:
            cursor = db_conn.cursor()
            cursor.execute(
                """
                SELECT reserve_id, order_line_id, seller_id, reserve_rate,
                       reserve_amount_cents, hold_days, hold_start_date, hold_release_date,
                       status, released_amount_cents, released_at, created_at
                FROM reserve_ledger
                WHERE reserve_id = ? OR order_line_id = ?
                """,
                (reserve_id_or_line_id, reserve_id_or_line_id),
            )
            row = cursor.fetchone()
            if row:
                cols = [col[0] for col in cursor.description]
                entry = dict(zip(cols, row))
                self._entries[entry["reserve_id"]] = entry
                self._by_line_id[entry["order_line_id"]] = entry["reserve_id"]

        if not entry:
            raise ReserveNotFoundError(f"Reserve entry not found for identifier '{reserve_id_or_line_id}'")

        if entry["status"] == "RELEASED":
            return entry

        if seller_status == "SUSPENDED":
            raise SuspendedSellerReleaseError(
                f"Cannot release reserve for suspended seller {entry['seller_id']}."
            )

        # Parse hold release date
        rel_dt_str = entry["hold_release_date"]
        rel_dt = (
            datetime.strptime(rel_dt_str, "%Y-%m-%d %H:%M:%S")
            if " " in rel_dt_str
            else datetime.fromisoformat(rel_dt_str)
        )

        if as_of_date < rel_dt and not force:
            raise PrematureReserveReleaseError(
                f"Reserve hold period has not expired. Release target: {rel_dt_str}, current: {as_of_date.isoformat()}"
            )

        # Mark released
        entry["status"] = "RELEASED"
        entry["released_amount_cents"] = entry["reserve_amount_cents"]
        entry["released_at"] = as_of_date.strftime("%Y-%m-%d %H:%M:%S")

        if db_conn:
            cursor = db_conn.cursor()
            cursor.execute(
                """
                UPDATE reserve_ledger
                SET status = 'RELEASED',
                    released_amount_cents = reserve_amount_cents,
                    released_at = ?
                WHERE reserve_id = ?
                """,
                (entry["released_at"], entry["reserve_id"]),
            )
            db_conn.commit()

        return entry

    def get_reserve_balance(
        self,
        seller_id: str,
        db_conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """
        Track reserve creation, balance, released reserve, and remaining reserve for a seller.
        """
        if db_conn:
            cursor = db_conn.cursor()
            cursor.execute(
                """
                SELECT
                    COALESCE(SUM(reserve_amount_cents), 0) AS total_held,
                    COALESCE(SUM(released_amount_cents), 0) AS total_released
                FROM reserve_ledger
                WHERE seller_id = ?
                """,
                (seller_id,),
            )
            row = cursor.fetchone()
            total_held = row[0]
            total_released = row[1]
        else:
            seller_entries = [e for e in self._entries.values() if e["seller_id"] == seller_id]
            total_held = sum(e["reserve_amount_cents"] for e in seller_entries)
            total_released = sum(e["released_amount_cents"] for e in seller_entries)

        remaining_reserve_cents = total_held - total_released

        return {
            "seller_id": seller_id,
            "total_reserve_held_cents": total_held,
            "total_reserve_released_cents": total_released,
            "remaining_reserve_cents": remaining_reserve_cents,
            "total_reserve_held_dollars": round(total_held / 100.0, 2),
            "total_reserve_released_dollars": round(total_released / 100.0, 2),
            "remaining_reserve_dollars": round(remaining_reserve_cents / 100.0, 2),
        }
