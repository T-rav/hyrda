"""Graph builder functions for deep research workflow.

Builds and compiles the LangGraph workflows for researcher, supervisor, and main profile agent.
"""

import logging

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from profiler.nodes.brief_validation import (
    research_brief_router,
    validate_research_brief,
)
from profiler.nodes.clarification import clarify_with_user
from profiler.nodes.compression import compress_research
from profiler.nodes.final_report import final_report_generation
from profiler.nodes.quality_control import (
    quality_control_node,
    quality_control_router,
)
from profiler.nodes.research_brief import write_research_brief
from profiler.nodes.aggregator import aggregator
from profiler.nodes.prepare_research import prepare_research
from profiler.nodes.research_assistant import research_assistant
from profiler.nodes.researcher import researcher, researcher_tools
from profiler.nodes.supervisor import supervisor
from profiler.state import (
    ProfileAgentInputState,
    ProfileAgentOutputState,
    ProfileAgentState,
    ResearcherOutputState,
    ResearcherState,
    SupervisorState,
)

logger = logging.getLogger(__name__)


def build_researcher_subgraph() -> CompiledStateGraph:
    """Build and compile the researcher subgraph.

    The researcher subgraph handles individual research tasks with tool calling.
    It consists of:
    - researcher: Makes LLM calls with tools (web search, scrape, internal search)
    - researcher_tools: Executes tool calls
    - compress_research: Compresses findings into summary

    Returns:
        Compiled researcher subgraph

    """
    researcher_builder = StateGraph(
        ResearcherState, output_schema=ResearcherOutputState
    )

    # Add nodes
    researcher_builder.add_node("researcher", researcher)
    researcher_builder.add_node("researcher_tools", researcher_tools)
    researcher_builder.add_node("compress_research", compress_research)

    # Add edges
    researcher_builder.add_edge(START, "researcher")
    researcher_builder.add_edge("compress_research", END)

    # Compile with increased recursion limit
    # Researcher can loop many times (researcher -> researcher_tools -> researcher)
    # Default limit of 25 is too low for deep research tasks
    # Compile without checkpointer - LangGraph API handles persistence automatically
    return researcher_builder.compile()


def build_supervisor_subgraph() -> CompiledStateGraph:
    """Build and compile the supervisor subgraph.

    The supervisor subgraph coordinates multiple researchers in parallel using Send().
    Flow: prepare_research → supervisor → [research_assistant, ...] → aggregator → supervisor | END

    Returns:
        Compiled supervisor subgraph

    """
    supervisor_builder = StateGraph(SupervisorState)

    # Add nodes
    supervisor_builder.add_node("prepare_research", prepare_research)
    supervisor_builder.add_node("supervisor", supervisor)
    supervisor_builder.add_node("research_assistant", research_assistant)
    supervisor_builder.add_node("aggregator", aggregator)

    # Flow
    supervisor_builder.add_edge(START, "prepare_research")
    supervisor_builder.add_edge("prepare_research", "supervisor")
    # supervisor returns either:
    #   - {"send": [Send(...), ...]} for dynamic parallel fan-out
    #   - {} empty dict when no more work
    # In both cases, after Send() processing (or immediately if empty), flow continues to aggregator
    supervisor_builder.add_edge("supervisor", "aggregator")
    # All research_assistants automatically route to aggregator after parallel execution
    supervisor_builder.add_edge("research_assistant", "aggregator")
    # aggregator uses Command(goto=...) to route to supervisor (loop) or __end__

    # Compile without checkpointer - LangGraph API handles persistence automatically
    return supervisor_builder.compile()


def build_profile_researcher(config: dict | None = None) -> CompiledStateGraph:
    """Build and compile the main profile researcher graph.

    The main graph orchestrates the entire deep research process:
    1. clarify_with_user: Check if user query needs clarification
    2. write_research_brief: Generate structured research plan
    3. validate_research_brief: Validate brief quality (with revision loop)
    4. research_supervisor: Delegate and coordinate research tasks
    5. final_report_generation: Synthesize findings into final report
    6. quality_control: Validate final report (with revision loop)

    Args:
        config: Optional LangGraph config dict (ignored - API manages checkpointing)

    Returns:
        Compiled profile researcher graph

    """
    # Build supervisor subgraph
    supervisor_subgraph = build_supervisor_subgraph()

    # Build main graph with explicit input/output schemas
    profile_builder = StateGraph(
        ProfileAgentState,
        input_schema=ProfileAgentInputState,
        output_schema=ProfileAgentOutputState,
    )

    # Add nodes
    profile_builder.add_node("clarify_with_user", clarify_with_user)
    profile_builder.add_node("write_research_brief", write_research_brief)
    profile_builder.add_node("validate_research_brief", validate_research_brief)
    profile_builder.add_node("research_supervisor", supervisor_subgraph)
    profile_builder.add_node("final_report_generation", final_report_generation)
    profile_builder.add_node("quality_control", quality_control_node)

    # Add edges
    # Main path uses static edges
    profile_builder.add_edge(START, "clarify_with_user")
    profile_builder.add_edge("clarify_with_user", "write_research_brief")
    profile_builder.add_edge("write_research_brief", "validate_research_brief")

    # Brief validation uses conditional edges to create validation loop (VISIBLE in graph!)
    profile_builder.add_conditional_edges(
        "validate_research_brief",
        research_brief_router,
        {
            "revise": "write_research_brief",  # Loop back for revision
            "proceed": "research_supervisor",  # Brief validated, start research
        },
    )

    profile_builder.add_edge("research_supervisor", "final_report_generation")
    profile_builder.add_edge("final_report_generation", "quality_control")

    # Quality control uses conditional edges to create evaluation loop (VISIBLE in graph!)
    # This replaces the Command-based routing with explicit conditional edges
    profile_builder.add_conditional_edges(
        "quality_control",
        quality_control_router,
        {
            "revise": "final_report_generation",  # Loop back for revision
            "end": END,  # Quality passed or max revisions exceeded
        },
    )

    # Compile without checkpointer - LangGraph API handles persistence automatically
    return profile_builder.compile()
