"""CSV Data and Audit Report Exporter.

Provides streaming, memory-efficient CSV export for all SellerOps relational entities
supporting full-dataset exports, seller filtering, date filtering, and SHA-256 checksums.
"""

import csv
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from src.database.connection import DatabaseManager


ORDERED_TABLES: List[str] = [
    "schema_migrations",
    "sellers",
    "seller_status_events",
    "customers",
    "listings",
    "commission_rules",
    "orders",
    "order_lines",
    "fulfillments",
    "fulfillment_events",
    "customer_reviews",
    "disputes",
    "dispute_events",
    "commission_ledger",
    "reserve_ledger",
    "refunds",
    "payouts",
    "payout_lines",
    "payout_events",
]


class CsvExporter:
    """Exports relational database tables and filtered audit reports to standard CSV."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def build_filter_query(
        self,
        table_name: str,
        seller_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Tuple[str, List]:
        """Construct deterministic SQL query with optional seller and date filters."""
        where_clauses: List[str] = []
        params: List = []

        # 1. Seller filter
        if seller_id:
            if table_name in [
                "sellers", "seller_status_events", "listings", "order_lines",
                "fulfillments", "customer_reviews", "disputes",
                "commission_ledger", "reserve_ledger", "payouts"
            ]:
                where_clauses.append(f"{table_name}.seller_id = ?")
                params.append(seller_id)
            elif table_name == "orders":
                where_clauses.append("orders.order_id IN (SELECT DISTINCT order_id FROM order_lines WHERE seller_id = ?)")
                params.append(seller_id)
            elif table_name == "customers":
                where_clauses.append(
                    "customers.customer_id IN (SELECT DISTINCT o.customer_id FROM orders o "
                    "JOIN order_lines ol ON o.order_id = ol.order_id WHERE ol.seller_id = ?)"
                )
                params.append(seller_id)
            elif table_name == "fulfillment_events":
                where_clauses.append(
                    "fulfillment_events.fulfillment_id IN (SELECT fulfillment_id FROM fulfillments WHERE seller_id = ?)"
                )
                params.append(seller_id)
            elif table_name == "dispute_events":
                where_clauses.append(
                    "dispute_events.dispute_id IN (SELECT dispute_id FROM disputes WHERE seller_id = ?)"
                )
                params.append(seller_id)
            elif table_name in ["payout_lines", "payout_events"]:
                where_clauses.append(
                    f"{table_name}.payout_id IN (SELECT payout_id FROM payouts WHERE seller_id = ?)"
                )
                params.append(seller_id)
            elif table_name == "ground_truth":
                where_clauses.append("(entity_id = ? OR description LIKE ?)")
                params.extend([seller_id, f"%{seller_id}%"])

        # 2. Date filter
        if start_date or end_date:
            date_col = None
            if table_name == "orders":
                date_col = "order_date"
            elif table_name == "fulfillments":
                date_col = "dispatched_at"
            elif table_name == "fulfillment_events":
                date_col = "event_timestamp"
            elif table_name == "disputes":
                date_col = "dispute_date"
            elif table_name == "payouts":
                date_col = "batch_date"
            elif table_name in [
                "seller_status_events", "customer_reviews", "dispute_events",
                "commission_ledger", "reserve_ledger", "payout_lines",
                "payout_events", "ground_truth"
            ]:
                date_col = "created_at"

            if date_col:
                if start_date:
                    where_clauses.append(f"{table_name}.{date_col} >= ?")
                    params.append(start_date)
                if end_date:
                    where_clauses.append(f"{table_name}.{date_col} <= ?")
                    params.append(end_date)
            elif table_name == "order_lines" and (start_date or end_date):
                sub = "order_lines.order_id IN (SELECT order_id FROM orders WHERE 1=1"
                if start_date:
                    sub += " AND order_date >= ?"
                    params.append(start_date)
                if end_date:
                    sub += " AND order_date <= ?"
                    params.append(end_date)
                sub += ")"
                where_clauses.append(sub)

        where_stmt = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        query = f"SELECT * FROM {table_name}{where_stmt} ORDER BY 1;"
        return query, params

    def export_table(
        self,
        table_name: str,
        output_path: Union[str, Path],
        seller_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        chunk_size: int = 10000,
    ) -> Dict:
        """Export a table to a CSV file in streaming chunks, returning metadata and SHA-256."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if not self.db.table_exists(table_name):
            return {
                "table": table_name,
                "path": str(path),
                "row_count": 0,
                "file_size_bytes": 0,
                "sha256": "",
                "status": "TABLE_NOT_FOUND",
            }

        query, params = self.build_filter_query(table_name, seller_id, start_date, end_date)
        row_count = 0
        hasher = hashlib.sha256()

        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            col_names = [d[0] for d in cursor.description]

            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(col_names)

                while True:
                    rows = cursor.fetchmany(chunk_size)
                    if not rows:
                        break
                    writer.writerows(rows)
                    row_count += len(rows)

        # Compute file hash and size
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)

        file_size = path.stat().st_size
        sha256_hash = hasher.hexdigest()

        return {
            "table": table_name,
            "path": str(path),
            "row_count": row_count,
            "file_size_bytes": file_size,
            "sha256": sha256_hash,
            "columns": col_names,
            "status": "SUCCESS",
        }

    def export_all_tables(
        self,
        output_dir: Union[str, Path] = "data/exports/csv",
        seller_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        exclude_ground_truth: bool = True,
    ) -> Dict[str, Dict]:
        """Export all platform relational tables to CSV in dependency order."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        tables = list(ORDERED_TABLES)
        if not exclude_ground_truth:
            tables.append("ground_truth")

        manifest = {}
        for t in tables:
            target_file = out_dir / f"{t}.csv"
            res = self.export_table(
                table_name=t,
                output_path=target_file,
                seller_id=seller_id,
                start_date=start_date,
                end_date=end_date,
            )
            manifest[t] = res

        return manifest

    def export_ground_truth(self, output_path: Union[str, Path] = "data/exports/ground_truth/ground_truth.csv") -> Dict:
        """Export negative scenario ground truth records to an isolated CSV destination."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return self.export_table("ground_truth", path)
