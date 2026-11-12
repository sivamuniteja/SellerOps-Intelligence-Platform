"""Commission Calculation and Immutable Ledger Engine for SellerOps Intelligence Platform."""

import sqlite3
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Union, Set
from src.config import PlatformConfig, load_config


class CommissionError(Exception):
    """Base exception for commission engine errors."""
    pass


class DuplicateCommissionError(CommissionError):
    """Raised when an order line commission calculation is attempted more than once."""
    pass


class RuleNotFoundError(CommissionError):
    """Raised when no applicable commission rule matches category, tier, and transaction date."""
    pass


class CommissionEngine:
    """
    Computes marketplace commissions and transaction fees by category, seller tier, and effective dates.
    Records calculations into an immutable ledger and prevents duplicate fee applications.
    """

    def __init__(self, config: Optional[PlatformConfig] = None, rules: Optional[List[Dict[str, Any]]] = None):
        self.config = config or load_config()
        self.category_rates: Dict[str, float] = {
            cat.name: cat.base_commission_rate for cat in self.config.categories
        }
        self.category_mins: Dict[str, float] = {
            cat.name: cat.min_commission for cat in self.config.categories
        }
        self.fixed_fee = float(self.config.payout_rules.get("fixed_transaction_fee", 0.30))
        self.fixed_fee_cents = int(round(self.fixed_fee * 100))

        # Dynamic effective-dated rules
        self.rules: List[Dict[str, Any]] = rules or []

        # Internal ledger and deduplication registry
        self._ledger_entries: List[Dict[str, Any]] = []
        self._recorded_order_lines: Set[str] = set()

    def load_rules_from_db(self, db_conn: sqlite3.Connection) -> List[Dict[str, Any]]:
        """Load effective-dated commission rules from the database."""
        cursor = db_conn.cursor()
        cursor.execute(
            """
            SELECT rule_id, category, tier, base_rate, discount_rate,
                   fixed_fee_cents, min_commission_cents, effective_from, effective_to
            FROM commission_rules
            ORDER BY effective_from DESC
            """
        )
        columns = [col[0] for col in cursor.description]
        self.rules = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return self.rules

    def sync_processed_lines_from_db(self, db_conn: sqlite3.Connection) -> int:
        """Sync previously processed order_line_ids from the database commission_ledger."""
        cursor = db_conn.cursor()
        cursor.execute("SELECT order_line_id FROM commission_ledger")
        rows = cursor.fetchall()
        for r in rows:
            self._recorded_order_lines.add(r[0])
        return len(self._recorded_order_lines)

    def find_applicable_rule(
        self,
        category: str,
        seller_tier: str,
        transaction_date: Optional[Union[str, datetime, date]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Finds the matching commission rule based on product category, seller tier, and effective dates.
        """
        if not self.rules:
            return None

        # Format transaction_date to 'YYYY-MM-DD'
        tx_str = "9999-12-31"
        if transaction_date:
            if isinstance(transaction_date, (datetime, date)):
                tx_str = transaction_date.strftime("%Y-%m-%d")
            else:
                tx_str = str(transaction_date)[:10]

        for rule in self.rules:
            # Check category & tier match
            rule_cat = rule.get("category")
            rule_tier = rule.get("tier")
            if rule_cat and rule_cat != category:
                continue
            if rule_tier and rule_tier != seller_tier:
                continue

            # Check effective dates
            eff_from = str(rule.get("effective_from", "1970-01-01"))[:10]
            eff_to = str(rule.get("effective_to") or "9999-12-31")[:10]

            if eff_from <= tx_str <= eff_to:
                return rule

        return None

    def calculate_commission(
        self,
        gross_amount: float,
        category: str,
        seller_tier: str,
        transaction_date: Optional[Union[str, datetime, date]] = None,
        rule: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Calculate commission rate and amount for an order in float currency.
        Supports effective-dated rules with fallback to config category/tier rates.
        Returns dict with effective_rate, variable_commission, fixed_fee, total_commission.
        """
        applicable_rule = rule or self.find_applicable_rule(category, seller_tier, transaction_date)

        if applicable_rule:
            base_rate = float(applicable_rule.get("base_rate", 0.12))
            discount = float(applicable_rule.get("discount_rate", 0.0))
            fixed_fee = float(applicable_rule.get("fixed_fee_cents", self.fixed_fee_cents)) / 100.0
            min_comm = float(applicable_rule.get("min_commission_cents", 50)) / 100.0
            rule_id = applicable_rule.get("rule_id")
        else:
            base_rate = self.category_rates.get(category, 0.12)
            tier_config = self.config.seller_tiers.get(seller_tier)
            discount = tier_config.commission_discount if tier_config else 0.0
            fixed_fee = self.fixed_fee
            min_comm = self.category_mins.get(category, 0.50)
            rule_id = None

        effective_rate = max(0.01, round(base_rate - discount, 4))

        # Exact Decimal calculation to eliminate binary floating point imprecision
        gross_dec = Decimal(str(round(gross_amount, 2)))
        rate_dec = Decimal(str(effective_rate))
        raw_variable = float((gross_dec * rate_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

        variable_commission = max(raw_variable, min_comm)
        total_commission = round(variable_commission + fixed_fee, 2)

        return {
            "rule_id": rule_id,
            "category": category,
            "seller_tier": seller_tier,
            "effective_rate": effective_rate,
            "rate_basis_points": int(round(effective_rate * 10000)),
            "variable_commission": variable_commission,
            "fixed_fee": fixed_fee,
            "total_commission": total_commission,
            "variable_commission_cents": int(round(variable_commission * 100)),
            "fixed_fee_cents": int(round(fixed_fee * 100)),
            "total_commission_cents": int(round(total_commission * 100)),
        }

    def calculate_commission_cents(
        self,
        gross_amount_cents: int,
        category: str,
        seller_tier: str,
        transaction_date: Optional[Union[str, datetime, date]] = None,
        rule: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Calculate exact integer cents commission.
        """
        applicable_rule = rule or self.find_applicable_rule(category, seller_tier, transaction_date)

        if applicable_rule:
            base_rate = float(applicable_rule.get("base_rate", 0.12))
            discount = float(applicable_rule.get("discount_rate", 0.0))
            fixed_fee_cents = int(applicable_rule.get("fixed_fee_cents", self.fixed_fee_cents))
            min_cents = int(applicable_rule.get("min_commission_cents", 50))
            rule_id = applicable_rule.get("rule_id")
        else:
            base_rate = self.category_rates.get(category, 0.12)
            tier_config = self.config.seller_tiers.get(seller_tier)
            discount = tier_config.commission_discount if tier_config else 0.0
            fixed_fee_cents = self.fixed_fee_cents
            min_cents = int(round(self.category_mins.get(category, 0.50) * 100))
            rule_id = None

        effective_rate = max(0.01, round(base_rate - discount, 4))
        rate_bps = int(round(effective_rate * 10000))

        # Integer cents math
        raw_variable_cents = (gross_amount_cents * rate_bps) // 10000
        variable_cents = max(raw_variable_cents, min_cents)
        total_cents = variable_cents + fixed_fee_cents

        return {
            "rule_id": rule_id,
            "category": category,
            "seller_tier": seller_tier,
            "effective_rate": effective_rate,
            "rate_basis_points": rate_bps,
            "gross_amount_cents": gross_amount_cents,
            "variable_commission_cents": variable_cents,
            "fixed_fee_cents": fixed_fee_cents,
            "total_commission_cents": total_cents,
        }

    def record_commission_ledger_entry(
        self,
        order_line_id: str,
        order_id: str,
        seller_id: str,
        gross_amount_cents: int,
        category: str,
        seller_tier: str,
        transaction_date: Union[str, datetime, date],
        db_conn: Optional[sqlite3.Connection] = None,
        allow_duplicate: bool = False,
    ) -> Dict[str, Any]:
        """
        Record commission calculation in an immutable ledger and prevent duplicate applications.
        If allow_duplicate is False, raises DuplicateCommissionError when order_line_id was already recorded.
        """
        if not allow_duplicate:
            if order_line_id in self._recorded_order_lines:
                raise DuplicateCommissionError(
                    f"Commission already recorded for order line '{order_line_id}'. Duplicate fee application prevented."
                )

            # Check database table if connection is provided
            if db_conn:
                cursor = db_conn.cursor()
                cursor.execute("SELECT ledger_id FROM commission_ledger WHERE order_line_id = ?", (order_line_id,))
                existing = cursor.fetchone()
                if existing:
                    self._recorded_order_lines.add(order_line_id)
                    raise DuplicateCommissionError(
                        f"Commission already recorded in database for order line '{order_line_id}' (ledger_id: {existing[0]})."
                    )

        calc = self.calculate_commission_cents(
            gross_amount_cents=gross_amount_cents,
            category=category,
            seller_tier=seller_tier,
            transaction_date=transaction_date,
        )

        ledger_idx = len(self._ledger_entries) + 1
        ledger_id = f"CML-{ledger_idx:06d}"

        tx_str = (
            transaction_date.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(transaction_date, (datetime, date))
            else str(transaction_date)
        )
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        entry = {
            "ledger_id": ledger_id,
            "order_line_id": order_line_id,
            "order_id": order_id,
            "seller_id": seller_id,
            "rule_id": calc["rule_id"],
            "gross_amount_cents": gross_amount_cents,
            "effective_rate": calc["effective_rate"],
            "variable_commission_cents": calc["variable_commission_cents"],
            "fixed_fee_cents": calc["fixed_fee_cents"],
            "total_commission_cents": calc["total_commission_cents"],
            "calculation_date": tx_str,
            "created_at": now_str,
        }

        # Immutable append
        self._ledger_entries.append(entry)
        self._recorded_order_lines.add(order_line_id)

        # Write to database if connection provided
        if db_conn:
            cursor = db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO commission_ledger (
                    ledger_id, order_line_id, order_id, seller_id, rule_id,
                    gross_amount_cents, effective_rate, variable_commission_cents,
                    fixed_fee_cents, total_commission_cents, calculation_date, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ledger_id,
                    order_line_id,
                    order_id,
                    seller_id,
                    calc["rule_id"],
                    gross_amount_cents,
                    calc["effective_rate"],
                    calc["variable_commission_cents"],
                    calc["fixed_fee_cents"],
                    calc["total_commission_cents"],
                    tx_str,
                    now_str,
                ),
            )
            db_conn.commit()

        return entry

    def get_ledger_entries(
        self,
        seller_id: Optional[str] = None,
        order_line_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return ledger entries filtered by seller_id or order_line_id."""
        entries = self._ledger_entries
        if seller_id:
            entries = [e for e in entries if e["seller_id"] == seller_id]
        if order_line_id:
            entries = [e for e in entries if e["order_line_id"] == order_line_id]
        return list(entries)
