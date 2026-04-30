"""
LangGraph node functions.

Each function receives the current AgentState, performs exactly one job,
appends a StepTrace to state["steps"], and returns the updated state.

Node flow:
    schema_retriever_node
        → sql_generator_node
            → sql_executor_node
                ─ success → response_formatter_node → END
                ─ error, retry_count < MAX_RETRIES → sql_generator_node (loop)
                ─ error, retry_count >= MAX_RETRIES → max_retry_handler_node → END
"""

import re
import json
import logging
from typing import Any

from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

from backend.config import (
    LLM_MODEL,
    LLM_TEMPERATURE,
    MAX_RETRIES,
    SCHEMA_CHUNKS_TO_RETRIEVE,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
)
from backend.agent.state import AgentState
from backend.agent.prompts import (
    SQL_GENERATOR_SYSTEM_PROMPT,
    SQL_GENERATOR_FIRST_ATTEMPT_PROMPT,
    SQL_GENERATOR_RETRY_PROMPT,
    RESPONSE_FORMATTER_SYSTEM_PROMPT,
    RESPONSE_FORMATTER_PROMPT,
)
from backend.rag.retriever import get_schema_context
from backend.db.executor import execute_sql

logger = logging.getLogger(__name__)

# ── Free model fallback chain ──────────────────────────────────────────────────
# Tried in order — first one that responds without 404/429 wins.
# All are $0 cost on OpenRouter. Update the list anytime at openrouter.ai/models?max_price=0
FREE_MODEL_CHAIN = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "google/gemma-4-31b-it:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "meta-llama/llama-3.2-3b-instruct:free",
]

# Module-level cache — stores the index of the last working model
_working_model_idx: int = -1   # -1 means "use .env preference first"


def _make_llm(model: str) -> ChatOpenAI:
    """Construct a ChatOpenAI pointed at OpenRouter with the given model."""
    import os
    from dotenv import load_dotenv
    load_dotenv(override=True)
    return ChatOpenAI(
        model=model,
        temperature=float(os.getenv("LLM_TEMPERATURE", str(LLM_TEMPERATURE))),
        openai_api_key=os.getenv("OPENROUTER_API_KEY", OPENROUTER_API_KEY),
        openai_api_base=os.getenv("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL),
    )


def _get_llm() -> ChatOpenAI:
    """
    Return a ChatOpenAI instance using the cached working model.
    On first call, reads LLM_MODEL from .env (always fresh).
    Falls back through FREE_MODEL_CHAIN automatically on 404/429.
    Call _mark_model_failed(model) when a call returns 404 or 429
    to advance to the next model in the chain.
    """
    global _working_model_idx
    import os
    from dotenv import load_dotenv
    load_dotenv(override=True)
    preferred = os.getenv("LLM_MODEL", FREE_MODEL_CHAIN[0])

    if _working_model_idx == -1:
        # First call — honour the .env setting
        model = preferred
    else:
        model = FREE_MODEL_CHAIN[_working_model_idx]

    logger.debug("_get_llm -> %s", model)
    return _make_llm(model)


def _mark_model_failed(failed_model: str) -> None:
    """
    Called when a model returns 404 or 429.
    Advances _working_model_idx to the next entry in FREE_MODEL_CHAIN.
    """
    global _working_model_idx
    import os
    from dotenv import load_dotenv
    load_dotenv(override=True)
    preferred = os.getenv("LLM_MODEL", FREE_MODEL_CHAIN[0])

    # Build the chain with preferred first (same as _get_llm)
    chain = [preferred] + [m for m in FREE_MODEL_CHAIN if m != preferred]

    current_idx = _working_model_idx if _working_model_idx >= 0 else 0
    # Find the failed model in the chain and move to next
    try:
        failed_idx = chain.index(failed_model)
        next_idx = failed_idx + 1
    except ValueError:
        next_idx = current_idx + 1

    if next_idx < len(chain):
        next_model = chain[next_idx]
        # Map back to FREE_MODEL_CHAIN index
        try:
            _working_model_idx = FREE_MODEL_CHAIN.index(next_model)
        except ValueError:
            _working_model_idx = 0
        logger.warning("Model %s failed — switching to %s", failed_model, next_model)
    else:
        logger.error("All free models exhausted. Staying on %s", failed_model)



def _extract_sql(raw: str) -> str:
    """Strip markdown fences, Qwen3 thinking traces, and whitespace from LLM output."""
    # Strip Qwen3 <think>...</think> reasoning blocks
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    # Remove ```sql ... ``` or ``` ... ```
    cleaned = re.sub(r"```(?:sql)?", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "").strip()
    return cleaned


# ── Node 1: Schema RAG ─────────────────────────────────────────────────────────
def schema_retriever_node(state: AgentState) -> AgentState:
    """
    Query ChromaDB to retrieve the most relevant table schemas
    for the user's question.
    """
    logger.info("[Node] schema_retriever")
    query = state["user_query"]

    schema_context = get_schema_context(
        query=query,
        n_results=SCHEMA_CHUNKS_TO_RETRIEVE,
    )

    state["schema_context"] = schema_context
    state["steps"].append({
        "node": "Schema Retriever",
        "thought": f"I need to find tables relevant to: '{query}'",
        "action": f"Queried ChromaDB vector store (top {SCHEMA_CHUNKS_TO_RETRIEVE} chunks)",
        "observation": f"Retrieved schema context ({len(schema_context)} chars):\n{schema_context[:400]}...",
    })
    return state


# ── Node 2: SQL Generator ──────────────────────────────────────────────────────
def sql_generator_node(state: AgentState) -> AgentState:
    """
    Generate (or regenerate with error context) a SQL query using the LLM.
    On the first call retry_count == 0, so we use the simple prompt.
    On retries we include the previous SQL and the error message.
    """
    logger.info("[Node] sql_generator (attempt %d)", state["retry_count"] + 1)
    llm = _get_llm()

    retry_count = state["retry_count"]
    is_retry = retry_count > 0

    if is_retry:
        human_prompt = SQL_GENERATOR_RETRY_PROMPT.format(
            schema_context=state["schema_context"],
            user_query=state["user_query"],
            retry_count=retry_count,
            previous_sql=state.get("generated_sql", ""),
            execution_error=state.get("execution_error", "Unknown error"),
        )
        thought = (
            f"My previous SQL failed with: '{state.get('execution_error', '')}'. "
            "Let me analyse the schema again and write a corrected query."
        )
    else:
        human_prompt = SQL_GENERATOR_FIRST_ATTEMPT_PROMPT.format(
            schema_context=state["schema_context"],
            user_query=state["user_query"],
        )
        thought = "I have the schema context. Let me generate SQL for the user's question."

    messages = [
        SystemMessage(content=SQL_GENERATOR_SYSTEM_PROMPT),
        HumanMessage(content=human_prompt),
    ]

    from openai import NotFoundError, RateLimitError
    response = None
    for _attempt in range(len(FREE_MODEL_CHAIN) + 1):
        try:
            response = llm.invoke(messages)
            break
        except (NotFoundError, RateLimitError) as e:
            failed_model = llm.model_name
            logger.warning("[sql_generator] %s on %s — trying next model", type(e).__name__, failed_model)
            _mark_model_failed(failed_model)
            llm = _get_llm()
    if response is None:
        raise RuntimeError("All free models exhausted. Cannot generate SQL.")

    sql = _extract_sql(response.content)

    state["generated_sql"] = sql
    state["execution_error"] = None  # reset error before next execution attempt
    state["steps"].append({
        "node": f"SQL Generator {'(retry #' + str(retry_count) + ')' if is_retry else ''}",
        "thought": thought,
        "action": f"Called {llm.model_name} to generate SQL",
        "observation": f"Generated SQL:\n{sql}",
    })
    return state


# ── Node 3: SQL Executor ───────────────────────────────────────────────────────
def sql_executor_node(state: AgentState) -> AgentState:
    """
    Execute the generated SQL against SQLite.
    On success: store rows in execution_result.
    On failure: store error string in execution_error and increment retry_count.
    """
    logger.info("[Node] sql_executor")
    sql = state["generated_sql"]

    try:
        rows, column_names = execute_sql(sql)
        state["execution_result"] = rows
        state["column_names"] = column_names
        state["execution_error"] = None
        state["steps"].append({
            "node": "SQL Executor",
            "thought": "Let me run this SQL against the database.",
            "action": f"Executed: {sql}",
            "observation": f"✅ Success — returned {len(rows)} row(s). "
                          f"Columns: {column_names}",
        })
    except Exception as e:
        error_msg = str(e)
        state["execution_result"] = None
        state["execution_error"] = error_msg
        state["retry_count"] = state.get("retry_count", 0) + 1
        state["steps"].append({
            "node": "SQL Executor",
            "thought": "Let me run this SQL against the database.",
            "action": f"Executed: {sql}",
            "observation": f"❌ Error (attempt {state['retry_count']}): {error_msg}",
        })
        logger.warning("[Node] sql_executor error: %s", error_msg)

    return state


# ── Node 4: Response Formatter ─────────────────────────────────────────────────
def response_formatter_node(state: AgentState) -> AgentState:
    """
    Converts the raw SQL result rows into a natural language answer.
    """
    logger.info("[Node] response_formatter")
    llm = _get_llm()

    rows = state.get("execution_result") or []
    row_count = len(rows)

    # Build a compact preview of results for the LLM (cap at 10 rows)
    preview_rows = rows[:10]
    result_preview = json.dumps(preview_rows, indent=2, default=str)

    prompt = RESPONSE_FORMATTER_PROMPT.format(
        user_query=state["user_query"],
        generated_sql=state["generated_sql"],
        row_count=row_count,
        result_preview=result_preview,
    )

    messages = [
        SystemMessage(content=RESPONSE_FORMATTER_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    from openai import NotFoundError, RateLimitError
    response = None
    for _attempt in range(len(FREE_MODEL_CHAIN) + 1):
        try:
            response = llm.invoke(messages)
            break
        except (NotFoundError, RateLimitError) as e:
            failed_model = llm.model_name
            logger.warning("[response_formatter] %s on %s — trying next model", type(e).__name__, failed_model)
            _mark_model_failed(failed_model)
            llm = _get_llm()
    if response is None:
        raise RuntimeError("All free models exhausted. Cannot format response.")

    answer = response.content.strip()

    state["final_answer"] = answer
    state["is_success"] = True
    state["steps"].append({
        "node": "Response Formatter",
        "thought": "I have the query results. Let me explain them in plain English.",
        "action": f"Formatted {row_count} rows into a natural language response",
        "observation": answer,
    })
    return state


# ── Node 5: Max Retry Handler ──────────────────────────────────────────────────
def max_retry_handler_node(state: AgentState) -> AgentState:
    """
    Called when the agent has hit MAX_RETRIES and still cannot produce
    a working SQL query. Returns a graceful error to the user.
    """
    logger.error("[Node] max_retry_handler — giving up after %d attempts", MAX_RETRIES)
    last_error = state.get("execution_error", "Unknown error")

    state["final_answer"] = (
        f"I was unable to generate a working SQL query after {MAX_RETRIES} attempts. "
        f"The last error was: {last_error}\n\n"
        "Suggestions:\n"
        "• Rephrase your question with more specific table or column names.\n"
        "• Check that the database schema has been indexed correctly.\n"
        "• Try a simpler version of the query first."
    )
    state["is_success"] = False
    state["steps"].append({
        "node": "Max Retry Handler",
        "thought": f"I've tried {MAX_RETRIES} times and keep getting errors.",
        "action": "Abort and return graceful error to user",
        "observation": state["final_answer"],
    })
    return state


# ── Conditional edge function ──────────────────────────────────────────────────
def should_retry_or_succeed(state: AgentState) -> str:
    """
    Router called after sql_executor_node.
    Returns one of: "success", "retry", "max_retries"
    """
    if state.get("execution_error") is None:
        return "success"
    if state.get("retry_count", 0) >= MAX_RETRIES:
        return "max_retries"
    return "retry"
