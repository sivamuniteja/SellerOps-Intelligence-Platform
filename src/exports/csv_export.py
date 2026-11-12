"""CSV Data and Audit Report Exporter."""

from pathlib import Path
from typing import Optional, Union
import pandas as pd
from src.database.connection import DatabaseManager


class CsvExporter:
    """Exports database tables and audit analytics to formatted CSV files."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def export_table(self, table_name: str, output_path: Union[str, Path]) -> str:
        """Export an entire database table to a CSV file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        df = self.db.query_df(f"SELECT * FROM {table_name};")
        df.to_csv(path, index=False, encoding="utf-8")
        return str(path)

    def export_all_tables(self, output_dir: Union[str, Path] = "data/scenarios/csv_exports") -> list:
        """Export all core platform tables to CSV."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        tables = [
            "sellers", "customers", "listings", "orders",
            "fulfillments", "reviews", "disputes", "order_settlements",
            "payout_batches", "payout_lines", "anomalies_ground_truth"
        ]
        exported_files = []
        for t in tables:
            target = out_dir / f"{t}.csv"
            self.export_table(t, target)
            exported_files.append(str(target))

        return exported_files
