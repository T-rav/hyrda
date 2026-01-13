"""Research Agent - Entry point for system agent loader.

This is the main entry point that the SystemAgentLoader will import.
Exports the Agent wrapper with streaming support.
"""

from .agent_wrapper import ResearchAgentWrapper

# Export Agent for system agent loader (with streaming support)
Agent = ResearchAgentWrapper
