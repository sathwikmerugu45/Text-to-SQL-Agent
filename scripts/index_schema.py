"""
CLI script — indexes PostgreSQL schema into ChromaDB.

Usage:
    python -m scripts.index_schema           # normal run (skip if already indexed)
    python -m scripts.index_schema --force   # wipe and rebuild from scratch
"""

import sys
import logging
import argparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
# Mute ChromaDB telemetry noise — the posthog client has a known bug in 0.5.x
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)
logging.getLogger("chromadb").setLevel(logging.WARNING)

from backend.db.connection import test_connection
from backend.rag.schema_indexer import build_schema_index
from backend.rag.retriever import list_indexed_tables


def main():
    parser = argparse.ArgumentParser(description="Index database schema into ChromaDB")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Drop and rebuild the ChromaDB collection from scratch",
    )
    args = parser.parse_args()

    print("🔌 Testing database connection...")
    if not test_connection():
        print("❌ Cannot connect to PostgreSQL. Check DATABASE_URL in your .env file.")
        sys.exit(1)
    print("✅ Database connected.\n")

    print(f"📦 Building schema index {'(forced rebuild)' if args.force else ''}...")
    build_schema_index(force=args.force)

    tables = list_indexed_tables()
    print(f"\n✅ Done. {len(tables)} tables indexed:")
    for t in sorted(tables):
        print(f"   • {t}")


if __name__ == "__main__":
    main()
