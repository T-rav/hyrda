"""Preparation node to parse research brief before supervision starts."""

import logging

from langchain_core.runnables import RunnableConfig

from profiler.nodes.supervisor import parse_research_brief_into_groups
from profiler.state import SupervisorState

logger = logging.getLogger(__name__)


def prepare_research(state: SupervisorState, config: RunnableConfig) -> dict:
    """Parse research brief into question groups.

    Runs once at the start to prepare the research plan.

    Args:
        state: Supervisor state with research_brief
        config: Runtime configuration

    Returns:
        Dict with all_question_groups

    """
    research_brief = state.get("research_brief", "")

    if not research_brief:
        logger.error("research_brief is missing")
        return {"error": "research brief not found"}

    # Parse into question groups
    all_question_groups = parse_research_brief_into_groups(research_brief, max_groups=12)

    logger.info(f"Prepared {len(all_question_groups)} question groups for research")

    return {
        "all_question_groups": all_question_groups,
        "research_iterations": 0,
        "completed_groups": [],
    }
