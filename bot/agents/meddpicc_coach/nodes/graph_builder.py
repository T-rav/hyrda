"""Graph builder for MEDDPICC coach workflow.

Builds and compiles the LangGraph workflow for MEDDPICC coaching
with persistent checkpointing for conversation continuity.
"""

import logging
import os

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

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


def build_meddpicc_coach() -> CompiledStateGraph:
    """Build and compile the MEDDPICC coach graph.

    Direct analysis workflow:
        - parse_notes → meddpicc_analysis → coaching_insights → END

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
    coach_builder.add_node("parse_notes", parse_notes)
    coach_builder.add_node("meddpicc_analysis", meddpicc_analysis)
    coach_builder.add_node("coaching_insights", coaching_insights)

    # Direct flow - no input checking
    coach_builder.add_edge(START, "parse_notes")
    coach_builder.add_edge("parse_notes", "meddpicc_analysis")
    coach_builder.add_edge("meddpicc_analysis", "coaching_insights")
    coach_builder.add_edge("coaching_insights", END)

    # Compile with checkpointer for state persistence (when not in LangGraph API mode)
    checkpointer = get_checkpointer()
    if checkpointer:
        compiled = coach_builder.compile(checkpointer=checkpointer)
        logger.info("MEDDPICC coach graph compiled with MemorySaver checkpointer")
    else:
        compiled = coach_builder.compile()
        logger.info("MEDDPICC coach graph compiled (platform persistence)")
    return compiled
