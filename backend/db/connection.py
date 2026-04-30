"""
SQLite connection management.
Uses Python's built-in sqlite3 — no external server or Docker required.

sqlite3 is part of the Python standard library so nothing needs to be installed.
"""

import sqlite3
import logging
import os
from contextlib import contextmanager
from typing import Generator

from backend.config import SQLITE_DB_PATH

logger = logging.getLogger(__name__)


def _dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
    """Make sqlite3 return dicts instead of tuples (like RealDictCursor)."""
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager that yields a sqlite3 connection.
    Rows are returned as dicts via dict_factory.

    Usage:
        with get_connection() as conn:
            cur = conn.execute(sql)
            rows = cur.fetchall()  # list of dicts
    """
    if not os.path.exists(SQLITE_DB_PATH):
        raise RuntimeError(
            f"SQLite database not found at '{SQLITE_DB_PATH}'. "
            "Run: python -m scripts.setup_chinook"
        )

    conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    conn.row_factory = _dict_factory
    # Enable foreign key enforcement
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def test_connection() -> bool:
    """Smoke-test the SQLite connection. Returns True on success."""
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1;")
        return True
    except Exception as e:
        logger.error("DB connection test failed: %s", e)
        return False
