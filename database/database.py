"""
Database module - SQLite persistence layer for system monitoring data.
"""
import sqlite3
import os
from contextlib import contextmanager
from typing import Any

# Default database path relative to project root
_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_DB_PATH = os.path.join(_DB_DIR, "monitor.db")


@contextmanager
def _get_connection(db_path: str | None = None):
    """Context manager for database connections. Auto-commits and closes."""
    path = db_path or _DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database(db_path: str | None = None) -> None:
    """
    Initialize the database: create system_stats table and indexes if not exist.
    Also ensures the data directory exists.
    """
    path = db_path or _DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with _get_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_stats (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       REAL    NOT NULL,
                cpu_percent     REAL    NOT NULL,
                memory_percent  REAL    NOT NULL,
                disk_percent    REAL    NOT NULL,
                upload_speed    REAL    NOT NULL,
                download_speed  REAL    NOT NULL
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_system_stats_ts
            ON system_stats(timestamp)
        """)


def save_stats(
    cpu_percent: float,
    memory_percent: float,
    disk_percent: float,
    upload_speed: float,
    download_speed: float,
    db_path: str | None = None,
) -> int:
    """
    Insert a row of system monitoring data. Returns the new row id.
    """
    import time

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO system_stats (timestamp, cpu_percent, memory_percent,
                                      disk_percent, upload_speed, download_speed)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (time.time(), cpu_percent, memory_percent, disk_percent, upload_speed, download_speed),
        )
        return cursor.lastrowid


def get_recent_stats(
    limit: int = 3600,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """
    Return the most recent rows from system_stats, ordered by timestamp descending.
    Default limit is 3600 (1 hour of 1-second samples).
    Returns a list of dicts.
    """
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, timestamp, cpu_percent, memory_percent,
                   disk_percent, upload_speed, download_speed
            FROM system_stats
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
