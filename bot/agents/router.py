"""Simple command router for HTTP-based agents."""

import logging
import re

logger = logging.getLogger(__name__)


class CommandRouter:
    """Routes commands to agent names (no local classes)."""

    def __init__(self):
        """Initialize router with agent mappings."""
        # Map agent names to their aliases
        self.agent_aliases = {
            "research": ["research", "deep research", "investigate"],
            "profile": ["profile", "company profile", "research company"],
            "meddic": ["meddic", "medic", "meddpicc", "deal analysis"],
            "help": ["help", "agents", "list agents"],
        }

        # Reverse map: alias -> primary name
        self.alias_to_primary = {}
        for primary, aliases in self.agent_aliases.items():
            for alias in aliases:
                self.alias_to_primary[alias.lower()] = primary

    def route(self, text: str) -> tuple[dict | None, str, str | None]:
        """Route text to agent name.

        Args:
            text: User input text

        Returns:
            (agent_info, query, primary_name)
            - agent_info: Dict with agent metadata (or None if no match)
            - query: Extracted query text
            - primary_name: Primary agent name (or None if no match)
        """
        text_lower = text.lower().strip()

        # Check for direct agent mentions
        for alias, primary in self.alias_to_primary.items():
            # Look for patterns like "@agent query" or "agent: query"
            patterns = [
                rf"^@?{re.escape(alias)}\s+(.+)$",  # @agent query
                rf"^{re.escape(alias)}:\s*(.+)$",  # agent: query
                rf"^{re.escape(alias)}\s+(.+)$",  # agent query
            ]

            for pattern in patterns:
                match = re.match(pattern, text_lower)
                if match:
                    query = match.group(1).strip()
                    agent_info = {"name": primary}
                    logger.info(
                        f"Matched agent '{primary}' via alias '{alias}' with query: '{query}'"
                    )
                    return agent_info, query, primary

        # No agent found
        return None, text, None


# Singleton instance
command_router = CommandRouter()
