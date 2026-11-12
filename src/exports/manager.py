"""Export Manager and Orchestrator for SellerOps Intelligence Platform.

Coordinates full-dataset and filtered exports across CSV, JSON, and SQL formats,
isolated ground-truth generation, machine-readable validation reports,
SHA-256 checksums, and round-trip re-import verification.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from src.database.connection import DatabaseManager, get_db
from src.exports.csv_export import ORDERED_TABLES, CsvExporter
from src.exports.json_export import JsonExporter
from src.exports.sql_export import SqlExporter
from src.validation.anomaly_detection import AnomalyDetectionEngine
from src.validation.validator import FullPlatformValidator


def compute_file_sha256(path: Union[str, Path]) -> str:
    """Compute standard SHA-256 hash for a file on disk."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class ExportManager:
    """Master manager coordinating all multi-format export engines and verification workflows."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or get_db()
        self.csv_exporter = CsvExporter(self.db)
        self.json_exporter = JsonExporter(self.db)
        self.sql_exporter = SqlExporter(self.db)

    def export_full_suite(
        self,
        output_dir: Union[str, Path] = "data/exports",
        seller_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_reports: bool = True,
        verify_after_export: bool = True,
    ) -> Dict:
        """Execute full multi-format export pipeline."""
        start_time = time.time()
        base_dir = Path(output_dir)
        base_dir.mkdir(parents=True, exist_ok=True)

        csv_dir = base_dir / "csv"
        json_dir = base_dir / "json"
        sql_dir = base_dir / "sql"
        gt_dir = base_dir / "ground_truth"
        reports_dir = base_dir / "reports"

        print(f"\n[1/6] Exporting CSV tables to {csv_dir}...")
        csv_manifest = self.csv_exporter.export_all_tables(
            output_dir=csv_dir,
            seller_id=seller_id,
            start_date=start_date,
            end_date=end_date,
            exclude_ground_truth=True,
        )

        print(f"[2/6] Exporting JSON tables to {json_dir}...")
        json_manifest = self.json_exporter.export_all_tables(
            output_dir=json_dir,
            seller_id=seller_id,
            start_date=start_date,
            end_date=end_date,
            exclude_ground_truth=True,
            as_envelope=False,
        )

        print(f"[3/6] Exporting SQL master seed script to {sql_dir}...")
        sql_seed_path = sql_dir / "seed_data.sql"
        sql_manifest = self.sql_exporter.export_seed_data(
            output_path=sql_seed_path,
            seller_id=seller_id,
            start_date=start_date,
            end_date=end_date,
            include_schema=True,
            exclude_ground_truth=True,
        )

        print(f"[4/6] Exporting isolated Ground Truth datasets to {gt_dir}...")
        gt_csv_meta = self.csv_exporter.export_ground_truth(gt_dir / "ground_truth.csv")
        gt_json_meta = self.json_exporter.export_ground_truth(gt_dir / "ground_truth.json")
        gt_sql_meta = self.sql_exporter.export_ground_truth_sql(gt_dir / "ground_truth.sql")

        # 5. Export Reports and Anomaly Results
        reports_manifest = {}
        if include_reports:
            print(f"[5/6] Generating validation and anomaly detection reports in {reports_dir}...")
            reports_dir.mkdir(parents=True, exist_ok=True)

            # A. Validation Report
            validator = FullPlatformValidator(self.db)
            val_report = validator.run_validation(
                export_path=str(reports_dir / "validation_report.json")
            )
            reports_manifest["validation_report_json"] = str(reports_dir / "validation_report.json")

            # B. Anomaly Detection Results
            detector = AnomalyDetectionEngine(self.db)
            ano_report = detector.run_all_detectors()

            ano_json_path = reports_dir / "anomaly_detection_results.json"
            with open(ano_json_path, "w", encoding="utf-8") as f:
                json.dump(ano_report, f, indent=2)
            reports_manifest["anomaly_results_json"] = str(ano_json_path)

            ano_csv_path = reports_dir / "anomaly_detection_results.csv"
            all_detected = ano_report.get("all_detected_list", [])
            if all_detected:
                import pandas as pd
                df_ano = pd.DataFrame(all_detected)
                df_ano.to_csv(ano_csv_path, index=False)
                reports_manifest["anomaly_results_csv"] = str(ano_csv_path)

        # 6. Generate Checksums and Manifests
        print(f"[6/6] Compiling SHA-256 checksums and manifests...")
        all_exported_files = []
        for root, _, files in os.walk(base_dir):
            for file in sorted(files):
                if file.startswith("checksums."):
                    continue
                full_path = Path(root) / file
                rel_path = full_path.relative_to(base_dir)
                all_exported_files.append((str(rel_path), full_path))

        checksums_dict = {}
        sha256_lines = []
        for rel_str, full_path in all_exported_files:
            file_hash = compute_file_sha256(full_path)
            file_size = full_path.stat().st_size
            checksums_dict[rel_str] = {
                "sha256": file_hash,
                "size_bytes": file_size,
            }
            sha256_lines.append(f"{file_hash}  {rel_str}")

        checksums_json_path = base_dir / "checksums.json"
        with open(checksums_json_path, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": datetime.now().isoformat(),
                "algorithm": "SHA-256",
                "total_files": len(checksums_dict),
                "files": checksums_dict,
            }, f, indent=2)

        checksums_sha256_path = base_dir / "checksums.sha256"
        with open(checksums_sha256_path, "w", encoding="utf-8") as f:
            f.write("\n".join(sha256_lines) + "\n")

        # Update Project Manifests in manifests/
        self._update_manifests(sql_manifest.get("table_row_counts", {}))

        # Re-import verification
        reimport_result = None
        if verify_after_export:
            print("[-] Verifying round-trip re-import of exported SQL seed data...")
            tmp_db = base_dir / "_temp_reimport_test.db"
            reimport_result = self.sql_exporter.verify_reimport_sql(sql_seed_path, tmp_db)
            if tmp_db.exists():
                tmp_db.unlink()
            print(f"    Re-import Verification: {'PASSED ✅' if reimport_result['valid'] else 'FAILED 🚨'}")

        elapsed = round(time.time() - start_time, 2)
        print(f"\n✅ Export suite completed in {elapsed}s across {len(checksums_dict)} files.")

        return {
            "status": "SUCCESS",
            "execution_seconds": elapsed,
            "output_directory": str(base_dir),
            "total_files_exported": len(checksums_dict),
            "csv_manifest": csv_manifest,
            "json_manifest": json_manifest,
            "sql_manifest": sql_manifest,
            "ground_truth_manifest": {
                "csv": gt_csv_meta,
                "json": gt_json_meta,
                "sql": gt_sql_meta,
            },
            "reports_manifest": reports_manifest,
            "checksums_json": str(checksums_json_path),
            "checksums_sha256": str(checksums_sha256_path),
            "reimport_verification": reimport_result,
        }

    def _update_manifests(self, actual_counts: Dict[str, int]):
        """Generate and synchronize manifests/source_manifest.json and generation_summary.json."""
        manifest_dir = Path("manifests")
        manifest_dir.mkdir(parents=True, exist_ok=True)

        gt_count = self.db.row_count("ground_truth") if self.db.table_exists("ground_truth") else 0

        # Compute table checksums
        table_checksums = {}
        for t in ORDERED_TABLES:
            if self.db.table_exists(t):
                with self.db.session() as conn:
                    cursor = conn.execute(f"SELECT * FROM {t} ORDER BY 1 LIMIT 5000;")
                    h = hashlib.sha256()
                    for r in cursor.fetchall():
                        h.update("|".join(str(v) for v in r).encode("utf-8"))
                    table_checksums[t] = h.hexdigest()[:16]

        summary = {
            "generated_at": datetime.now().isoformat(),
            "target_mode": "full" if actual_counts.get("orders", 0) > 5000 else "starter",
            "seed": 20261022,
            "counts": actual_counts,
            "ground_truth_count": gt_count,
            "table_checksums": table_checksums,
        }

        with open(manifest_dir / "generation_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        source_manifest = {
            "project": "SellerOps Intelligence Platform",
            "version": "1.0.0",
            "seed": 20261022,
            "database_engine": "SQLite 3",
            "foreign_keys_enforced": True,
            "financial_precision": "Integer cents",
            "exported_tables_count": len(ORDERED_TABLES),
            "tables_sequence": ORDERED_TABLES,
            "table_checksums": table_checksums,
            "table_row_counts": actual_counts,
        }

        with open(manifest_dir / "source_manifest.json", "w", encoding="utf-8") as f:
            json.dump(source_manifest, f, indent=2)


def main():
    """CLI Entrypoint for the Export Engine."""
    parser = argparse.ArgumentParser(description="Export SellerOps database entities and reports.")
    parser.add_argument("--out-dir", type=str, default="data/exports", help="Target output directory.")
    parser.add_argument("--seller-id", type=str, default=None, help="Filter by Seller ID.")
    parser.add_argument("--start-date", type=str, default=None, help="Filter by Start Date (YYYY-MM-DD).")
    parser.add_argument("--end-date", type=str, default=None, help="Filter by End Date (YYYY-MM-DD).")
    parser.add_argument("--no-verify", action="store_true", help="Skip round-trip re-import verification.")

    args = parser.parse_args()

    manager = ExportManager()
    manager.export_full_suite(
        output_dir=args.out_dir,
        seller_id=args.seller_id,
        start_date=args.start_date,
        end_date=args.end_date,
        verify_after_export=not args.no_verify,
    )


if __name__ == "__main__":
    main()
