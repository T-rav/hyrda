"""Supervisor node for deterministic parallel research workflow.

Parses research brief into question groups and launches parallel researchers
without LLM tool calling - fully deterministic parallelization.
"""

import asyncio
import logging
import re
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.graph.state import CompiledStateGraph
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


async def supervisor(state: SupervisorState, config: RunnableConfig) -> Command[str]:
    """Supervisor node - deterministically launches parallel researchers.

    Args:
        state: Current supervisor state
        config: Runtime configuration

    Returns:
        Command to END

    """
    from profiler.nodes.graph_builder import build_researcher_subgraph

    configuration = ProfileConfiguration.from_runnable_config(config)
    research_iterations = state.get("research_iterations", 0)
    research_brief = state.get("research_brief", "")
    notes = list(state.get("notes", []))
    raw_notes = list(state.get("raw_notes", []))
    profile_type = state.get("profile_type", "company")
    focus_area = state.get("focus_area", "")
    completed_groups = list(state.get("completed_groups", []))

    # Validate research_brief exists
    if not research_brief:
        logger.error("research_brief is missing or empty in supervisor state")
        return Command(
            goto=END,
            update={"final_report": "Error: research brief not found in state"},
        )

    logger.info(f"Supervisor iteration {research_iterations}")

    # Check iteration limit
    if research_iterations >= configuration.max_researcher_iterations:
        logger.info(
            f"Max supervisor iterations ({configuration.max_researcher_iterations}) reached"
        )
        return Command(goto=END, update={})

    # Parse research brief into question groups (only on first iteration)
    if research_iterations == 0:
        all_question_groups = parse_research_brief_into_groups(
            research_brief, max_groups=12
        )
        logger.info(f"Total question groups identified: {len(all_question_groups)}")
    else:
        # On follow-up iterations, use stored groups
        all_question_groups = state.get("all_question_groups", [])
        if not all_question_groups:
            logger.info("No remaining question groups - research complete")
            return Command(goto=END, update={})

    # Select question groups for this iteration
    remaining_groups = [g for g in all_question_groups if g not in completed_groups]

    if not remaining_groups:
        logger.info("All question groups completed")
        return Command(goto=END, update={})

    # Take up to max_concurrent_research_units groups for this iteration
    groups_this_iteration = remaining_groups[: configuration.max_concurrent_research_units]
    logger.info(
        f"Processing {len(groups_this_iteration)} question groups in parallel "
        f"({len(remaining_groups)} remaining)"
    )

    # Build researcher subgraph
    researcher_graph = build_researcher_subgraph()

    # Create tasks for parallel execution
    research_tasks = []
    for idx, question_group in enumerate(groups_this_iteration):
        task = execute_researcher(
            researcher_graph,
            question_group,
            profile_type,
            focus_area,
            f"research_{research_iterations}_{idx}",
            config,
        )
        research_tasks.append(task)

    # Execute in parallel
    logger.info(f"Launching {len(research_tasks)} researchers in parallel")
    research_results = await asyncio.gather(*research_tasks)

    # Process results
    for result in research_results:
        if result["compressed_research"]:
            notes.append(result["compressed_research"])
        if result["raw_notes"]:
            raw_notes.extend(result["raw_notes"])

    # Mark groups as completed
    completed_groups.extend(groups_this_iteration)

    # Determine if we should continue
    remaining_after_this = [g for g in all_question_groups if g not in completed_groups]

    if remaining_after_this and research_iterations + 1 < configuration.max_researcher_iterations:
        # More groups to process, continue
        logger.info(
            f"Completed {len(completed_groups)}/{len(all_question_groups)} groups. "
            f"Continuing to next iteration."
        )
        return Command(
            goto="supervisor",
            update={
                "research_iterations": research_iterations + 1,
                "notes": notes,
                "raw_notes": raw_notes,
                "completed_groups": completed_groups,
                "all_question_groups": all_question_groups,
            },
        )
    else:
        # All done
        logger.info(
            f"Research complete. Processed {len(completed_groups)} question groups, "
            f"gathered {len(notes)} research notes."
        )
        return Command(
            goto=END,
            update={
                "notes": notes,
                "raw_notes": raw_notes,
                "completed_groups": completed_groups,
            },
        )


async def execute_researcher(
    researcher_graph: CompiledStateGraph,
    research_topic: str,
    profile_type: str,
    focus_area: str,
    task_id: str,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Execute a single researcher task.

    Args:
        researcher_graph: Compiled researcher subgraph
        research_topic: Research questions for this researcher
        profile_type: Type of profile
        focus_area: Optional focus area
        task_id: Unique task identifier
        config: Runtime configuration

    Returns:
        Dict with compressed_research and raw_notes

    """
    logger.info(f"Researcher {task_id} starting: {research_topic[:100]}...")

    try:
        # Invoke researcher subgraph
        result = await researcher_graph.ainvoke(
            {
                "research_topic": research_topic,
                "profile_type": profile_type,
                "focus_area": focus_area,
            },
            config,
        )

        compressed = result.get("compressed_research", "")
        raw = result.get("raw_notes", [])

        logger.info(
            f"Researcher {task_id} completed: "
            f"{len(compressed)} chars compressed, {len(raw)} raw notes"
        )

        return {
            "compressed_research": compressed,
            "raw_notes": raw,
        }

    except Exception as e:
        logger.error(f"Researcher {task_id} failed: {e}")
        return {
            "compressed_research": f"Research failed: {str(e)}",
            "raw_notes": [],
        }
