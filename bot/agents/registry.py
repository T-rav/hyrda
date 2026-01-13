"""Agent registry for bot command routing.

This module provides a registry pattern where agents can self-register
with their names and aliases, making it easy to add new agents without
modifying the router.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Registry for bot command agents.

    Agents register themselves with a primary name and optional aliases.
    The registry handles routing commands to the appropriate agent.
    """

    def __init__(self):
        """Initialize empty agent registry."""
        self._agents: dict[str, dict[str, Any]] = {}

    def register(
        self, name: str, agent_class: type, aliases: list[str] | None = None
    ) -> None:
        """Register an agent with its name and aliases.

        Args:
            name: Primary name for the agent (e.g., "profile", "meddic")
            agent_class: The agent class to instantiate
            aliases: Optional list of aliases (e.g., ["medic"] for "meddic")

        """
        name_lower = name.lower()
        aliases = aliases or []

        # Register primary name
        self._agents[name_lower] = {
            "name": name_lower,
            "agent_class": agent_class,
            "aliases": aliases,
            "is_primary": True,
        }

        logger.info(
            f"Registered agent '{name_lower}' with aliases: {aliases or 'none'}"
        )

        # Register each alias pointing to the primary name
        for alias in aliases:
            alias_lower = alias.lower()
            self._agents[alias_lower] = {
                "name": alias_lower,
                "agent_class": agent_class,
                "primary_name": name_lower,
                "is_primary": False,
            }
            logger.debug(f"Registered alias '{alias_lower}' -> '{name_lower}'")

    def get(self, name: str) -> dict[str, Any] | None:
        """Get agent info by name or alias.

        Args:
            name: Agent name or alias (case-insensitive)

        Returns:
            Agent info dict with 'agent_class' and metadata, or None if not found

        """
        return self._agents.get(name.lower())

    def list_agents(self) -> list[dict[str, Any]]:
        """List all registered agents (primary names only).

        Returns:
            List of agent info dicts with name, agent_class, and aliases

        """
        return [
            {
                "name": info["name"],
                "agent_class": info["agent_class"],
                "aliases": info["aliases"],
            }
            for info in self._agents.values()
            if info.get("is_primary", False)
        ]

    def is_registered(self, name: str) -> bool:
        """Check if an agent is registered.

        Args:
            name: Agent name or alias to check

        Returns:
            True if registered, False otherwise

        """
        return name.lower() in self._agents

    def get_primary_name(self, name: str) -> str | None:
        """Get the primary name for an agent or alias.

        Args:
            name: Agent name or alias

        Returns:
            Primary name if found, None otherwise

        """
        info = self.get(name)
        if not info:
            return None

        # If it's an alias, return the primary name
        if "primary_name" in info:
            return info["primary_name"]

        # Otherwise, it's already the primary name
        return info["name"]


# Global registry instance
agent_registry = AgentRegistry()
