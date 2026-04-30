# 🤖 Self-Healing Text-to-SQL Agent

A production-grade AI agent that converts plain English questions into SQL, executes them against PostgreSQL, and **automatically fixes errors through a self-healing retry loop** — showing every reasoning step in a Streamlit UI.

Built with **LangGraph**, **LangChain**, **ChromaDB**, **FastAPI**, and **PostgreSQL**.

---

## Architecture

```
User Query
    │
    ▼
┌─────────────────────┐
│   Schema Retriever  │  ← ChromaDB vector search (finds relevant tables)
└────────┬────────────┘
         │
    ┌────▼────────────┐
    │  SQL Generator  │◄──────────────────────────┐
    └────┬────────────┘                            │
         │                                         │ error + context
    ┌────▼────────────┐                            │ (self-healing loop)
    │  SQL Executor   │                            │
    └────┬────────────┘                            │
         │                                         │
    ┌────▼──────┐  error, retries < 3   ───────────┘
    │  Router   │
    └──┬────┬───┘
       │    │
    success  retries ≥ 3
       │         │
  ┌────▼───┐  ┌──▼──────────────┐
  │Formatter│  │Max Retry Handler│
  └────┬────┘  └─────────────────┘
       │
    Final Answer
```

**The key insight:** After a SQL execution error, the agent doesn't start over — it reads the exact PostgreSQL error message, adds it to the LangGraph state, and feeds it back to the SQL Generator. The LLM now knows *what went wrong* and can fix it specifically. This is the **ReAct (Reason → Act → Observe)** loop applied to a real SDE problem.

---

## Project Structure

```
sql-agent/
├── main.py                    # FastAPI app (REST API)
├── requirements.txt
├── docker-compose.yml         # Spins up PostgreSQL
├── .env.example               # Copy to .env and fill in
│
├── backend/
│   ├── config.py              # All config loaded from .env
│   ├── agent/
│   │   ├── state.py           # AgentState TypedDict (LangGraph state)
│   │   ├── prompts.py         # All LLM prompt templates
│   │   ├── nodes.py           # LangGraph node functions (core logic)
│   │   └── graph.py           # Graph assembly + run_agent() entry point
│   ├── db/
│   │   ├── connection.py      # PostgreSQL connection pool
│   │   └── executor.py        # SQL execution with safety guards
│   └── rag/
│       ├── schema_indexer.py  # One-time: reads PG schema → ChromaDB
│       └── retriever.py       # Per-query: fetches relevant schema chunks
│
├── frontend/
│   └── app.py                 # Streamlit UI with step trace viewer
│
├── scripts/
│   ├── setup_chinook.py       # Downloads + loads Chinook sample DB
│   ├── index_schema.py        # Indexes DB schema into ChromaDB
│   └── test_agent.py          # End-to-end smoke tests
│
└── data/                      # Downloaded SQL files go here
```

---

## Quick Start

**Prerequisites:** Python 3.10+ and an OpenAI API key. Nothing else — no Docker, no database server.

### 1. Clone and install
```bash
git clone https://github.com/yourusername/sql-agent.git
cd sql-agent
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Open .env and set your OPENAI_API_KEY — that's the only required change
```

### 3. Download the Chinook sample database
```bash
python -m scripts.setup_chinook
```
Downloads `data/chinook.sqlite` (~1 MB) from GitHub. Uses SQLite — built into Python, zero install, no Docker needed. The Chinook schema has 11 tables: Artist, Album, Track, Genre, Invoice, InvoiceLine, Customer, Employee — perfect for complex multi-join queries.

### 4. Index the schema into ChromaDB
```bash
python -m scripts.index_schema
```
Reads every table's columns, types, foreign keys, and sample rows, then embeds them into ChromaDB. Run once — or with `--force` to rebuild.

### 5. Start the FastAPI backend
```bash
uvicorn main:app --reload --port 8000
```

### 6. Start the Streamlit frontend (new terminal)
```bash
streamlit run frontend/app.py
```
Open **http://localhost:8501** and start asking questions.

---

## Example Queries to Try

| Query | Why it's interesting |
|---|---|
| `Who are the top 5 customers by total invoice amount?` | 3-table join: Customer + Invoice + InvoiceLine |
| `Which genre has the most tracks?` | GROUP BY + ORDER BY + LIMIT |
| `What is the average track length per genre?` | Aggregate with unit conversion |
| `Which employee has handled the most customers?` | Self-referential Employee table |
| `Show total revenue by country` | Geo aggregation |
| `List all albums by AC/DC` | Specific artist lookup |

---

## How the Self-Healing Works (Interview Explanation)

```
Attempt 1: "Show top customers"
  LLM writes: SELECT name FROM Customers ORDER BY total DESC LIMIT 5
  Error: column "total" does not exist

State now contains: { previous_sql, error_message, retry_count: 1 }

Attempt 2: LLM receives the error + original schema context
  LLM writes: SELECT c.FirstName, SUM(i.Total) AS revenue
              FROM Customer c JOIN Invoice i ON c.CustomerId = i.CustomerId
              GROUP BY c.CustomerId ORDER BY revenue DESC LIMIT 5
  Result: 5 rows ✅
```

The LangGraph state object accumulates error context across attempts — this is **stateful error recovery**, not just retrying the same prompt.

---

## API Reference

```
POST /query         → Run the agent
GET  /health        → DB + ChromaDB health check
GET  /tables        → List indexed tables
GET  /docs          → Swagger UI (auto-generated by FastAPI)
```

**POST /query example:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Who are the top 5 customers by revenue?"}'
```

---

## Interview Talking Points

**Q: Why LangGraph instead of just chaining prompts?**  
A: LangGraph gives you a proper state machine with typed state, conditional edges, and a persistent state object. Each retry enriches `AgentState` with the previous SQL and error, so the LLM has cumulative context — not just the last error.

**Q: How does Schema RAG prevent hallucinations?**  
A: Before generating SQL, the schema retriever embeds the user's question and does cosine similarity search in ChromaDB to find the most relevant table definitions. The LLM is told "these are the actual columns available" — not guessing from training data.

**Q: What prevents infinite loops?**  
A: The `retry_count` field in `AgentState`. The conditional edge `should_retry_or_succeed()` checks `retry_count >= MAX_RETRIES` and routes to `max_retry_handler_node` instead of the generator — a dead-end that returns a graceful error.

**Q: How is this different from ChatGPT writing SQL?**  
A: ChatGPT has no memory of its own failures, doesn't know your actual schema, and can't execute queries. This agent executes real SQL, reads real PostgreSQL errors, updates state, and self-corrects — it's an autonomous loop, not a one-shot prompt.

**Q: How did you make the SQL execution safe?**  
A: Two layers — (1) a regex guard in `executor.py` that rejects any non-SELECT statement before it reaches the DB, and (2) a PostgreSQL read-only transaction via `conn.set_session(readonly=True)`, so even if the guard is bypassed, the DB won't mutate.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph 0.2 |
| LLM calls | LangChain + OpenAI GPT-3.5/4o |
| Vector DB | ChromaDB (local, persistent) |
| Embeddings | OpenAI ada-002 or HuggingFace all-MiniLM (free) |
| Database | PostgreSQL 16 (Docker) |
| Backend API | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Sample data | Chinook Database |
