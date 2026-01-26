"""LangGraph workflow for company profile deep research.

Implements a hierarchical research system with supervisor and researcher subgraphs.
All nodes have been refactored into the nodes/ subdirectory with comprehensive Langfuse tracing.

IMPORTANT: Graph is compiled WITH SqliteSaver for persistent conversation state.
This enables followup_mode to work across invocations in the same thread.
"""

import logging
import sqlite3
from pathlib import Path
from langgraph.checkpoint.sqlite import SqliteSaver

from .nodes.graph_builder import build_profile_researcher
from .services.prompt_service import initialize_prompt_service
from config.settings import Settings

logger = logging.getLogger(__name__)

# Initialize PromptService for profile agent
settings = Settings()
initialize_prompt_service(settings)
logger.info("PromptService initialized for profile agent")

# Setup persistent SQLite checkpointer for conversation state
checkpoint_dir = Path("/app/data/checkpoints")
checkpoint_dir.mkdir(parents=True, exist_ok=True)
checkpoint_path = str(checkpoint_dir / "profile_agent_checkpoints.db")

# Create connection and checkpointer
# SqliteSaver.from_conn_string returns a context manager, but we need persistent connection
# So create connection directly and pass to SqliteSaver
conn = sqlite3.connect(checkpoint_path, check_same_thread=False)
checkpointer = SqliteSaver(conn)

# Create the main graph instance WITH persistent checkpointer
profile_researcher = build_profile_researcher(checkpointer=checkpointer)

logger.info(f"Profile researcher graph compiled with persistent checkpointing at {checkpoint_path}")
