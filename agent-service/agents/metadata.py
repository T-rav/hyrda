"""Agent metadata decorator for auto-registration with control plane.

Usage:
    from agents.metadata import agent_metadata

    @agent_metadata(
        display_name="My Agent",
        description="Does cool stuff",
        aliases=["my", "cool"]
    )
    my_agent = StateGraph(...).compile()

    # For goal bots (autonomous scheduled agents):
    @agent_metadata(
        display_name="Prospect Finder",
        description="Finds new prospects",
        goal_bot=GoalBotConfig(
            schedule_type="interval",
            schedule_config={"interval_seconds": 86400},
        )
    )
    prospect_agent = StateGraph(...).compile()
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GoalBotConfig:
    """Configuration for a goal bot (autonomous scheduled agent).

    Goal bots run autonomously on a schedule, persist state between runs,
    and log milestones as they work toward their goal.
    """

    goal_prompt: str
    """The goal/objective for this bot to achieve. Required."""

    schedule_type: str = "interval"
    """Schedule type: 'cron' or 'interval'."""

    schedule_config: dict = field(default_factory=lambda: {"interval_seconds": 86400})
    """Schedule configuration. For cron: {"cron_expression": "0 9 * * *"}.
    For interval: {"interval_seconds": 3600}."""

    max_runtime_seconds: int = 3600
    """Maximum runtime per execution (1 hour default)."""

    max_iterations: int = 10
    """Maximum plan-execute-check iterations per run."""

    notification_channel: str | None = None
    """Slack channel for completion/failure notifications."""

    is_enabled: bool = True
    """Whether the bot is enabled by default."""

    is_paused: bool = False
    """Whether the bot is paused by default."""

    tools: list[str] = field(default_factory=list)
    """List of tool names this bot can use."""


def agent_metadata(
    display_name: str,
    description: str,
    aliases: list[str] | None = None,
    is_system: bool = False,
    goal_bot: GoalBotConfig | None = None,
):
    """Decorator to attach metadata to agent graphs.

    Args:
        display_name: Human-readable name for UI
        description: What the agent does
        aliases: Alternative names for invoking the agent
        is_system: If True, agent cannot be disabled
        goal_bot: If provided, registers this agent as a goal bot with
                  the specified configuration for autonomous scheduled execution

    Returns:
        Decorator function
    """

    def decorator(agent_graph: Any) -> Any:
        """Attach metadata to agent graph."""
        metadata = {
            "display_name": display_name,
            "description": description,
            "aliases": aliases or [],
            "is_system": is_system,
        }

        # Add goal bot configuration if provided
        if goal_bot is not None:
            metadata["goal_bot"] = {
                "goal_prompt": goal_bot.goal_prompt,
                "schedule_type": goal_bot.schedule_type,
                "schedule_config": goal_bot.schedule_config,
                "max_runtime_seconds": goal_bot.max_runtime_seconds,
                "max_iterations": goal_bot.max_iterations,
                "notification_channel": goal_bot.notification_channel,
                "is_enabled": goal_bot.is_enabled,
                "is_paused": goal_bot.is_paused,
                "tools": goal_bot.tools,
            }

        agent_graph.__agent_metadata__ = metadata
        return agent_graph

    return decorator
