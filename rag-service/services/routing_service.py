"""Routing service to determine if query needs agent processing."""

import logging
import re

logger = logging.getLogger(__name__)


class RoutingService:
    """Determines routing between agents and LLM based on query patterns."""

    # Agent command patterns - maps agent names to regex patterns
    AGENT_PATTERNS = {
        "profile": [
            r"^/profile",
            r"^profile\s",
            r"company profile",
            r"tell me about.*company",
        ],
        "meddic": [
            r"^/meddic",
            r"^meddic\s",
        ],
        "research": [
            r"^/research",
            r"^research\s",
            r"deep research",
        ],
        # Add more agent patterns as needed
    }

    def detect_agent(self, query: str) -> str | None:
        """
        Detect if query needs agent routing.

        Checks query against known agent patterns and returns the agent name
        if a match is found, otherwise returns None for standard LLM processing.

        Args:
            query: User query text

        Returns:
            Agent name if agent needed, None otherwise

        Examples:
            >>> routing_service = RoutingService()
            >>> routing_service.detect_agent("/profile acme corp")
            'profile'
            >>> routing_service.detect_agent("what is the weather?")
            None
        """
        if not query:
            return None

        # Normalize query
        query_lower = query.lower().strip()

        # Remove Slack markdown formatting (bold, italic, etc.)
        # Slack sends *bold* and _italic_ which breaks command parsing
        while query_lower and query_lower[0] in ["*", "_", "~"]:
            query_lower = query_lower[1:]
        while query_lower and query_lower[-1] in ["*", "_", "~"]:
            query_lower = query_lower[:-1]

        # Check each agent's patterns
        for agent_name, patterns in self.AGENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    logger.info(f"Routing to agent: {agent_name} (matched pattern: {pattern})")
                    return agent_name

        # No agent match - use standard LLM
        logger.debug(f"No agent routing for query: '{query[:50]}...'")
        return None

    def extract_query_after_command(self, query: str, agent_name: str) -> str:
        """
        Extract query text after agent command prefix.

        Args:
            query: Original query with command
            agent_name: Name of detected agent

        Returns:
            Query text without command prefix

        Examples:
            >>> routing_service = RoutingService()
            >>> routing_service.extract_query_after_command("/profile acme corp", "profile")
            'acme corp'
        """
        query_lower = query.lower().strip()

        # Try to remove command prefix
        for pattern in self.AGENT_PATTERNS.get(agent_name, []):
            match = re.match(pattern, query_lower)
            if match:
                # Remove matched prefix and return rest
                remaining = query[match.end():].strip()
                return remaining if remaining else query

        # If no pattern matched, return original
        return query


# Global instance
_routing_service: RoutingService | None = None


def get_routing_service() -> RoutingService:
    """Get or create global routing service instance."""
    global _routing_service  # noqa: PLW0603

    if _routing_service is None:
        _routing_service = RoutingService()

    return _routing_service
