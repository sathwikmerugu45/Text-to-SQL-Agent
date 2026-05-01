"""
FastAPI application — REST API wrapper around the LangGraph agent.

Endpoints:
    POST /query          — Run the agent on a natural language question
    GET  /health         — DB + ChromaDB health check
    GET  /tables         — List all indexed tables
"""

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.agent.graph import run_agent
from backend.db.connection import test_connection
from backend.rag.retriever import list_indexed_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress annoying ChromaDB telemetry errors
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)

app = FastAPI(
    title="Self-Healing Text-to-SQL Agent",
    description=(
        "Ask natural language questions about your database. "
        "The agent auto-generates SQL, executes it, and self-heals on errors."
    ),
    version="1.0.0",
)

# Allow the Streamlit frontend (localhost:8501) to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response Models ──────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        example="Who are the top 5 customers by total purchase amount?",
    )


class StepTrace(BaseModel):
    node: str
    thought: str
    action: str
    observation: str


class QueryResponse(BaseModel):
    question: str
    final_answer: str
    generated_sql: str
    column_names: list[str]
    rows: list[dict[str, Any]]
    retry_count: int
    is_success: bool
    steps: list[StepTrace]


class HealthResponse(BaseModel):
    status: str
    database: bool
    chroma_tables_indexed: int


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.post("/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest):
    """
    Run the self-healing Text-to-SQL agent on a natural language question.

    The agent will:
    1. Retrieve relevant schema context from ChromaDB
    2. Generate SQL using the LLM
    3. Execute SQL against PostgreSQL
    4. Self-heal (retry with error context) up to MAX_RETRIES times
    5. Format a natural language response
    """
    logger.info("Received query: '%s'", req.question)

    try:
        state = run_agent(req.question)
    except RuntimeError as e:
        # e.g. ChromaDB not indexed yet
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected agent error")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    return QueryResponse(
        question=req.question,
        final_answer=state["final_answer"],
        generated_sql=state.get("generated_sql", ""),
        column_names=state.get("column_names", []),
        rows=state.get("execution_result") or [],
        retry_count=state.get("retry_count", 0),
        is_success=state.get("is_success", False),
        steps=[StepTrace(**s) for s in state.get("steps", [])],
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check database connectivity and ChromaDB index status."""
    db_ok = test_connection()
    try:
        tables = list_indexed_tables()
        chroma_count = len(tables)
    except Exception:
        chroma_count = 0

    status = "ok" if db_ok else "degraded"
    return HealthResponse(
        status=status,
        database=db_ok,
        chroma_tables_indexed=chroma_count,
    )


@app.get("/tables")
async def get_tables():
    """List all tables currently indexed in ChromaDB."""
    try:
        tables = list_indexed_tables()
        return {"tables": tables, "count": len(tables)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
