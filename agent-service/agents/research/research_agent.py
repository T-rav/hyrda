"""Main research agent module - LangGraph workflow instance.

For LangGraph Studio: This module exports a graph WITHOUT a checkpointer,
as LangGraph platform provides persistence automatically.
"""

import logging

from .nodes.graph_builder import build_research_agent

logger = logging.getLogger(__name__)

# Create the main graph instance (no checkpointer for production/Studio)
research_agent = build_research_agent()

logger.info("Research agent graph compiled successfully")
