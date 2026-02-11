"""Main help agent module - LangGraph workflow instance.

Exports the compiled help agent graph for LangGraph API.
"""

import logging

from ..metadata import agent_metadata
from .nodes.graph_builder import build_help_agent

logger = logging.getLogger(__name__)


# Create the main graph instance (no checkpointer for production/Studio)
@agent_metadata(
    display_name="Help Agent",
    description="List available bot agents and their aliases (filtered by your access)",
    aliases=["help", "agents"],
    is_system=False,
)
def _build():
    """Build and return help agent graph."""
    return build_help_agent()


help_agent = _build()

logger.info("Help agent graph compiled successfully")
