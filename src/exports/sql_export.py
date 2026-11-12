"""SQL Dump Exporter for SellerOps Database."""

from pathlib import Path
from typing import Union
from src.database.connection import DatabaseManager


class SqlExporter:
    """Generates standard SQL dump scripts for cross-database migration."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def export_dump(self, output_path: Union[str, Path]) -> str:
        """Export full database schema and data as SQL statements."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write("-- ========================================================\n")
            f.write("-- SellerOps Intelligence Platform - Complete SQL Data Dump\n")
            f.write("-- ========================================================\n\n")

            with self.db.session() as conn:
                for line in conn.iterdump():
                    f.write(f"{line}\n")

        return str(path)
