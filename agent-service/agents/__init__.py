"""Agent system for bot commands.

All business logic agents (profile, meddic, etc.) are now loaded from external_agents/.
System agents (help, research) are loaded from agents/system/.
"""

from agents.registry import agent_registry
from agents.router import command_router

__all__ = [
    "agent_registry",
    "command_router",
]
