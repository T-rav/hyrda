"""Main help agent module - LangGraph workflow instance.

Exports the compiled help agent graph for LangGraph API.
"""

import logging

from ..metadata import agent_metadata
from .nodes.graph_builder import build_help_agent

logger = logging.getLogger(__name__)


# Export the agent builder function (callable)
@agent_metadata(
    display_name="Help Agent",
    description="List available bot agents and their aliases (filtered by your access)",
    aliases=["help", "agents"],
    is_system=False,
)
def help_agent():
    """Build and return help agent graph."""
    return build_help_agent()


logger.info("Help agent builder loaded")
