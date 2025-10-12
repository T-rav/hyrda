"""LangGraph workflow for MEDDPICC sales coaching.

Implements a simple linear workflow that transforms sales call notes
into structured MEDDPICC analysis with actionable coaching insights.
"""

import logging

from agents.meddpicc_coach.nodes.graph_builder import build_meddpicc_coach

logger = logging.getLogger(__name__)

# Create the main graph instance
meddpicc_coach = build_meddpicc_coach()

logger.info("MEDDPICC coach graph compiled successfully")
