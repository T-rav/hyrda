"""LangGraph workflow for company profile deep research.

Implements a hierarchical research system with supervisor and researcher subgraphs.
All nodes have been refactored into the nodes/ subdirectory with comprehensive Langfuse tracing.
"""

import logging

from .nodes.graph_builder import build_profile_researcher
from .services.prompt_service import initialize_prompt_service
from config.settings import Settings

logger = logging.getLogger(__name__)

# Initialize PromptService for profile agent
settings = Settings()
initialize_prompt_service(settings)
logger.info("PromptService initialized for profile agent")

# Create the main graph instance
profile_researcher = build_profile_researcher()

logger.info("Profile researcher graph compiled successfully")
