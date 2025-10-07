"""Agent system for bot commands.

Agents are automatically registered when imported.
"""

from agents.help_agent import HelpAgent  # noqa: F401
from agents.meddic_agent import MeddicAgent  # noqa: F401

# Import agents to trigger auto-registration
from agents.profile_agent import ProfileAgent  # noqa: F401
from agents.registry import agent_registry
from agents.router import command_router

__all__ = [
    "agent_registry",
    "command_router",
    "ProfileAgent",
    "MeddicAgent",
    "HelpAgent",
]
