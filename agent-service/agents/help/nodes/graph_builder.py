"""Graph builder for help agent.

Builds a simple LangGraph workflow that lists available agents
filtered by user permissions.
"""

import logging

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ..state import HelpAgentInputState, HelpAgentOutputState, HelpAgentState
from .list_agents import list_agents_node

logger = logging.getLogger(__name__)


def build_help_agent(config: dict = None) -> CompiledStateGraph:
    """Build help agent graph.

    The help agent graph is simple:
    1. list_agents_node: Fetches agents and filters by user permissions
    2. End: Return formatted response

    Args:
        config: Optional LangGraph config dict (ignored - API manages checkpointing)

    Returns:
        Compiled help agent graph
    """
    # Build graph with state definition
    builder = StateGraph(
        HelpAgentState,
        input_schema=HelpAgentInputState,
        output_schema=HelpAgentOutputState,
    )

    # Add nodes
    builder.add_node("list_agents", list_agents_node)

    # Add edges
    builder.add_edge(START, "list_agents")
    builder.add_edge("list_agents", END)

    # Compile without checkpointer - LangGraph API handles persistence automatically
    return builder.compile()


logger.info("Help agent graph builder loaded")
