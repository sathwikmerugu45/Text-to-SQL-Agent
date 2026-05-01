"""
Schema Retriever — queries ChromaDB to get relevant table schemas.

Called by schema_retriever_node before every SQL generation attempt.
"""

import logging
from functools import lru_cache

import chromadb
from chromadb.utils import embedding_functions
from chromadb.config import Settings

from backend.config import (
    CHROMA_PERSIST_DIR,
    CHROMA_COLLECTION_NAME,
    OPENAI_API_KEY,
    SCHEMA_CHUNKS_TO_RETRIEVE,
)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_collection():
    """
    Returns a cached ChromaDB collection handle.
    lru_cache ensures we only open the DB once per process.
    """
    client = chromadb.PersistentClient(
        path=CHROMA_PERSIST_DIR,
        settings=Settings(anonymized_telemetry=False)
    )

    if OPENAI_API_KEY:
        emb_fn = embedding_functions.OpenAIEmbeddingFunction(
            api_key=OPENAI_API_KEY,
            model_name="text-embedding-ada-002",
        )
    else:
        emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

    return client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        embedding_function=emb_fn,
        metadata={"hnsw:space": "cosine"},
    )


def get_schema_context(query: str, n_results: int = SCHEMA_CHUNKS_TO_RETRIEVE) -> str:
    """
    Retrieve the most relevant table schema chunks for a natural language query.

    Args:
        query:     The user's plain-English question.
        n_results: How many schema chunks to retrieve (default from config).

    Returns:
        A single formatted string with all retrieved schema chunks,
        ready to be injected into the LLM prompt.
    """
    collection = _get_collection()

    # Clamp n_results to actual collection size
    total = collection.count()
    if total == 0:
        raise RuntimeError(
            "ChromaDB schema store is empty. "
            "Run `python -m scripts.index_schema` first."
        )
    n_results = min(n_results, total)

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    docs = results["documents"][0]       # list of schema chunk strings
    dists = results["distances"][0]      # cosine distances (lower = more similar)

    logger.debug(
        "Retrieved %d schema chunks for query '%s'. Distances: %s",
        len(docs), query, [f"{d:.3f}" for d in dists],
    )

    # Join all retrieved chunks with a clear separator
    formatted = "\n\n---\n\n".join(docs)
    return formatted


def list_indexed_tables() -> list[str]:
    """Return the names of all tables currently in the schema store."""
    collection = _get_collection()
    result = collection.get(include=["metadatas"])
    return [m["table_name"] for m in result["metadatas"]]
