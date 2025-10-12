"""Graph builder for MEDDPICC coach workflow.

Builds and compiles the LangGraph workflow for MEDDPICC coaching.
"""

import logging

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


def build_meddpicc_coach() -> CompiledStateGraph:
    """Build and compile the MEDDPICC coach graph.

    The workflow is a simple linear pipeline:
    1. parse_notes: Clean and prepare sales call notes
    2. meddpicc_analysis: Structure into MEDDPICC format
    3. coaching_insights: Generate Maverick's coaching advice

    Returns:
        Compiled MEDDPICC coach graph
    """
    # Build graph with explicit input/output schemas
    coach_builder = StateGraph(
        MeddpiccAgentState,
        input=MeddpiccAgentInputState,
        output=MeddpiccAgentOutputState,
    )

    # Add nodes
    coach_builder.add_node("parse_notes", parse_notes)
    coach_builder.add_node("meddpicc_analysis", meddpicc_analysis)
    coach_builder.add_node("coaching_insights", coaching_insights)

    # Add edges - simple linear flow
    coach_builder.add_edge(START, "parse_notes")
    coach_builder.add_edge("parse_notes", "meddpicc_analysis")
    coach_builder.add_edge("meddpicc_analysis", "coaching_insights")
    coach_builder.add_edge("coaching_insights", END)

    # Compile and return
    compiled = coach_builder.compile()
    logger.info("MEDDPICC coach graph compiled successfully")
    return compiled
