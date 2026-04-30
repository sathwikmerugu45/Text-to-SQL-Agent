"""
Schema Indexer — one-time setup script.

Reads every table's structure from SQLite (using PRAGMA commands),
builds rich schema chunks, then embeds and stores them in ChromaDB.

Run once:
    python -m scripts.index_schema
"""

import logging
from typing import List

import chromadb
from chromadb.utils import embedding_functions

from backend.config import (
    CHROMA_PERSIST_DIR,
    CHROMA_COLLECTION_NAME,
    OPENAI_API_KEY,
)
from backend.db.connection import get_connection

logger = logging.getLogger(__name__)


def _get_all_tables() -> List[str]:
    """Return all user table names (excludes SQLite system tables)."""
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        return [row["name"] for row in cur.fetchall()]


def _get_columns(table_name: str) -> List[dict]:
    """Return column info using SQLite PRAGMA."""
    with get_connection() as conn:
        cur = conn.execute(f'PRAGMA table_info("{table_name}");')
        return cur.fetchall()
    # Returns: cid, name, type, notnull, dflt_value, pk


def _get_foreign_keys(table_name: str) -> List[dict]:
    """Return FK constraints using SQLite PRAGMA."""
    with get_connection() as conn:
        cur = conn.execute(f'PRAGMA foreign_key_list("{table_name}");')
        return cur.fetchall()
    # Returns: id, seq, table, from, to, on_update, on_delete, match


def _get_sample_rows(table_name: str, n: int = 3) -> List[dict]:
    """Return a few sample rows for grounding context."""
    try:
        with get_connection() as conn:
            cur = conn.execute(f'SELECT * FROM "{table_name}" LIMIT {n};')
            return cur.fetchall()
    except Exception as e:
        logger.warning("Could not fetch sample rows for %s: %s", table_name, e)
        return []


def _build_schema_chunk(table_name: str) -> str:
    """
    Build a rich, human-readable schema string for a single table.
    This is what gets embedded and retrieved at query time.
    """
    columns = _get_columns(table_name)
    foreign_keys = _get_foreign_keys(table_name)
    sample_rows = _get_sample_rows(table_name)

    # Build FK map: column_name → {foreign_table, foreign_column}
    fk_map = {fk["from"]: fk for fk in foreign_keys}

    lines = [f"TABLE: {table_name}", "COLUMNS:"]
    for col in columns:
        pk_note = " (PRIMARY KEY)" if col["pk"] else ""
        null_note = "not null" if col["notnull"] else "nullable"
        fk_note = ""
        if col["name"] in fk_map:
            fk = fk_map[col["name"]]
            fk_note = f" → FK to {fk['table']}.{fk['to']}"
        lines.append(
            f"  - {col['name']} ({col['type']}, {null_note}{pk_note}){fk_note}"
        )

    if foreign_keys:
        lines.append("RELATIONSHIPS:")
        for fk in foreign_keys:
            lines.append(
                f"  - {table_name}.{fk['from']} references {fk['table']}.{fk['to']}"
            )

    if sample_rows:
        lines.append("SAMPLE ROWS (first 3):")
        for row in sample_rows:
            truncated = {
                k: (str(v)[:50] if v is not None else "NULL")
                for k, v in row.items()
            }
            lines.append(f"  {truncated}")

    return "\n".join(lines)


def build_schema_index(force: bool = False) -> None:
    """
    Index all SQLite tables into ChromaDB.

    Args:
        force: If True, deletes and rebuilds the collection from scratch.
    """
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

    if OPENAI_API_KEY:
        logger.info("Using OpenAI embeddings (text-embedding-ada-002)")
        emb_fn = embedding_functions.OpenAIEmbeddingFunction(
            api_key=OPENAI_API_KEY,
            model_name="text-embedding-ada-002",
        )
    else:
        logger.info("Using HuggingFace all-MiniLM-L6-v2 (free, runs locally)")
        emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

    if force:
        try:
            client.delete_collection(CHROMA_COLLECTION_NAME)
            logger.info("Deleted existing collection '%s'", CHROMA_COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        embedding_function=emb_fn,
        metadata={"hnsw:space": "cosine"},
    )

    tables = _get_all_tables()
    logger.info("Found %d tables to index: %s", len(tables), tables)

    documents, ids, metadatas = [], [], []
    for table in tables:
        chunk = _build_schema_chunk(table)
        documents.append(chunk)
        ids.append(f"schema_{table}")
        metadatas.append({"table_name": table})
        logger.debug("Built schema chunk for '%s'", table)

    if documents:
        collection.upsert(documents=documents, ids=ids, metadatas=metadatas)
        logger.info("✅ Indexed %d schema chunks into ChromaDB.", len(documents))
    else:
        logger.warning("No tables found to index!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_schema_index(force=True)
    print("Schema index built successfully.")
