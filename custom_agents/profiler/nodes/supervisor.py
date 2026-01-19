"""Supervisor node for deterministic parallel research workflow.

Uses LangGraph's Send() pattern to launch parallel researchers.
"""

import logging
import re

from langchain_core.runnables import RunnableConfig
from langgraph.constants import Send
from langgraph.types import Command

from profiler.configuration import ProfileConfiguration
from profiler.state import SupervisorState

logger = logging.getLogger(__name__)


def parse_research_brief_into_groups(
    research_brief: str, max_groups: int = 10
) -> list[str]:
    """Parse research brief into question groups by section.

    Args:
        research_brief: Full research brief with sections
        max_groups: Maximum number of question groups to create

    Returns:
        List of question group strings

    """
    # Split by section headers (e.g., "1. **Section Name**", "## Section")
    section_pattern = r"(?:^|\n)(?:\d+\.|##)\s*\*?\*?([^*\n]+)\*?\*?"
    sections = re.split(section_pattern, research_brief)

    # Group sections into question groups
    question_groups = []
    current_group = []
    chars_in_group = 0
    max_chars_per_group = 2000  # Reasonable size for each researcher

    for i, section in enumerate(sections):
        if not section.strip():
            continue

        # If this looks like a header, start tracking
        if i % 2 == 1:  # Headers are at odd indices after split
            current_group.append(section.strip())
            chars_in_group += len(section)
        else:
            # This is section content
            if current_group:
                current_group.append(section.strip())
                chars_in_group += len(section)

                # If group is getting large, finalize it
                if chars_in_group > max_chars_per_group or len(question_groups) >= max_groups - 1:
                    question_groups.append("\n".join(current_group))
                    current_group = []
                    chars_in_group = 0

    # Add remaining group
    if current_group:
        question_groups.append("\n".join(current_group))

    # If no sections found, split by paragraphs
    if not question_groups:
        paragraphs = [p.strip() for p in research_brief.split("\n\n") if p.strip()]
        # Group paragraphs into chunks
        for i in range(0, len(paragraphs), 3):
            chunk = "\n\n".join(paragraphs[i:i + 3])
            if chunk:
                question_groups.append(chunk)

    # Limit to max_groups
    question_groups = question_groups[:max_groups]

    logger.info(f"Parsed research brief into {len(question_groups)} question groups")
    return question_groups


def supervisor(state: SupervisorState, config: RunnableConfig) -> dict:
    """Supervisor node - parses brief and sends parallel research tasks.

    Args:
        state: Current supervisor state
        config: Runtime configuration

    Returns:
        Dict with "send" key containing Send() list for parallel execution, or empty dict

    """
    configuration = ProfileConfiguration.from_runnable_config(config)
    research_iterations = state.get("research_iterations", 0)
    research_brief = state.get("research_brief", "")
    profile_type = state.get("profile_type", "company")
    focus_area = state.get("focus_area", "")
    completed_groups = list(state.get("completed_groups", []))

    # Validate research_brief exists
    if not research_brief:
        logger.error("research_brief is missing or empty in supervisor state")
        return {}

    logger.info(f"Supervisor iteration {research_iterations}")

    # Check iteration limit
    if research_iterations >= configuration.max_researcher_iterations:
        logger.info(
            f"Max supervisor iterations ({configuration.max_researcher_iterations}) reached"
        )
        return {}

    # Get question groups (prepared by prepare_research node)
    all_question_groups = state.get("all_question_groups", [])
    if not all_question_groups:
        logger.error("all_question_groups not found - prepare_research should have set this")
        return {}

    # Select question groups for this iteration
    remaining_groups = [g for g in all_question_groups if g not in completed_groups]

    if not remaining_groups:
        logger.info("All question groups completed")
        return {}

    # Take up to max_concurrent_research_units groups for this iteration
    groups_this_iteration = remaining_groups[: configuration.max_concurrent_research_units]
    logger.info(
        f"Processing {len(groups_this_iteration)} question groups in parallel "
        f"({len(remaining_groups)} remaining)"
    )

    # Create Send() commands for parallel execution
    sends = []
    for idx, question_group in enumerate(groups_this_iteration):
        sends.append(
            Send(
                "research_assistant",
                {
                    "question_group": question_group,
                    "profile_type": profile_type,
                    "focus_area": focus_area,
                    "task_id": f"research_{research_iterations}_{idx}",
                },
            )
        )

    logger.info(f"Dispatching {len(sends)} parallel Send() commands to research_assistant")

    return {"send": sends}
