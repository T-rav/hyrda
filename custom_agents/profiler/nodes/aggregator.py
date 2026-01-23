"""Aggregator node for collecting parallel research results.

Collects results from parallel research_assistant invocations.
"""

import logging

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from profiler.configuration import ProfileConfiguration
from profiler.state import SupervisorState

logger = logging.getLogger(__name__)


def aggregator(state: SupervisorState, config: RunnableConfig) -> Command[str]:
    """Aggregate results from parallel research assistants.

    The reducer has already accumulated notes/raw_notes from all parallel executions.
    This node just checks progress and decides whether to continue or end.

    Args:
        state: State with accumulated results from research_assistants
        config: Runtime configuration

    Returns:
        Command to continue to supervisor or end

    """
    configuration = ProfileConfiguration.from_runnable_config(config)

    # Get progress tracking (already updated by reducer)
    notes = state.get("notes", [])
    raw_notes = state.get("raw_notes", [])
    all_question_groups = state.get("all_question_groups", [])
    completed_groups = state.get("completed_groups", [])
    research_iterations = state.get("research_iterations", 0)

    logger.info(f"Aggregator called! State keys: {list(state.keys())}")
    logger.info(
        f"Aggregator: {len(completed_groups)}/{len(all_question_groups)} groups completed, "
        f"{len(notes)} research notes collected"
    )
    logger.info(f"All question groups: {len(all_question_groups)}")

    # Determine if we should continue
    remaining_groups = [g for g in all_question_groups if g not in completed_groups]

    if remaining_groups and research_iterations + 1 < configuration.max_researcher_iterations:
        # More work to do, continue to supervisor
        logger.info(
            f"{len(remaining_groups)} groups remaining. Continuing to next iteration."
        )
        return Command(
            goto="supervisor",
            update={
                "research_iterations": research_iterations + 1,
            },
        )
    else:
        # All done, end supervision - return notes and raw_notes to parent graph
        logger.info(
            f"Research complete. Processed {len(completed_groups)} question groups, "
            f"gathered {len(notes)} research notes."
        )
        logger.info(f"AGGREGATOR ENDING: Returning {len(notes)} notes and {len(raw_notes)} raw_notes to parent graph")
        if notes:
            logger.info(f"First note preview: {notes[0][:200]}...")
        if raw_notes:
            logger.info(f"First raw note preview: {raw_notes[0][:200]}...")

        # Return the accumulated research data to parent graph via output schema
        return Command(
            goto="__end__",
            update={
                "notes": notes,
                "raw_notes": raw_notes,
            }
        )
