"""Router for bot agent commands.

This module provides command parsing and routing to registered agents.
The router is separate from agent implementations, making it easy to
swap routing logic in the future.
"""

import logging
import re
from typing import Any

from agents.registry import agent_registry

logger = logging.getLogger(__name__)


class CommandRouter:
    """Router for parsing and routing bot commands to agents."""

    def __init__(self, registry=None):
        """Initialize router with agent registry.

        Args:
            registry: AgentRegistry instance (defaults to global registry)
        """
        self.registry = registry or agent_registry

    def parse_command(self, text: str) -> tuple[str | None, str]:
        """Parse bot command from message text.

        Extracts command name and query from messages like:
        - "-profile tell me about Charlotte"
        - "-meddic analyze this deal"

        Args:
            text: Message text to parse

        Returns:
            Tuple of (command_name, query) or (None, "") if no command found
        """
        # Match pattern: -command rest of text
        match = re.match(r"^-(\w+)\s*(.*)", text.strip(), re.IGNORECASE)

        if not match:
            return None, ""

        command_name = match.group(1).lower()
        query = match.group(2).strip()

        return command_name, query

    def route(self, text: str) -> tuple[dict[str, Any] | None, str, str | None]:
        """Parse command and route to appropriate agent.

        Args:
            text: Message text containing bot command

        Returns:
            Tuple of (agent_info, query, primary_name):
            - agent_info: Dict with agent_class and metadata, or None if not found
            - query: Parsed query text
            - primary_name: Primary name of agent (resolves aliases)
        """
        command_name, query = self.parse_command(text)

        if not command_name:
            logger.debug("No command found in text")
            return None, "", None

        # Check if command is registered
        if not self.registry.is_registered(command_name):
            logger.debug(f"Command '{command_name}' not registered")
            return None, query, None

        # Get agent info and resolve to primary name
        agent_info = self.registry.get(command_name)
        primary_name = self.registry.get_primary_name(command_name)

        logger.info(f"Routing command '-{command_name}' to agent '{primary_name}'")

        return agent_info, query, primary_name

    def list_available_commands(self) -> list[str]:
        """List all available bot commands.

        Returns:
            List of command names (primary names only)
        """
        agents = self.registry.list_agents()
        return [agent["name"] for agent in agents]


# Global router instance
command_router = CommandRouter()
