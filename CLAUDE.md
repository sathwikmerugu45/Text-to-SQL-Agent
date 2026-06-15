# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Common Development Commands

| Task | Command | Notes |
|------|---------|-------|
| **Install dependencies** | `python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate`
|  | `pip install -r requirements.txt` | Installs all runtime, agent, and UI dependencies. |
| **Configure environment** | `cp .env.example .env` && edit `.env` to set `OPENAI_API_KEY` (optional) and any other overrides. |
| **Download sample database** | `python -m scripts.setup_chinook` | Pulls the Chinook SQLite DB into `data/`. |
| **Index schema into ChromaDB** | `python -m scripts.index_schema [--force]` | Embeds PostgreSQL/SQLite schema for retrieval; `--force` rebuilds the index. |
| **Run the FastAPI backend** | `uvicorn main:app --reload --port 8000` | Starts the HTTP API (`/query`, `/health`, `/tables`). |
| **Run the Streamlit UI** | `streamlit run frontend/app.py` | Opens the tracing UI at `http://localhost:8501`. |
| **Run the end‑to‑end smoke test** | `python -m scripts.test_agent` | Executes a handful of representative queries and prints pass/fail. |
| **Run a single test (debug)** | `python - <<EOF\nfrom scripts.test_agent import TEST_QUERIES, run_tests\nprint(TEST_QUERIES[0])\nEOF` | You can import `run_agent` from `backend.agent.graph` and call it directly for ad‑hoc debugging. |
| **Re‑run the agent on a custom query** | `python -c "from backend.agent.graph import run_agent; print(run_agent('your question'))"` | Useful for rapid experimentation without the UI. |
| **Lint / type‑check** | No dedicated lint config shipped. Recommended: `ruff check .` or `flake8 .` if installed locally. |
| **Format code** | `black .` (if you have `black` installed). |

---

## High‑Level Architecture

The repository implements a **self‑healing Text‑to‑SQL agent** built on LangGraph. The data flow can be understood as three logical layers:

1. **FastAPI Backend (`main.py`)** – exposes HTTP endpoints (`/query`, `/health`, `/tables`). It wires the LangGraph agent graph (`backend/agent/graph.py`) to HTTP request handling.
2. **Agent Layer (`backend/agent/…`)** – core state machine:
   * `state.py` defines `AgentState` (typed dict) holding the current SQL, any error message, and `retry_count`.
   * `prompts.py` stores the LLM prompt templates used for schema retrieval, SQL generation, and retry handling.
   * `nodes.py` implements the LangGraph node functions: schema RAG, SQL generation, execution, routing, success formatting, and max‑retry handling.
   * `graph.py` assembles the nodes into a LangGraph `graph` and provides `run_agent(question: str) → dict` that returns the final answer and metadata.
3. **Data & Retrieval Layer (`backend/db/` and `backend/rag/`)** –
   * `connection.py` creates a read‑only PostgreSQL/SQLite connection pool.
   * `executor.py` safely runs generated SELECT statements (regex guard + read‑only transaction).
   * `schema_indexer.py` reads the database schema (tables, columns, foreign keys, sample rows) and stores vector embeddings in a local ChromaDB collection.
   * `retriever.py` performs a cosine‑similarity search over the schema embeddings at query time, returning the most relevant schema chunks to the LLM.

### Execution Flow (simplified)

```
User → FastAPI /query → run_agent()
    ├─ retrieve relevant schema chunks via ChromaDB (RAG)
    ├─ generate SQL (LLM) using schema context & user question
    ├─ execute SQL (executor) → either success or PostgreSQL error
    ├─ if error && retry_count < MAX_RETRIES:
    │     augment AgentState with error + previous SQL
    │     loop back to SQL generation (self‑healing)
    └─ on success: format answer, return to API → UI
```

The **self‑healing loop** is a classic ReAct pattern: the LLM observes the error, reasons about a fix, and acts again. The retry limit (`MAX_RETRIES`) is enforced in the graph to prevent infinite cycles.

### Frontend (`frontend/app.py`)

A Streamlit app visualises the LangGraph trace: each node's output, the generated SQL, execution results, and any retries. This UI is primarily for debugging and demo purposes.

---

## Project Structure (summary)

```
sql-agent/
├─ main.py                 # FastAPI entry point
├─ requirements.txt
├─ docker-compose.yml      # (optional) PostgreSQL container definition
├─ .env.example            # Template for environment configuration
│
├─ backend/
│   ├─ config.py          # Loads environment variables
│   ├─ agent/
│   │   ├─ state.py       # Typed AgentState
│   │   ├─ prompts.py     # Prompt templates
│   │   ├─ nodes.py       # LangGraph node implementations
│   │   └─ graph.py       # Graph assembly + run_agent()
│   ├─ db/
│   │   ├─ connection.py  # DB connection pool (Postgres/SQLite)
│   │   └─ executor.py    # Safe SELECT execution with guard
│   └─ rag/
│       ├─ schema_indexer.py  # One‑time schema → ChromaDB
│       └─ retriever.py       # Per‑query schema chunk retrieval
│
├─ frontend/
│   └─ app.py            # Streamlit UI for trace viewing
│
├─ scripts/
│   ├─ setup_chinook.py  # Downloads SQLite Chinook sample DB
│   ├─ index_schema.py   # Runs schema_indexer
│   └─ test_agent.py     # Smoke‑test suite (run with `python -m scripts.test_agent`)
│
└─ data/                  # Holds downloaded DB files & generated ChromaDB files
```

---

## Additional Notes for Claude Code

* **State Persistence** – The LangGraph state is purely in‑memory for each request; there is no external persistence of retry history.
* **Safety** – `executor.py` enforces a regex whitelist that only permits `SELECT` statements and runs the query inside a read‑only transaction. This protects the underlying DB from accidental writes.
* **Embedding Model** – If `OPENAI_API_KEY` is not set, the code falls back to a local Sentence‑Transformer model (`all‑MiniLM‑L6‑v2`) for schema embeddings.
* **Docker** – The repo includes a `docker-compose.yml` that can spin up a PostgreSQL instance, but the default quick‑start uses the SQLite Chinook DB for zero‑install setup.
* **Extensibility** – To add more agent capabilities (e.g., INSERT/UPDATE with approval), you would extend `nodes.py` with new LangGraph nodes and adjust the state schema accordingly.

---

*This file is intended solely for Claude Code tooling; it is not part of the runtime application.*
