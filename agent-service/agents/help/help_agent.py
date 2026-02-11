"""Main help agent module - LangGraph workflow instance.

Exports the compiled help agent graph for LangGraph API.
"""

import logging

from .nodes.graph_builder import build_help_agent

logger = logging.getLogger(__name__)

# Create the main graph instance (no checkpointer for production/Studio)
help_agent = build_help_agent()

logger.info("Help agent graph compiled successfully")
