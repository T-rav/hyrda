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
from agents.meddpicc_coach.nodes.followup_handler import followup_handler
from agents.meddpicc_coach.nodes.meddpicc_analysis import meddpicc_analysis
from agents.meddpicc_coach.nodes.parse_notes import parse_notes
from agents.meddpicc_coach.nodes.qa_collector import qa_collector
from agents.meddpicc_coach.state import (
    MeddpiccAgentInputState,
    MeddpiccAgentOutputState,
    MeddpiccAgentState,
)

logger = logging.getLogger(__name__)

# Detect if running in LangGraph API mode (Studio/Cloud)
_langgraph_api_mode = os.getenv("LANGGRAPH_API_URL") is not None

# Only use custom checkpointer when NOT in LangGraph API mode
# (LangGraph API provides its own persistence)
if _langgraph_api_mode:
    _checkpointer = None
    logger.info("LangGraph API mode detected - using platform persistence")
else:
    _checkpointer = MemorySaver()
    logger.info("LangGraph checkpointer initialized (MemorySaver)")


def build_meddpicc_coach() -> CompiledStateGraph:
    """Build and compile the MEDDPICC coach graph.

    Workflow with Q&A branch and follow-up questions:
        - START → route based on input
        - If in follow-up mode: followup_handler (loops for more questions) → END
        - If no notes: qa_collector (loops until all questions answered) → parse_notes
        - If has notes: parse_notes
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
    coach_builder.add_node("qa_collector", qa_collector)
    coach_builder.add_node("parse_notes", parse_notes)
    coach_builder.add_node("meddpicc_analysis", meddpicc_analysis)
    coach_builder.add_node("coaching_insights", coaching_insights)
    coach_builder.add_node("followup_handler", followup_handler)

    # Routing functions
    def route_start(state: MeddpiccAgentState) -> str:
        """Route from START based on whether we have notes, are in Q&A mode, or follow-up mode."""
        query = state.get("query", "").strip()
        question_mode = state.get("question_mode", False)
        followup_mode = state.get("followup_mode", False)

        # Priority 1: If in follow-up mode (after analysis), handle follow-up questions
        if followup_mode:
            logger.info(
                "In follow-up mode (from checkpoint) - routing to follow-up handler"
            )
            return "followup_handler"

        # Priority 2: If we're already in Q&A mode (from checkpoint), continue Q&A
        if question_mode:
            logger.info(
                "Already in Q&A mode (from checkpoint) - routing to Q&A collector"
            )
            return "qa_collector"

        # Priority 3: If no query and not in Q&A mode, start Q&A
        if not query:
            logger.info("No notes provided - routing to Q&A collector")
            return "qa_collector"

        # Priority 4: Has notes and not in Q&A/follow-up mode, go straight to analysis
        logger.info("Notes provided - routing directly to parse_notes")
        return "parse_notes"

    def route_qa(state: MeddpiccAgentState) -> str:
        """Route from Q&A: loop back if still collecting, proceed to analysis if done."""
        question_mode = state.get("question_mode", False)
        if question_mode:
            logger.info("Still in Q&A mode - returning response to user")
            return END  # Return to user to get next answer
        logger.info("Q&A complete - proceeding to parse_notes")
        return "parse_notes"

    # Build the graph with conditional routing
    coach_builder.add_conditional_edges(
        START,
        route_start,
        {
            "followup_handler": "followup_handler",
            "qa_collector": "qa_collector",
            "parse_notes": "parse_notes",
        },
    )

    coach_builder.add_conditional_edges(
        "qa_collector",
        route_qa,
        {
            END: END,
            "parse_notes": "parse_notes",
        },
    )

    # Linear flow after notes are ready
    coach_builder.add_edge("parse_notes", "meddpicc_analysis")
    coach_builder.add_edge("meddpicc_analysis", "coaching_insights")
    coach_builder.add_edge("coaching_insights", END)

    # Follow-up handler loops back to END for more questions
    coach_builder.add_edge("followup_handler", END)

    # Compile with checkpointer for state persistence
    # (only when not in LangGraph API mode)
    if _checkpointer:
        compiled = coach_builder.compile(checkpointer=_checkpointer)
        logger.info("MEDDPICC coach graph compiled with MemorySaver")
    else:
        compiled = coach_builder.compile()
        logger.info("MEDDPICC coach graph compiled (LangGraph API mode)")
    return compiled
