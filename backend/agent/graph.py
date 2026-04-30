"""
LangGraph state machine for the Text-to-SQL Self-Healing Agent.

Graph topology:
                    ┌─────────────────────┐
                    │   schema_retriever  │
                    └────────┬────────────┘
                             │
                    ┌────────▼────────────┐
               ┌───►│    sql_generator    │◄──────────────┐
               │    └────────┬────────────┘               │
               │             │                             │
               │    ┌────────▼────────────┐               │
               │    │    sql_executor     │               │
               │    └────────┬────────────┘               │
               │             │                             │
               │      ┌──────▼──────┐                     │
               │      │   router    │ (conditional edge)   │
               │      └──┬──────┬───┘                     │
               │         │      │                          │
               │      error  success                       │
               │   retry<3  │                              │
               └───────────┘   ┌───────────┐              │
                               │ formatter │               │
                               └─────┬─────┘              │
                               error │ retry≥3             │
                               ┌─────▼──────────┐         │
                               │ max_retry_hdlr │─────────┘
                               └────────────────┘
"""

from langgraph.graph import StateGraph, END

from backend.agent.state import AgentState
from backend.agent.nodes import (
    schema_retriever_node,
    sql_generator_node,
    sql_executor_node,
    response_formatter_node,
    max_retry_handler_node,
    should_retry_or_succeed,
)


def build_graph() -> StateGraph:
    """Construct and compile the LangGraph state machine."""
    workflow = StateGraph(AgentState)

    # ── Register nodes ─────────────────────────────────────────────────────────
    workflow.add_node("schema_retriever", schema_retriever_node)
    workflow.add_node("sql_generator", sql_generator_node)
    workflow.add_node("sql_executor", sql_executor_node)
    workflow.add_node("response_formatter", response_formatter_node)
    workflow.add_node("max_retry_handler", max_retry_handler_node)

    # ── Entry point ────────────────────────────────────────────────────────────
    workflow.set_entry_point("schema_retriever")

    # ── Static edges ───────────────────────────────────────────────────────────
    workflow.add_edge("schema_retriever", "sql_generator")
    workflow.add_edge("sql_generator", "sql_executor")
    workflow.add_edge("response_formatter", END)
    workflow.add_edge("max_retry_handler", END)

    # ── Conditional edge (self-healing loop) ───────────────────────────────────
    workflow.add_conditional_edges(
        "sql_executor",
        should_retry_or_succeed,
        {
            "success": "response_formatter",
            "retry": "sql_generator",        # ← the self-healing loop
            "max_retries": "max_retry_handler",
        },
    )

    return workflow.compile()


# Module-level compiled graph — import this everywhere
agent_graph = build_graph()


def run_agent(user_query: str) -> AgentState:
    """
    Entry point for running the agent.

    Args:
        user_query: Plain English question about the database.

    Returns:
        Final AgentState with steps trace, final_answer, and result rows.
    """
    initial_state: AgentState = {
        "user_query": user_query,
        "schema_context": "",
        "generated_sql": "",
        "execution_result": None,
        "execution_error": None,
        "retry_count": 0,
        "steps": [],
        "final_answer": "",
        "column_names": [],
        "is_success": False,
    }
    return agent_graph.invoke(initial_state)
