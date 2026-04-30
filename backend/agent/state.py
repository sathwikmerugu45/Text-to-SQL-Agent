from typing import TypedDict, List, Optional, Any


class StepTrace(TypedDict):
    """Single step in the agent's reasoning trace, shown in the UI."""
    node: str
    thought: str
    action: str
    observation: str


class AgentState(TypedDict):
    """
    Central state object passed between every LangGraph node.

    Lifecycle:
        user_query → schema_context → generated_sql → execution_result
        On error: execution_error is set, retry_count incremented,
                  loop back to sql_generator with full error context.
    """
    # Input
    user_query: str

    # Schema RAG output
    schema_context: str

    # SQL generation (updated on every retry)
    generated_sql: str

    # Execution output (mutually exclusive with error on each attempt)
    execution_result: Optional[List[dict]]
    execution_error: Optional[str]

    # Retry bookkeeping
    retry_count: int

    # Full reasoning trace for UI display (Thought → Action → Observation)
    steps: List[StepTrace]

    # Final formatted answer to return to the user
    final_answer: str
    column_names: List[str]

    # Did we succeed?
    is_success: bool
