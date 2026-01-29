"""Graph builder for deep research agent.

Builds LangGraph workflow with research planning, task execution, synthesis, and quality control.
"""

import logging

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ..state import (
    ResearchAgentInputState,
    ResearchAgentOutputState,
    ResearchAgentState,
    ResearcherOutputState,
    ResearcherState,
    SupervisorState,
)
from .quality_control import quality_control, quality_control_router
from .research_planner import create_research_plan
from .researcher import researcher, researcher_tools
from .supervisor import supervisor, supervisor_tools
from .synthesizer import synthesize_findings

logger = logging.getLogger(__name__)


def build_researcher_subgraph() -> CompiledStateGraph:
    """Build researcher subgraph for executing individual research tasks.

    The researcher subgraph:
    - researcher: Makes LLM calls with tools (web search, file cache)
    - researcher_tools: Executes tool calls
    - Loops until research complete

    Returns:
        Compiled researcher subgraph
    """
    researcher_builder = StateGraph(
        ResearcherState, output_schema=ResearcherOutputState
    )

    # Add nodes
    researcher_builder.add_node("researcher", researcher)
    researcher_builder.add_node("researcher_tools", researcher_tools)

    # Add edges
    researcher_builder.add_edge(START, "researcher")

    # Conditional routing: if tool calls exist, go to tools, else end
    def researcher_router(state: ResearcherState) -> str:
        """Route researcher based on tool calls."""
        messages = state.get("researcher_messages", [])
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return "researcher_tools"
        return END

    researcher_builder.add_conditional_edges(
        "researcher",
        researcher_router,
        {
            "researcher_tools": "researcher_tools",
            END: END,
        },
    )

    # Tools loop back to researcher
    researcher_builder.add_edge("researcher_tools", "researcher")

    # Compile without checkpointer - LangGraph API handles persistence automatically
    # Note: recursion_limit is configured at runtime in invoke/stream config
    return researcher_builder.compile()


def build_supervisor_subgraph() -> CompiledStateGraph:
    """Build and compile the supervisor subgraph.

    The supervisor subgraph coordinates parallel researchers executing TODO tasks.
    It consists of:
    - supervisor: Delegates research tasks using ConductResearch tool
    - supervisor_tools: Executes tool calls and launches parallel researchers

    Returns:
        Compiled supervisor subgraph
    """
    supervisor_builder = StateGraph(SupervisorState)

    # Add nodes
    supervisor_builder.add_node("supervisor", supervisor)
    supervisor_builder.add_node("supervisor_tools", supervisor_tools)

    # Add edges
    supervisor_builder.add_edge(START, "supervisor")

    # Compile without checkpointer - LangGraph API handles persistence automatically
    # Note: recursion_limit is configured at runtime in invoke/stream config
    return supervisor_builder.compile()


def build_research_agent(config: dict = None) -> CompiledStateGraph:
    """Build main research agent graph.

    The main graph orchestrates:
    1. create_research_plan: Generate research strategy and TODO tasks
    2. research_supervisor: Coordinate parallel researchers executing tasks
    3. synthesize_findings: Combine findings into comprehensive report
    4. quality_control: Validate report with revision loop

    Args:
        config: Optional LangGraph config dict (ignored - API manages checkpointing)

    Returns:
        Compiled research agent graph
    """
    # Build supervisor subgraph
    supervisor_subgraph = build_supervisor_subgraph()

    # Build main graph with input/output schemas
    research_builder = StateGraph(
        ResearchAgentState,
        input_schema=ResearchAgentInputState,
        output_schema=ResearchAgentOutputState,
    )

    # Add nodes
    research_builder.add_node("create_research_plan", create_research_plan)
    research_builder.add_node("research_supervisor", supervisor_subgraph)
    research_builder.add_node("synthesize_findings", synthesize_findings)
    research_builder.add_node("quality_control", quality_control)

    # Add edges
    research_builder.add_edge(START, "create_research_plan")
    # Full implementation: plan -> supervisor (parallel research) -> synthesize
    research_builder.add_edge("create_research_plan", "research_supervisor")
    research_builder.add_edge("research_supervisor", "synthesize_findings")
    research_builder.add_edge("synthesize_findings", "quality_control")

    # Quality control conditional routing
    research_builder.add_conditional_edges(
        "quality_control",
        quality_control_router,
        {
            "revise": "synthesize_findings",  # Loop back for revision
            "end": END,  # Quality passed or max revisions exceeded
        },
    )

    # Compile without checkpointer - LangGraph API handles persistence automatically
    return research_builder.compile()


logger.info("Research agent graph builder loaded")
