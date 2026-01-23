"""LangGraph workflow for MEDDPICC sales coaching.

Implements a simple linear workflow that transforms sales call notes
into structured MEDDPICC analysis with actionable coaching insights.

For LangGraph Studio: This module exports a graph WITHOUT a checkpointer,
as LangGraph platform provides persistence automatically.

For bot code: Use MeddicAgent which creates the graph WITH MemorySaver.
"""

import logging

from meddpicc_coach.nodes.graph_builder import build_meddpicc_coach

logger = logging.getLogger(__name__)

# Create the main graph instance WITHOUT checkpointer
# LangGraph Studio will use platform persistence
meddpicc_coach = build_meddpicc_coach()

logger.info(
    "MEDDPICC coach graph compiled successfully (no checkpointer for LangGraph Studio)"
)
