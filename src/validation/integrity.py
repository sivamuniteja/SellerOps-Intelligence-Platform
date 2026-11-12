"""Database Referential, Schema, and Enum Integrity Validator."""

import re
from typing import Dict, List, Any, Optional
from src.database.connection import DatabaseManager


class IntegrityValidator:
    """
    Audits database tables for:
    - Primary-key uniqueness
    - Foreign-key referential integrity
    - Canonical ID formats (Regex)
    - Required non-null constraints
    - Enum value validity
    - Duplicate record detection
    """

    ID_PATTERNS = {
        "sellers": ("seller_id", r"^SELL-\d{6}$"),
        "customers": ("customer_id", r"^CUST-\d{6}$"),
        "listings": ("listing_id", r"^LIST-SELL-\d{6}-\d{6}$"),
        "orders": ("order_id", r"^ORD-\d{4}-\d{6}$"),
        "order_lines": ("order_line_id", r"^ORDLN-\d{4}-\d{6}-\d{2}$"),
        "fulfillments": ("fulfillment_id", r"^FUL-ORDLN-\d{4}-\d{6}-\d{2}(-\d+)?$"),
        "customer_reviews": ("review_id", r"^REV-\d{4}-\d{6}$"),
        "disputes": ("dispute_id", r"^DSP-\d{4}-\d{6}$"),
        "commission_ledger": ("entry_id", r"^CML-\d{6}$"),
        "reserve_ledger": ("entry_id", r"^RSV-\d{6}$"),
        "payouts": ("payout_id", r"^PAYOUT-(PREM-)?(\d{4}-)?\d{4,6}$"),
        "payout_lines": ("line_id", r"^PLN-.*$"),
    }

    ENUM_CONSTRAINTS = {
        "sellers": {
            "tier": {"STANDARD", "PREFERRED", "ENTERPRISE", "PROBATION", "SUSPENDED"},
            "status": {"ACTIVE", "PROBATION", "SUSPENDED", "UNDER_REVIEW"},
        },
        "listings": {
            "status": {"ACTIVE", "OUT_OF_STOCK", "SUSPENDED", "ARCHIVED"},
        },
        "orders": {
            "order_status": {"PLACED", "CONFIRMED", "PARTIALLY_SHIPPED", "SHIPPED", "DELIVERED", "CANCELLED", "RETURNED"},
        },
        "order_lines": {
            "line_status": {"PLACED", "CONFIRMED", "PARTIALLY_SHIPPED", "SHIPPED", "DELIVERED", "CANCELLED", "RETURNED"},
        },
        "fulfillments": {
            "sla_status": {"ON_TIME", "LATE", "IN_TRANSIT", "CANCELLED"},
        },
        "disputes": {
            "status": {"OPEN", "UNDER_REVIEW", "RESOLVED_BUYER_FAVOR", "RESOLVED_SELLER_FAVOR", "CHARGEBACK_LOST", "CHARGEBACK_WON"},
        },
        "reserve_ledger": {
            "status": {"HELD", "RELEASED", "FORFEITED"},
        },
        "payouts": {
            "payout_status": {"SCHEDULED", "PROCESSING", "PAID", "HELD", "FAILED"},
            "reconciliation_status": {"MATCHED", "DISCREPANCY", "PENDING"},
        },
    }

    def __init__(self, db: DatabaseManager):
        self.db = db

    def check_all(self) -> Dict[str, Any]:
        """Run all referential integrity, schema format, enum, and duplicate checks."""
        fk_check = self.check_foreign_keys()
        null_check = self.check_null_constraints()
        pk_check = self.check_primary_keys()
        id_check = self.check_id_formats()
        enum_check = self.check_enum_constraints()
        dup_check = self.check_duplicate_records()

        total_issues = (
            len(fk_check.get("violations", []))
            + len(null_check.get("violations", []))
            + len(pk_check.get("violations", []))
            + len(id_check.get("violations", []))
            + len(enum_check.get("violations", []))
            + len(dup_check.get("violations", []))
        )

        return {
            "passed": total_issues == 0,
            "total_issues": total_issues,
            "foreign_keys": fk_check,
            "primary_keys": pk_check,
            "id_formats": id_check,
            "null_constraints": null_check,
            "enum_validation": enum_check,
            "duplicate_records": dup_check,
        }

    def check_foreign_keys(self) -> Dict[str, Any]:
        """Audit foreign key references in SQLite."""
        with self.db.session() as conn:
            rows = conn.execute("PRAGMA foreign_key_check;").fetchall()
            violations = [
                {
                    "table": r[0],
                    "rowid": r[1],
                    "parent_table": r[2],
                    "fkid": r[3],
                }
                for r in rows
            ]
            return {
                "valid": len(violations) == 0,
                "violations_count": len(violations),
                "violations": violations,
            }

    def check_primary_keys(self) -> Dict[str, Any]:
        """Verify primary key uniqueness across all entity tables."""
        tables_pks = {
            "sellers": "seller_id",
            "customers": "customer_id",
            "listings": "listing_id",
            "orders": "order_id",
            "order_lines": "order_line_id",
            "fulfillments": "fulfillment_id",
            "customer_reviews": "review_id",
            "disputes": "dispute_id",
            "commission_ledger": "entry_id",
            "reserve_ledger": "entry_id",
            "payouts": "payout_id",
            "payout_lines": "line_id",
        }

        violations = []
        with self.db.session() as conn:
            for table, pk in tables_pks.items():
                if not self.db.table_exists(table):
                    continue
                q = f"""
                    SELECT {pk}, COUNT(*) as c
                    FROM {table}
                    GROUP BY {pk}
                    HAVING c > 1;
                """
                duplicates = conn.execute(q).fetchall()
                if duplicates:
                    violations.append({
                        "table": table,
                        "primary_key": pk,
                        "duplicate_count": len(duplicates),
                    })

        return {
            "valid": len(violations) == 0,
            "violations_count": len(violations),
            "violations": violations,
        }

    def check_id_formats(self) -> Dict[str, Any]:
        """Validate that all IDs conform to canonical regex patterns."""
        violations = []
        with self.db.session() as conn:
            for table, (col, pattern) in self.ID_PATTERNS.items():
                if not self.db.table_exists(table):
                    continue
                cursor = conn.execute(f"SELECT DISTINCT {col} FROM {table};")
                rows = cursor.fetchall()
                prog = re.compile(pattern)
                invalid_ids = [r[0] for r in rows if not prog.match(str(r[0]))]
                if invalid_ids:
                    violations.append({
                        "table": table,
                        "column": col,
                        "pattern": pattern,
                        "invalid_count": len(invalid_ids),
                        "sample_invalid": invalid_ids[:5],
                    })

        return {
            "valid": len(violations) == 0,
            "violations_count": len(violations),
            "violations": violations,
        }

    def check_null_constraints(self) -> Dict[str, Any]:
        """Check for unexpected NULL values in non-nullable columns."""
        checks = [
            ("sellers", "seller_id"),
            ("sellers", "name"),
            ("sellers", "tier"),
            ("sellers", "status"),
            ("customers", "customer_id"),
            ("customers", "email"),
            ("listings", "listing_id"),
            ("listings", "price_cents"),
            ("orders", "order_id"),
            ("orders", "total_amount_cents"),
            ("orders", "order_status"),
            ("order_lines", "order_line_id"),
            ("order_lines", "gross_amount_cents"),
            ("fulfillments", "fulfillment_id"),
            ("disputes", "dispute_id"),
            ("disputes", "disputed_amount_cents"),
            ("payouts", "payout_id"),
            ("payouts", "net_payout_amount_cents"),
        ]
        violations = []
        with self.db.session() as conn:
            for table, col in checks:
                if not self.db.table_exists(table):
                    continue
                q = f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL;"
                null_count = conn.execute(q).fetchone()[0]
                if null_count > 0:
                    violations.append({"table": table, "column": col, "null_count": null_count})

        return {
            "valid": len(violations) == 0,
            "violations_count": len(violations),
            "violations": violations,
        }

    def check_enum_constraints(self) -> Dict[str, Any]:
        """Validate that enum columns contain only allowed values."""
        violations = []
        with self.db.session() as conn:
            for table, col_map in self.ENUM_CONSTRAINTS.items():
                if not self.db.table_exists(table):
                    continue
                for col, allowed in col_map.items():
                    cursor = conn.execute(f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL;")
                    found_vals = {r[0] for r in cursor.fetchall()}
                    illegal = found_vals - allowed
                    if illegal:
                        violations.append({
                            "table": table,
                            "column": col,
                            "illegal_values": list(illegal),
                            "allowed_values": list(allowed),
                        })

        return {
            "valid": len(violations) == 0,
            "violations_count": len(violations),
            "violations": violations,
        }

    def check_duplicate_records(self) -> Dict[str, Any]:
        """Detect duplicate business entities and duplicate line assignments."""
        violations = []
        with self.db.session() as conn:
            # 1. Duplicate order_line_id in payout_lines (unless intentional anomaly)
            if self.db.table_exists("payout_lines"):
                dup_po = conn.execute(
                    """
                    SELECT order_line_id, COUNT(*) as c
                    FROM payout_lines
                    WHERE order_line_id IS NOT NULL
                    GROUP BY order_line_id
                    HAVING c > 1;
                    """
                ).fetchall()
                if dup_po:
                    violations.append({
                        "check": "DUPLICATE_PAYOUT_LINES",
                        "count": len(dup_po),
                        "description": f"{len(dup_po)} order lines disbursed in multiple payout lines",
                    })

            # 2. Duplicate order_line_id in commission_ledger
            if self.db.table_exists("commission_ledger"):
                dup_comm = conn.execute(
                    """
                    SELECT order_line_id, COUNT(*) as c
                    FROM commission_ledger
                    GROUP BY order_line_id
                    HAVING c > 1;
                    """
                ).fetchall()
                if dup_comm:
                    violations.append({
                        "check": "DUPLICATE_COMMISSION_LEDGER_LINES",
                        "count": len(dup_comm),
                        "description": f"{len(dup_comm)} order lines have duplicate commission ledger entries",
                    })

        return {
            "valid": len(violations) == 0,
            "violations_count": len(violations),
            "violations": violations,
        }
