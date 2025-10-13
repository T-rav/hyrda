"""Graph builder for MEDDPICC coach workflow.

Builds and compiles the LangGraph workflow for MEDDPICC coaching
with persistent checkpointing for conversation continuity.
"""

import logging
import os

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.meddpicc_coach.nodes.check_input import check_input_completeness
from agents.meddpicc_coach.nodes.coaching_insights import coaching_insights
from agents.meddpicc_coach.nodes.meddpicc_analysis import meddpicc_analysis
from agents.meddpicc_coach.nodes.parse_notes import parse_notes
from agents.meddpicc_coach.state import (
    MeddpiccAgentInputState,
    MeddpiccAgentOutputState,
    MeddpiccAgentState,
)

logger = logging.getLogger(__name__)

# Global checkpointer instance for state persistence
# SQLite for simplicity and portability
_checkpointer = None


def get_checkpointer():
    """Get or create checkpointer for LangGraph state persistence.

    Uses MemorySaver for now - state persists during bot runtime.
    Thread tracking in Redis handles cross-restart persistence.

    Returns None when running in LangGraph API mode, as persistence
    is handled automatically by the platform.
    """
    # Don't use custom checkpointer in LangGraph API mode
    if os.getenv("LANGGRAPH_API_URL") or os.getenv("LANGSMITH_API_KEY"):
        logger.info("Running in LangGraph API mode - using platform persistence")
        return None

    global _checkpointer  # noqa: PLW0603
    if _checkpointer is None:
        _checkpointer = MemorySaver()
        logger.info("LangGraph checkpointer initialized (MemorySaver)")

    return _checkpointer


def route_after_check(state: MeddpiccAgentState) -> str:
    """Route based on whether input needs clarification.

    Returns:
        "clarify" if more info needed, "parse_notes" to proceed with analysis
    """
    if state.get("needs_clarification"):
        logger.info("Routing to clarification (insufficient input)")
        return "clarify"
    else:
        logger.info("Routing to parse_notes (sufficient input)")
        return "parse_notes"


async def clarify_node(state: MeddpiccAgentState) -> dict[str, str]:
    """Return clarification message to user and end workflow.

    Args:
        state: Current state with clarification_message

    Returns:
        Dict with final_response containing clarification questions
    """
    clarification_msg = state.get("clarification_message", "")
    logger.info(f"Clarification requested ({len(clarification_msg)} chars)")

    return {"final_response": clarification_msg}


def build_meddpicc_coach() -> CompiledStateGraph:
    """Build and compile the MEDDPICC coach graph.

    Conditional workflow with input checking:
        - check_input: Assess if notes have enough information
        - IF needs clarification → clarify (ask questions) → END
        - ELSE → parse_notes → meddpicc_analysis → coaching_insights → END

    This ensures users provide sufficient context before running full analysis.

    Returns:
        Compiled MEDDPICC coach graph
    """
    # Build graph with explicit input/output schemas
    coach_builder = StateGraph(
        MeddpiccAgentState,
        input_schema=MeddpiccAgentInputState,
        output_schema=MeddpiccAgentOutputState,
    )

    # Add nodes
    coach_builder.add_node("check_input", check_input_completeness)
    coach_builder.add_node("clarify", clarify_node)
    coach_builder.add_node("parse_notes", parse_notes)
    coach_builder.add_node("meddpicc_analysis", meddpicc_analysis)
    coach_builder.add_node("coaching_insights", coaching_insights)

    # Start with input checking
    coach_builder.add_edge(START, "check_input")

    # Route based on input completeness
    coach_builder.add_conditional_edges(
        "check_input",
        route_after_check,
        {
            "clarify": "clarify",
            "parse_notes": "parse_notes",
        },
    )

    # Clarification ends the workflow (user needs to provide more info)
    coach_builder.add_edge("clarify", END)

    # Full analysis flow
    coach_builder.add_edge("parse_notes", "meddpicc_analysis")
    coach_builder.add_edge("meddpicc_analysis", "coaching_insights")
    coach_builder.add_edge("coaching_insights", END)

    # Compile with checkpointer for state persistence (when not in LangGraph API mode)
    checkpointer = get_checkpointer()
    if checkpointer:
        compiled = coach_builder.compile(checkpointer=checkpointer)
        logger.info(
            "MEDDPICC coach graph compiled with conditional workflow and MemorySaver checkpointer"
        )
    else:
        compiled = coach_builder.compile()
        logger.info(
            "MEDDPICC coach graph compiled with conditional workflow (platform persistence)"
        )
    return compiled
