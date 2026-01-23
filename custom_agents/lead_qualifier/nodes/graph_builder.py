"""Graph builder for Lead Qualifier agent."""

import logging

from langgraph.graph import END, START, StateGraph

from ..state import QualifierInput, QualifierOutput, QualifierState
from .analyze_historical_similarity import analyze_historical_similarity
from .analyze_solution_fit import analyze_solution_fit
from .analyze_strategic_fit import analyze_strategic_fit
from .search_similar_clients import search_similar_clients
from .synthesize_qualification import synthesize_qualification

logger = logging.getLogger(__name__)


def build_lead_qualifier() -> StateGraph:
    """Build the Lead Qualifier agent graph.

    Workflow:
    1. Analyze Solution Fit (0-40 points)
    2. Analyze Strategic Fit (0-25 points)
    3. Search Similar Clients (parallel with analysis)
    4. Analyze Historical Similarity (0-25 points)
    5. Synthesize Qualification (final score + summary)
    """
    # Create graph with input/output schemas
    # Note: config_schema removed - we use from_runnable_config() in nodes instead
    workflow = StateGraph(
        QualifierState,
        input_schema=QualifierInput,
        output_schema=QualifierOutput,
    )

    # Add nodes
    workflow.add_node("analyze_solution_fit", analyze_solution_fit)
    workflow.add_node("analyze_strategic_fit", analyze_strategic_fit)
    workflow.add_node("search_similar_clients", search_similar_clients)
    workflow.add_node("analyze_historical_similarity", analyze_historical_similarity)
    workflow.add_node("synthesize_qualification", synthesize_qualification)

    # Define edges (sequential flow for now)
    workflow.add_edge(START, "analyze_solution_fit")
    workflow.add_edge("analyze_solution_fit", "analyze_strategic_fit")
    workflow.add_edge("analyze_strategic_fit", "search_similar_clients")
    workflow.add_edge("search_similar_clients", "analyze_historical_similarity")
    workflow.add_edge("analyze_historical_similarity", "synthesize_qualification")
    workflow.add_edge("synthesize_qualification", END)

    return workflow.compile()
