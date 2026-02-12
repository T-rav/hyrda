"""Agent metadata decorator for auto-registration with control plane.

Usage:
    from agents.metadata import agent_metadata

    @agent_metadata(
        display_name="My Agent",
        description="Does cool stuff",
        aliases=["my", "cool"]
    )
    my_agent = StateGraph(...).compile()
"""

from typing import Any


def agent_metadata(
    display_name: str,
    description: str,
    aliases: list[str] | None = None,
    is_system: bool = False,
):
    """Decorator to attach metadata to agent graphs.

    Args:
        display_name: Human-readable name for UI
        description: What the agent does
        aliases: Alternative names for invoking the agent
        is_system: If True, agent cannot be disabled

    Returns:
        Decorator function
    """

    def decorator(agent_graph: Any) -> Any:
        """Attach metadata to agent graph."""
        agent_graph.__agent_metadata__ = {
            "display_name": display_name,
            "description": description,
            "aliases": aliases or [],
            "is_system": is_system,
        }
        return agent_graph

    return decorator
