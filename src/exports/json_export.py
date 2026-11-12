"""JSON Data and Audit Report Exporter.

Provides streaming, memory-efficient JSON export for all SellerOps relational entities
preserving financial precision, timestamps, and relational keys.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from src.database.connection import DatabaseManager
from src.exports.csv_export import ORDERED_TABLES, CsvExporter


class JsonExporter:
    """Exports structured database entities and audit datasets to standardized JSON format."""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._query_builder = CsvExporter(db)

    def export_table(
        self,
        table_name: str,
        output_path: Union[str, Path],
        seller_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
        chunk_size: int = 5000,
        as_envelope: bool = False,
    ) -> Dict:
        """Export table records to JSON in streaming chunks with SHA-256 computation."""
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

        query, params = self._query_builder.build_filter_query(
            table_name, seller_id=seller_id, start_date=start_date, end_date=end_date
        )
        if limit and limit > 0:
            query = query.rstrip(";") + f" LIMIT {limit};"

        row_count = 0
        hasher = hashlib.sha256()

        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            col_names = [d[0] for d in cursor.description]

            with open(path, "w", encoding="utf-8") as f:
                if as_envelope:
                    f.write("{\n")
                    f.write(f'  "table": "{table_name}",\n')
                    f.write(f'  "exported_at": "{datetime.now().isoformat()}",\n')
                    if seller_id:
                        f.write(f'  "seller_id_filter": "{seller_id}",\n')
                    f.write('  "records": [\n')
                else:
                    f.write("[\n")

                first_row = True
                while True:
                    rows = cursor.fetchmany(chunk_size)
                    if not rows:
                        break

                    for r in rows:
                        record_dict = dict(zip(col_names, r))
                        json_str = json.dumps(record_dict, ensure_ascii=False)
                        if not first_row:
                            f.write(",\n")
                        else:
                            first_row = False
                        f.write("  " + json_str)
                        row_count += 1

                if as_envelope:
                    f.write("\n  ],\n")
                    f.write(f'  "record_count": {row_count}\n')
                    f.write("}\n")
                else:
                    f.write("\n]\n")

        # Compute SHA-256 and size
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
        output_dir: Union[str, Path] = "data/exports/json",
        seller_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        exclude_ground_truth: bool = True,
        as_envelope: bool = False,
    ) -> Dict[str, Dict]:
        """Export all platform relational tables to individual JSON files."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        tables = list(ORDERED_TABLES)
        if not exclude_ground_truth:
            tables.append("ground_truth")

        manifest = {}
        for t in tables:
            target_file = out_dir / f"{t}.json"
            res = self.export_table(
                table_name=t,
                output_path=target_file,
                seller_id=seller_id,
                start_date=start_date,
                end_date=end_date,
                as_envelope=as_envelope,
            )
            manifest[t] = res

        return manifest

    def export_ground_truth(
        self,
        output_path: Union[str, Path] = "data/exports/ground_truth/ground_truth.json",
        as_envelope: bool = True,
    ) -> Dict:
        """Export negative scenario ground truth records to an isolated JSON destination."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return self.export_table("ground_truth", path, as_envelope=as_envelope)
