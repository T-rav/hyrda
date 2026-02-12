"""Help Agent - Entry point for unified agent loader.

Provides information about available bot agents and their usage.
Exports the LangGraph CompiledStateGraph for API invocation.
"""

from .help_agent import help_agent

# Export for unified agent loader
# This is a LangGraph CompiledStateGraph, not a class
Agent = help_agent
