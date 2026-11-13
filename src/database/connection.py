"""SQLite Database connection manager and versioned migration utility."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional, Union
import pandas as pd

CURRENT_SCHEMA_VERSION = 2


class DatabaseManager:
    """Manages SQLite database connections, schema setup, and versioned migrations."""

    def __init__(self, db_path: Union[str, Path] = "data/sellerops.db"):
        path = Path(db_path)
        if not path.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent
            candidate = project_root / path
            if candidate.exists() or candidate.with_suffix(candidate.suffix + ".gz").exists():
                path = candidate
            elif not path.exists():
                path = candidate
        self.db_path = path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_db_extracted()

    def _ensure_db_extracted(self) -> None:
        """Decompress .db.gz archive into .db if the database file is absent or 0 bytes."""
        if not self.db_path.exists() or self.db_path.stat().st_size == 0:
            gz_path = self.db_path.with_name(self.db_path.name + ".gz")
            if gz_path.exists():
                import gzip
                import shutil
                tmp_path = self.db_path.with_suffix(self.db_path.suffix + ".tmp")
                with gzip.open(gz_path, "rb") as f_in:
                    with open(tmp_path, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                tmp_path.replace(self.db_path)

    def get_connection(self) -> sqlite3.Connection:
        """Create and configure a SQLite connection with foreign keys and WAL mode enabled."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.row_factory = sqlite3.Row
        # Strict foreign keys enforcement & WAL performance
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    @contextmanager
    def session(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager yielding a transactional connection with automatic rollback."""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_schema_version(self) -> int:
        """Retrieve latest applied migration version."""
        with self.session() as conn:
            if not self.table_exists("schema_migrations"):
                return 0
            row = conn.execute("SELECT MAX(version) FROM schema_migrations;").fetchone()
            return row[0] if row and row[0] is not None else 0

    def init_schema(self, schema_path: Optional[Union[str, Path]] = None, force_recreate: bool = False) -> None:
        """Initialize or upgrade database schema to current version."""
        path = schema_path or (Path(__file__).parent.parent / "models" / "schema.sql")
        if not Path(path).exists():
            raise FileNotFoundError(f"Schema file not found at: {path}")

        with open(path, "r", encoding="utf-8") as f:
            ddl_script = f.read()

        with self.session() as conn:
            current_ver = self.get_schema_version()
            if force_recreate or current_ver < CURRENT_SCHEMA_VERSION:
                # Disable FKs temporarily during table recreation
                conn.execute("PRAGMA foreign_keys = OFF;")
                tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
                for t in tables:
                    if t != "sqlite_sequence":
                        conn.execute(f"DROP TABLE IF EXISTS {t};")
                conn.execute("PRAGMA foreign_keys = ON;")

            conn.executescript(ddl_script)
            # Record migration entry
            conn.execute(
                """INSERT OR REPLACE INTO schema_migrations (version, description, applied_at)
                   VALUES (?, ?, ?);""",
                (CURRENT_SCHEMA_VERSION, f"Relational Schema v{CURRENT_SCHEMA_VERSION}", datetime.now().isoformat()),
            )

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a single write statement."""
        with self.session() as conn:
            return conn.execute(sql, params)

    def execute_many(self, sql: str, seq_of_params: list) -> None:
        """Execute batch insert/update statements."""
        with self.session() as conn:
            conn.executemany(sql, seq_of_params)

    def query_df(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        """Execute query and return results as a pandas DataFrame."""
        with self.session() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        with self.session() as conn:
            res = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
                (table_name,),
            ).fetchone()
            return res is not None

    def row_count(self, table_name: str) -> int:
        """Return the exact row count for a given table."""
        with self.session() as conn:
            res = conn.execute(f"SELECT COUNT(*) FROM {table_name};").fetchone()
            return res[0] if res else 0


def get_db(db_path: Union[str, Path] = "data/sellerops.db") -> DatabaseManager:
    """Convenience factory function."""
    return DatabaseManager(db_path)
