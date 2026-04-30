"""
SQL execution layer — SQLite edition.

Runs SQL in read-only mode to prevent mutations.
Returns (rows, column_names) on success, raises on error.

SQLite differences vs PostgreSQL to note for the LLM prompts:
  - No ILIKE  → use LIKE (case-insensitive by default for ASCII)
  - No SERIAL → use INTEGER PRIMARY KEY AUTOINCREMENT
  - String concat: || instead of concat()
  - Date funcs: strftime() instead of date_trunc()
"""

import logging
import re
from typing import Any, Dict, List, Tuple

from backend.db.connection import get_connection

logger = logging.getLogger(__name__)

_FORBIDDEN = re.compile(
    r"^\s*(DROP|DELETE|INSERT|UPDATE|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|REPLACE|ATTACH)\b",
    re.IGNORECASE | re.MULTILINE,
)

MAX_ROWS = 500


def _is_safe(sql: str) -> bool:
    return not bool(_FORBIDDEN.search(sql))


def execute_sql(sql: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Execute a SQL string against the SQLite database.

    Args:
        sql: A SELECT query string.

    Returns:
        (rows, column_names)

    Raises:
        ValueError: non-SELECT SQL detected.
        sqlite3.Error: SQLite syntax or runtime error.
    """
    if not sql.strip():
        raise ValueError("Empty SQL query.")

    if not _is_safe(sql):
        raise ValueError(
            "Only SELECT statements are allowed. "
            "Forbidden keyword detected in generated SQL."
        )

    logger.debug("Executing SQL:\n%s", sql)

    with get_connection() as conn:
        cur = conn.execute(sql)
        raw_rows = cur.fetchmany(MAX_ROWS)
        # dict_factory already applied in connection.py
        column_names = [desc[0] for desc in cur.description] if cur.description else []

    logger.debug("Query returned %d rows. Columns: %s", len(raw_rows), column_names)
    return raw_rows, column_names
