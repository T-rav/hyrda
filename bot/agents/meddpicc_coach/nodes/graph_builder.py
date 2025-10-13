"""Graph builder for MEDDPICC coach workflow.

Builds and compiles the LangGraph workflow for MEDDPICC coaching
with persistent checkpointing for conversation continuity.
"""

import asyncio
import logging
import os
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver

try:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
except (ImportError, ModuleNotFoundError):
    # Handle missing module for tests or older langgraph versions
    AsyncSqliteSaver = None  # type: ignore
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

# Global checkpointer instance for state persistence
_checkpointer = None
_checkpointer_setup_done = False
_checkpointer_lock = asyncio.Lock()


def _init_checkpointer():
    """Initialize checkpointer synchronously (for module load time).

    Creates the checkpointer object but doesn't call async setup() yet.
    """
    # Don't use custom checkpointer in LangGraph API mode
    if os.getenv("LANGGRAPH_API_URL"):
        logger.info("Running in LangGraph API mode - using platform persistence")
        return None

    environment = os.getenv("ENVIRONMENT", "development").lower()

    if environment in ("staging", "production") and AsyncSqliteSaver:
        # Use persistent SQLite storage for production
        data_dir = Path(os.getenv("DATA_DIR", "./data"))
        data_dir.mkdir(parents=True, exist_ok=True)

        db_path = data_dir / "langgraph_checkpoints.db"
        logger.info(
            f"Initializing persistent checkpointer for {environment}: {db_path}"
        )

        # Create AsyncSqliteSaver synchronously
        checkpointer = AsyncSqliteSaver.from_conn_string(str(db_path))
        logger.info(
            f"LangGraph checkpointer created (AsyncSqliteSaver - {environment})"
        )
        return checkpointer
    else:
        # Use in-memory storage for development or when AsyncSqliteSaver not available
        logger.info("LangGraph checkpointer initialized (MemorySaver - development)")
        return MemorySaver()


async def get_checkpointer():
    """Get checkpointer and ensure it's set up.

    Environment-aware storage:
    - Development: MemorySaver (in-memory, fast)
    - Staging/Production: AsyncSqliteSaver (persistent SQLite database)

    Returns None when running in LangGraph API mode, as persistence
    is handled automatically by the platform.
    """
    global _checkpointer_setup_done  # noqa: PLW0603

    if _checkpointer is None:
        return None

    # Ensure async setup is called for AsyncSqliteSaver (if available)
    if (
        not _checkpointer_setup_done
        and AsyncSqliteSaver is not None
        and hasattr(_checkpointer, "setup")
    ):
        try:
            if isinstance(_checkpointer, AsyncSqliteSaver):
                async with _checkpointer_lock:
                    if (
                        not _checkpointer_setup_done
                    ):  # Double-check after acquiring lock
                        await _checkpointer.setup()
                        _checkpointer_setup_done = True
                        logger.info("✅ AsyncSqliteSaver setup complete")
        except (TypeError, NameError):
            # isinstance can fail when AsyncSqliteSaver is mocked/unavailable, just skip
            pass

    return _checkpointer


# Initialize checkpointer at module load time (synchronous)
_checkpointer = _init_checkpointer()


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
    # Use the global _checkpointer initialized at module load
    if _checkpointer:
        compiled = coach_builder.compile(checkpointer=_checkpointer)
        checkpointer_type = type(_checkpointer).__name__
        logger.info(f"MEDDPICC coach graph compiled with {checkpointer_type}")
    else:
        compiled = coach_builder.compile()
        logger.info("MEDDPICC coach graph compiled (platform persistence)")
    return compiled
