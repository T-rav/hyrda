"""LangGraph workflow for company profile deep research.

Implements a hierarchical research system with supervisor and researcher subgraphs.
All nodes have been refactored into the nodes/ subdirectory with comprehensive Langfuse tracing.

IMPORTANT: Graph is compiled WITH checkpointing enabled for persistent conversation state.
This enables followup_mode to work across invocations in the same thread.
"""

import logging
from pathlib import Path

from .nodes.graph_builder import build_profile_researcher
from .services.prompt_service import initialize_prompt_service
from config.settings import Settings

logger = logging.getLogger(__name__)

# Initialize PromptService for profile agent
settings = Settings()
initialize_prompt_service(settings)
logger.info("PromptService initialized for profile agent")

# Setup checkpointing directory
checkpoint_dir = Path("/app/data/checkpoints")
checkpoint_dir.mkdir(parents=True, exist_ok=True)

# Create the main graph instance WITH checkpointing enabled
# Pass True to enable automatic checkpointing (LangGraph will manage the checkpointer)
profile_researcher = build_profile_researcher(checkpointer=True)

logger.info("Profile researcher graph compiled with persistent checkpointing enabled")
