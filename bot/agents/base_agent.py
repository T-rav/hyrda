"""Base agent class for bot commands.

Provides common interface and utilities for all bot agents.
Each agent should implement its own LangGraph logic.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for bot command agents.

    Each agent should:
    1. Set class attributes: name, aliases, description
    2. Implement run() method with LangGraph logic
    3. Register itself with the agent registry
    """

    # Subclasses should override these
    name: str = ""
    aliases: list[str] = []
    description: str = ""

    def __init__(self):
        """Initialize agent."""
        if not self.name:
            raise ValueError(f"{self.__class__.__name__} must define 'name' attribute")

    @abstractmethod
    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        """Execute agent logic.

        Args:
            query: User query text
            context: Context dict with:
                - user_id: Slack user ID
                - channel: Slack channel ID
                - thread_ts: Thread timestamp (optional)
                - slack_service: SlackService instance
                - llm_service: LLMService instance (optional)

        Returns:
            Result dict with:
                - response: Response text to send to user
                - metadata: Optional metadata dict

        """
        pass

    def validate_context(self, context: dict[str, Any]) -> bool:
        """Validate required context fields.

        Args:
            context: Context dict to validate

        Returns:
            True if valid, False otherwise

        """
        required_fields = ["user_id", "channel", "slack_service"]

        for field in required_fields:
            if field not in context:
                logger.error(f"Missing required context field: {field}")
                return False

        return True

    def get_info(self) -> dict[str, Any]:
        """Get agent information.

        Returns:
            Dict with name, aliases, and description

        """
        return {
            "name": self.name,
            "aliases": self.aliases,
            "description": self.description,
        }

    def __repr__(self) -> str:
        """String representation."""
        aliases_str = f", aliases={self.aliases}" if self.aliases else ""
        return f"{self.__class__.__name__}(name={self.name}{aliases_str})"
