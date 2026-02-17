"""Goal Executor Subgraph - OpenClaw-style goal-driven agent.

This is a REUSABLE SUBGRAPH, not a standalone agent. It implements
a goal-driven execution loop:

1. Plan - LLM decomposes goal into executable steps with dependencies
2. Execute - Run steps in parallel (respecting dependencies)
3. Check - Evaluate progress, decide next steps
4. Loop - Continue until goal achieved or max iterations reached

Key concepts:
- Steps have dependencies and run in parallel up to maxParallel limit
- Each step can invoke tools/skills provided by the parent agent
- Progress and milestones are logged throughout execution
- State persists between runs for long-running goals

Usage:
    from agents.goal_executor import build_goal_executor

    graph = build_goal_executor(
        tools=[my_tool1, my_tool2],
        system_prompt="Custom prompt"
    )
"""

from .nodes.graph_builder import build_goal_executor

__all__ = ["build_goal_executor"]
