"""Main research agent module - LangGraph workflow instance.

For LangGraph Studio: This module exports a graph WITHOUT a checkpointer,
as LangGraph platform provides persistence automatically.
"""

import logging

from ..metadata import agent_metadata
from .nodes.graph_builder import build_research_agent

logger = logging.getLogger(__name__)


# Export the agent builder function (callable)
@agent_metadata(
    display_name="Research Agent",
    description="Deep research agent for comprehensive company analysis",
    aliases=["research", "deep_research"],
    is_system=True,
)
def research_agent():
    """Build and return research agent graph."""
    return build_research_agent()


logger.info("Research agent builder loaded")
