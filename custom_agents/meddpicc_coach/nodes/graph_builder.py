"""Graph builder for MEDDPICC coach workflow.

Builds and compiles the LangGraph workflow for MEDDPICC coaching
with persistent checkpointing for conversation continuity.
"""

import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from meddpicc_coach.nodes.check_input import check_input_completeness
from meddpicc_coach.nodes.coaching_insights import coaching_insights
from meddpicc_coach.nodes.followup_handler import followup_handler
from meddpicc_coach.nodes.meddpicc_analysis import meddpicc_analysis
from meddpicc_coach.nodes.parse_notes import parse_notes
from meddpicc_coach.nodes.qa_collector import qa_collector
from meddpicc_coach.state import (
    MeddpiccAgentInputState,
    MeddpiccAgentOutputState,
    MeddpiccAgentState,
)

logger = logging.getLogger(__name__)


def build_meddpicc_coach(checkpointer=None) -> CompiledStateGraph:
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
    coach_builder.add_node("check_input", check_input_completeness)
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

        # Priority 4: Has notes - check if they're sufficient for analysis
        logger.info("Notes provided - checking input completeness")
        return "check_input"

    def route_check_input(state: MeddpiccAgentState) -> str:
        """Route from check_input: to QA if needs clarification, to parse_notes if ready."""
        needs_clarification = state.get("needs_clarification", False)
        if needs_clarification:
            logger.info("Input needs clarification - routing to Q&A collector")
            return "qa_collector"
        logger.info("Input is sufficient - proceeding to parse_notes")
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
            "check_input": "check_input",
        },
    )

    coach_builder.add_conditional_edges(
        "check_input",
        route_check_input,
        {
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

    # Compile with optional checkpointer - LangGraph API handles persistence automatically
    # For standalone usage, checkpointer can be provided; for LangGraph server, use None
    if checkpointer is not None:
        logger.info(
            f"MEDDPICC coach graph compiled with checkpointer: {type(checkpointer).__name__}"
        )
    else:
        logger.info("MEDDPICC coach graph compiled without checkpointer (LangGraph API manages persistence)")

    return coach_builder.compile(checkpointer=checkpointer)
