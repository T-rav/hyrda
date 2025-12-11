"""Agent system for bot commands.

All business logic agents (profile, meddic, etc.) are now loaded from external_agents/.
Only system agents (help) are bundled in the image.
"""

from agents.help_agent import HelpAgent  # noqa: F401
from agents.registry import agent_registry
from agents.router import command_router

__all__ = [
    "agent_registry",
    "command_router",
    "HelpAgent",
]
