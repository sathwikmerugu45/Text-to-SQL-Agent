import os
from dotenv import load_dotenv

load_dotenv()

# ── OpenRouter LLM (free tier) ─────────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# Default: Llama 3.3 70B — free on OpenRouter, great SQL accuracy
LLM_MODEL = os.getenv("LLM_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))

# ── OpenAI API key (leave blank — local embeddings are used instead) ────────────
# Only needed if you want OpenAI text-embedding-ada-002; leave empty for free local embeddings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── SQLite — just a file path, no server or Docker needed ──────────────────────
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./data/chinook.sqlite")

# ── ChromaDB ───────────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "schema_store")

# ── Agent ──────────────────────────────────────────────────────────────────────
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
SCHEMA_CHUNKS_TO_RETRIEVE = int(os.getenv("SCHEMA_CHUNKS_TO_RETRIEVE", "6"))
