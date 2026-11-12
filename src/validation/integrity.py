"""Database Referential and Schema Integrity Validator."""

from typing import Dict, List, Any
import pandas as pd
from src.database.connection import DatabaseManager


class IntegrityValidator:
    """Audits database tables for missing primary keys, orphan foreign keys, and null violations."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def check_all(self) -> Dict[str, Any]:
        """Run all referential integrity and format checks."""
        fk_check = self.check_foreign_keys()
        null_check = self.check_null_constraints()
        pk_check = self.check_primary_keys()

        total_issues = (
            len(fk_check.get("violations", []))
            + len(null_check.get("violations", []))
            + len(pk_check.get("violations", []))
        )

        return {
            "passed": total_issues == 0,
            "total_issues": total_issues,
            "foreign_keys": fk_check,
            "primary_keys": pk_check,
            "null_constraints": null_check,
        }

    def check_foreign_keys(self) -> Dict[str, Any]:
        """Audit foreign key references in SQLite."""
        with self.db.session() as conn:
            # PRAGMA foreign_key_check returns [table, rowid, parent, fkid]
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
        """Verify primary key uniqueness across tables."""
        tables_pks = {
            "sellers": "seller_id",
            "customers": "customer_id",
            "listings": "listing_id",
            "orders": "order_id",
            "fulfillments": "fulfillment_id",
            "reviews": "review_id",
            "disputes": "dispute_id",
            "order_settlements": "settlement_id",
            "payout_batches": "payout_id",
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
            "violations": violations,
        }

    def check_null_constraints(self) -> Dict[str, Any]:
        """Check for unexpected NULL values in non-nullable columns."""
        checks = [
            ("sellers", "name"),
            ("sellers", "tier"),
            ("customers", "email"),
            ("listings", "price"),
            ("orders", "gross_amount"),
            ("orders", "order_status"),
            ("disputes", "disputed_amount"),
            ("payout_batches", "net_payout_amount"),
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
            "violations": violations,
        }
