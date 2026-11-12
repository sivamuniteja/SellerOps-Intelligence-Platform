"""SQL Dump and Seed Data Exporter for SellerOps Database.

Generates standard, executable SQL seed data scripts adhering to relational dependency order,
with foreign key enforcement, exact integer cents preservation, and re-import verification.
"""

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from src.database.connection import DatabaseManager
from src.exports.csv_export import ORDERED_TABLES, CsvExporter


def sql_escape_value(val) -> str:
    """Format Python values as standard SQL literals."""
    if val is None:
        return "NULL"
    if isinstance(val, (int, float)):
        return str(val)
    # String escaping: replace ' with ''
    escaped = str(val).replace("'", "''")
    return f"'{escaped}'"


class SqlExporter:
    """Generates standard SQL seed scripts for cross-database migrations and restoration."""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._query_builder = CsvExporter(db)

    def export_seed_data(
        self,
        output_path: Union[str, Path] = "data/exports/sql/seed_data.sql",
        seller_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_schema: bool = True,
        exclude_ground_truth: bool = True,
        batch_size: int = 500,
    ) -> Dict:
        """Export all relational data as an executable SQL seed script in strict dependency order."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        tables = list(ORDERED_TABLES)
        if not exclude_ground_truth:
            tables.append("ground_truth")

        hasher = hashlib.sha256()
        total_rows = 0
        table_row_counts: Dict[str, int] = {}

        schema_path = Path(__file__).parent.parent / "models" / "schema.sql"

        with open(path, "w", encoding="utf-8") as f:
            f.write("-- =====================================================================\n")
            f.write("-- SellerOps Intelligence Platform - Master SQL Seed Script\n")
            f.write(f"-- Generated At: {datetime.now().isoformat()}\n")
            if seller_id:
                f.write(f"-- Filtered by Seller ID: {seller_id}\n")
            if start_date or end_date:
                f.write(f"-- Filtered by Date Range: {start_date or 'epoch'} to {end_date or 'now'}\n")
            f.write("-- =====================================================================\n\n")

            f.write("PRAGMA foreign_keys = OFF;\n\n")

            # 1. Include Schema if requested
            if include_schema and schema_path.exists():
                f.write("-- ---------------------------------------------------------------------\n")
                f.write("-- Relational Schema DDL\n")
                f.write("-- ---------------------------------------------------------------------\n")
                with open(schema_path, "r", encoding="utf-8") as sf:
                    f.write(sf.read())
                f.write("\n\n")

            f.write("BEGIN TRANSACTION;\n\n")

            # 2. Iterate tables in strict foreign-key dependency order
            with self.db.session() as conn:
                for table_name in tables:
                    if not self.db.table_exists(table_name):
                        continue

                    query, params = self._query_builder.build_filter_query(
                        table_name, seller_id=seller_id, start_date=start_date, end_date=end_date
                    )
                    cursor = conn.cursor()
                    cursor.execute(query, params)
                    col_names = [d[0] for d in cursor.description]
                    col_list_str = ", ".join(f'"{c}"' for c in col_names)

                    t_rows = 0
                    f.write(f"-- ---------------------------------------------------------------------\n")
                    f.write(f"-- Table Data: {table_name}\n")
                    f.write(f"-- ---------------------------------------------------------------------\n")

                    while True:
                        rows = cursor.fetchmany(batch_size)
                        if not rows:
                            break

                        values_clauses = []
                        for r in rows:
                            val_str = ", ".join(sql_escape_value(v) for v in r)
                            values_clauses.append(f"({val_str})")

                        f.write(f'INSERT INTO "{table_name}" ({col_list_str}) VALUES\n  ')
                        f.write(",\n  ".join(values_clauses))
                        f.write(";\n\n")

                        t_rows += len(rows)

                    table_row_counts[table_name] = t_rows
                    total_rows += t_rows

            f.write("COMMIT;\n\n")
            f.write("PRAGMA foreign_keys = ON;\n")
            f.write("-- Integrity assertion on restore\n")
            f.write("PRAGMA foreign_key_check;\n")

        # Compute SHA-256 and size
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)

        file_size = path.stat().st_size
        sha256_hash = hasher.hexdigest()

        return {
            "path": str(path),
            "total_rows": total_rows,
            "table_row_counts": table_row_counts,
            "file_size_bytes": file_size,
            "sha256": sha256_hash,
            "status": "SUCCESS",
        }

    def export_ground_truth_sql(
        self,
        output_path: Union[str, Path] = "data/exports/ground_truth/ground_truth.sql",
        batch_size: int = 250,
    ) -> Dict:
        """Export negative scenario ground truth records to an isolated SQL seed script."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        hasher = hashlib.sha256()
        t_rows = 0

        with open(path, "w", encoding="utf-8") as f:
            f.write("-- =====================================================================\n")
            f.write("-- SellerOps Platform - Isolated Ground Truth Anomalies Seed Script\n")
            f.write(f"-- Generated At: {datetime.now().isoformat()}\n")
            f.write("-- =====================================================================\n\n")
            f.write("BEGIN TRANSACTION;\n\n")

            if self.db.table_exists("ground_truth"):
                with self.db.session() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM ground_truth ORDER BY anomaly_id ASC;")
                    col_names = [d[0] for d in cursor.description]
                    col_list_str = ", ".join(f'"{c}"' for c in col_names)

                    while True:
                        rows = cursor.fetchmany(batch_size)
                        if not rows:
                            break

                        values_clauses = []
                        for r in rows:
                            val_str = ", ".join(sql_escape_value(v) for v in r)
                            values_clauses.append(f"({val_str})")

                        f.write(f'INSERT INTO "ground_truth" ({col_list_str}) VALUES\n  ')
                        f.write(",\n  ".join(values_clauses))
                        f.write(";\n\n")

                        t_rows += len(rows)

            f.write("COMMIT;\n")

        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)

        file_size = path.stat().st_size
        sha256_hash = hasher.hexdigest()

        return {
            "path": str(path),
            "total_rows": t_rows,
            "file_size_bytes": file_size,
            "sha256": sha256_hash,
            "status": "SUCCESS",
        }

    def verify_reimport_sql(
        self,
        sql_path: Union[str, Path],
        target_db_path: Union[str, Path],
        seller_id: Optional[str] = None,
    ) -> Dict:
        """Execute the exported SQL script against a clean database and verify integrity."""
        sql_file = Path(sql_path)
        target_db = Path(target_db_path)

        if target_db.exists():
            target_db.unlink()
        target_db.parent.mkdir(parents=True, exist_ok=True)

        # 1. Execute SQL script
        conn = sqlite3.connect(str(target_db))
        with open(sql_file, "r", encoding="utf-8") as f:
            script_text = f.read()

        conn.executescript(script_text)

        # 2. Check foreign keys
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.execute("PRAGMA foreign_key_check;")
        fk_violations = cursor.fetchall()

        # 3. Check row counts
        tables_res = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
        ).fetchall()
        table_counts = {}
        total_reimported = 0
        for (t,) in tables_res:
            c = conn.execute(f"SELECT COUNT(*) FROM {t};").fetchone()[0]
            table_counts[t] = c
            total_reimported += c

        # 4. Check financial sums integrity
        with self.db.session() as src_conn:
            if seller_id:
                orig_order_gmv = src_conn.execute(
                    "SELECT SUM(total_amount_cents) FROM orders WHERE order_id IN "
                    "(SELECT DISTINCT order_id FROM order_lines WHERE seller_id = ?);",
                    (seller_id,)
                ).fetchone()[0] or 0
                orig_payout_net = src_conn.execute(
                    "SELECT SUM(net_payout_amount_cents) FROM payouts WHERE seller_id = ?;",
                    (seller_id,)
                ).fetchone()[0] or 0
            else:
                orig_order_gmv = src_conn.execute("SELECT SUM(total_amount_cents) FROM orders;").fetchone()[0] or 0
                orig_payout_net = src_conn.execute("SELECT SUM(net_payout_amount_cents) FROM payouts;").fetchone()[0] or 0

        new_order_gmv = conn.execute("SELECT SUM(total_amount_cents) FROM orders;").fetchone()[0] or 0
        gmv_matched = (orig_order_gmv == new_order_gmv)

        new_payout_net = conn.execute("SELECT SUM(net_payout_amount_cents) FROM payouts;").fetchone()[0] or 0
        payout_matched = (orig_payout_net == new_payout_net)

        conn.close()

        is_valid = (len(fk_violations) == 0 and gmv_matched and payout_matched)

        return {
            "valid": is_valid,
            "target_db_path": str(target_db),
            "foreign_key_violations_count": len(fk_violations),
            "foreign_key_violations": fk_violations,
            "total_reimported_rows": total_reimported,
            "table_counts": table_counts,
            "financial_accuracy": {
                "gmv_matched": gmv_matched,
                "orig_gmv_cents": orig_order_gmv,
                "reimported_gmv_cents": new_order_gmv,
                "payout_matched": payout_matched,
                "orig_payout_net_cents": orig_payout_net,
                "reimported_payout_net_cents": new_payout_net,
            },
        }
