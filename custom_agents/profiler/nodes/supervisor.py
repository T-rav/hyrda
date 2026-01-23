"""Supervisor node for deterministic parallel research workflow.

Uses LangGraph's Send() pattern to launch parallel researchers.
"""

import logging
import re

import asyncio

from langchain_core.runnables import RunnableConfig

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


async def supervisor(state: SupervisorState, config: RunnableConfig) -> dict:
    """Supervisor node - runs parallel research tasks using asyncio.gather().

    Args:
        state: Current supervisor state
        config: Runtime configuration

    Returns:
        Dict with accumulated research notes and updated state

    """
    from profiler.nodes.graph_builder import build_researcher_subgraph
    configuration = ProfileConfiguration.from_runnable_config(config)
    research_iterations = state.get("research_iterations", 0)
    research_brief = state.get("research_brief", "")
    profile_type = state.get("profile_type", "company")
    focus_area = state.get("focus_area", "")
    completed_groups = list(state.get("completed_groups", []))

    logger.info("=" * 80)
    logger.info(f"SUPERVISOR NODE CALLED - research_brief length: {len(research_brief)}")
    logger.info(f"Supervisor state keys: {list(state.keys())}")
    logger.info("=" * 80)

    # Validate research_brief exists
    if not research_brief:
        logger.error("research_brief is missing or empty in supervisor state")
        return {}  # supervisor_debug: "no_research_brief"}

    logger.info(f"Supervisor iteration {research_iterations}")

    # Check iteration limit
    if research_iterations >= configuration.max_researcher_iterations:
        logger.info(
            f"Max supervisor iterations ({configuration.max_researcher_iterations}) reached"
        )
        return {}  # supervisor_debug: "max_iterations_reached"}

    # Get question groups (prepared by prepare_research node)
    all_question_groups = state.get("all_question_groups", [])
    logger.info(f"Supervisor found {len(all_question_groups)} question groups")
    logger.info(f"Completed groups: {len(completed_groups)}")

    if not all_question_groups:
        logger.error("all_question_groups not found - prepare_research should have set this")
        return {}  # supervisor_debug: "no_question_groups"}

    # Select question groups for this iteration
    remaining_groups = [g for g in all_question_groups if g not in completed_groups]
    logger.info(f"Remaining groups: {len(remaining_groups)}")

    if not remaining_groups:
        logger.info("All question groups completed")
        return {}  # supervisor_debug: "no_remaining_groups"}

    # Take up to max_concurrent_research_units groups for this iteration
    groups_this_iteration = remaining_groups[: configuration.max_concurrent_research_units]
    logger.info(
        f"Processing {len(groups_this_iteration)} question groups in parallel "
        f"({len(remaining_groups)} remaining)"
    )

    # Build researcher subgraph once
    researcher_graph = build_researcher_subgraph()

    # Run researchers in parallel with asyncio.gather()
    tasks = []
    for idx, question_group in enumerate(groups_this_iteration):
        task = researcher_graph.ainvoke(
            {
                "research_topic": question_group,
                "profile_type": profile_type,
                "focus_area": focus_area,
                "researcher_messages": [],  # Initialize empty message list
                "tool_call_iterations": 0,  # Initialize iteration counter
            },
            config,
        )
        tasks.append(task)

    logger.info(f"Executing {len(tasks)} parallel research tasks with asyncio.gather()")

    # Execute all research tasks in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Accumulate results
    all_notes = []
    all_raw_notes = []
    completed_this_iteration = []

    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Research task {idx} failed: {result}")
            continue

        compressed = result.get("compressed_research", "")
        raw = result.get("raw_notes", [])

        logger.info(f"Task {idx} result: compressed={len(compressed)} chars, raw_notes={len(raw)} items")
        if raw:
            logger.info(f"Raw notes sample: {raw[0][:200] if raw else 'empty'}...")

        if compressed:
            all_notes.append(compressed)
        if raw:
            all_raw_notes.extend(raw)

        completed_this_iteration.append(groups_this_iteration[idx])

    logger.info(
        f"Completed {len(completed_this_iteration)} research tasks, "
        f"collected {len(all_notes)} notes, {len(all_raw_notes)} raw notes"
    )

    return {
        "notes": all_notes,
        "raw_notes": all_raw_notes,
        "completed_groups": completed_this_iteration,
    }
