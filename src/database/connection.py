"""SQLite Database connection manager and query utility with strict PRAGMA enforcement."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Union
import pandas as pd


class DatabaseManager:
    """Manages SQLite database connections, schema setup, and query execution."""

    def __init__(self, db_path: Union[str, Path] = "data/sellerops.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Create and configure a SQLite connection with foreign keys and WAL mode enabled."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.row_factory = sqlite3.Row
        # Enforce foreign key constraints and WAL performance
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    @contextmanager
    def session(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager yielding a transactional connection."""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self, schema_path: Optional[Union[str, Path]] = None) -> None:
        """Initialize the database tables and indexes from schema.sql."""
        path = schema_path or (Path(__file__).parent.parent / "models" / "schema.sql")
        if not Path(path).exists():
            raise FileNotFoundError(f"Schema file not found at: {path}")

        with open(path, "r", encoding="utf-8") as f:
            ddl_script = f.read()

        with self.session() as conn:
            conn.executescript(ddl_script)

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
