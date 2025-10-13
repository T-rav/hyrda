"""Graph builder for MEDDPICC coach workflow.

Builds and compiles the LangGraph workflow for MEDDPICC coaching
with persistent checkpointing for conversation continuity.
"""

import logging

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
    """
    global _checkpointer  # noqa: PLW0603
    if _checkpointer is None:
        _checkpointer = MemorySaver()
        logger.info("LangGraph checkpointer initialized (MemorySaver)")

    return _checkpointer


def build_meddpicc_coach() -> CompiledStateGraph:
    """Build and compile the MEDDPICC coach graph.

    Simple linear workflow - always proceeds to full analysis:
        - parse_notes: Clean and prepare sales call notes
        - meddpicc_analysis: Structure into MEDDPICC format
        - coaching_insights: Generate Maverick's coaching advice

    If information is missing, the analysis will mark fields as
    "❌ Missing → Action" and coaching will guide next steps.

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

    # Simple linear flow - always proceed to analysis
    coach_builder.add_edge(START, "parse_notes")
    coach_builder.add_edge("parse_notes", "meddpicc_analysis")
    coach_builder.add_edge("meddpicc_analysis", "coaching_insights")
    coach_builder.add_edge("coaching_insights", END)

    # Compile with checkpointer for state persistence
    checkpointer = get_checkpointer()
    compiled = coach_builder.compile(checkpointer=checkpointer)
    logger.info(
        "MEDDPICC coach graph compiled with linear workflow (always proceeds to analysis)"
    )
    return compiled
