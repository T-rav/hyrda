"""Simple agent registry (HTTP-based, no local classes)."""

import logging

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Registry for agent metadata (no local classes)."""

    def __init__(self):
        """Initialize registry."""
        self.agents = {
            "research": {
                "name": "research",
                "display_name": "Research Agent",
                "description": "Deep research on any topic",
                "aliases": ["research", "investigate"],
            },
            "profile": {
                "name": "profile",
                "display_name": "Company Profile Agent",
                "description": "Generate company profiles",
                "aliases": ["profile", "company profile"],
            },
            "meddic": {
                "name": "meddic",
                "display_name": "MEDDIC Coach",
                "description": "Deal coaching and analysis",
                "aliases": ["meddic", "medic", "meddpicc"],
            },
            "help": {
                "name": "help",
                "display_name": "Help Agent",
                "description": "List available agents and help",
                "aliases": ["help", "agents"],
            },
        }

    def list_agents(self) -> list[dict]:
        """List all registered agents."""
        return list(self.agents.values())

    def get_agent(self, name: str) -> dict | None:
        """Get agent metadata by name."""
        return self.agents.get(name)


# Singleton instance
agent_registry = AgentRegistry()
