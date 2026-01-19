"""Research assistant node for parallel research execution.

Single node that gets invoked multiple times in parallel via Send().
"""

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from profiler.state import SupervisorState

logger = logging.getLogger(__name__)


async def research_assistant(
    state: SupervisorState, config: RunnableConfig
) -> dict[str, Any]:
    """Execute a single research task.

    This node is invoked N times in parallel via Send() from supervisor.

    Args:
        state: State with question_group and metadata
        config: Runtime configuration

    Returns:
        Dict with compressed_research and raw_notes to be aggregated

    """
    from profiler.nodes.graph_builder import build_researcher_subgraph

    question_group = state.get("question_group", "")
    profile_type = state.get("profile_type", "company")
    focus_area = state.get("focus_area", "")
    task_id = state.get("task_id", "unknown")

    logger.info(f"Research assistant {task_id} starting: {question_group[:100]}...")

    try:
        # Build and invoke researcher subgraph
        researcher_graph = build_researcher_subgraph()

        result = await researcher_graph.ainvoke(
            {
                "research_topic": question_group,
                "profile_type": profile_type,
                "focus_area": focus_area,
            },
            config,
        )

        compressed = result.get("compressed_research", "")
        raw = result.get("raw_notes", [])

        logger.info(
            f"Research assistant {task_id} completed: "
            f"{len(compressed)} chars compressed, {len(raw)} raw notes"
        )

        # Return results - reducer will accumulate notes and raw_notes
        return {
            "notes": [compressed] if compressed else [],
            "raw_notes": raw if raw else [],
            "completed_groups": [question_group],
        }

    except Exception as e:
        logger.error(f"Research assistant {task_id} failed: {e}")
        return {
            "notes": [f"Research failed: {str(e)}"],
            "raw_notes": [],
            "completed_groups": [question_group],
        }
