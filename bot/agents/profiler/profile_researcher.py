"""LangGraph workflow for company profile deep research.

Implements a hierarchical research system with supervisor and researcher subgraphs.
All nodes have been refactored into the nodes/ subdirectory with comprehensive Langfuse tracing.
"""

import logging

from agents.profiler.nodes.graph_builder import build_profile_researcher

logger = logging.getLogger(__name__)

# Create the main graph instance
profile_researcher = build_profile_researcher()

logger.info("Profile researcher graph compiled successfully")
