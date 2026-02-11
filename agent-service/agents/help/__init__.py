"""Help Agent - List available agents and commands.

LangGraph-based agent that provides information about available bot agents,
filtered by user permissions.
"""

from .help_agent import help_agent

# Export for unified agent loader
Agent = help_agent

__all__ = ["Agent", "help_agent"]
