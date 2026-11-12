"""JSON Data and Audit Report Exporter."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Union
from src.database.connection import DatabaseManager


class JsonExporter:
    """Exports structured database entities and anomaly logs to JSON."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def export_table(self, table_name: str, output_path: Union[str, Path], limit: Optional[int] = None) -> str:
        """Export table rows to JSON array with metadata wrapper."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        limit_clause = f" LIMIT {limit}" if limit else ""
        df = self.db.query_df(f"SELECT * FROM {table_name}{limit_clause};")

        payload = {
            "table": table_name,
            "exported_at": datetime.now().isoformat(),
            "record_count": len(df),
            "records": df.to_dict(orient="records"),
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        return str(path)
