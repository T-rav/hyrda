"""Goal Executor Subgraph - OpenClaw-style goal-driven agent.

This is a REUSABLE SUBGRAPH, not a standalone agent. It implements
an autonomous goal-driven execution loop:

1. Plan - LLM decomposes goal into executable steps with dependencies
2. Execute - Run steps (potentially in parallel) using provided tools
3. Check - Evaluate progress, decide whether to continue or complete
4. Loop - Continue until goal achieved or max iterations reached

Usage:
    from agents.goal_executor import build_goal_executor

    # Create with custom tools
    graph = build_goal_executor(
        tools=[my_tool1, my_tool2],
        system_prompt="Custom executor prompt"
    )

    # Use in your agent
    result = await graph.ainvoke({"goal": "Research competitors"})

Designed to be embedded in other agents (like prospect_research)
that provide their specific tools and goal prompts.
"""

import logging

from .nodes.graph_builder import build_goal_executor

logger = logging.getLogger(__name__)

# Re-export for convenience
__all__ = ["build_goal_executor"]

logger.info("Goal executor subgraph loaded")
