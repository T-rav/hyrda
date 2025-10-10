"""Graph builder functions for deep research workflow.

Builds and compiles the LangGraph workflows for researcher, supervisor, and main profile agent.
"""

import logging

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.company_profile.nodes.clarification import clarify_with_user
from agents.company_profile.nodes.compression import compress_research
from agents.company_profile.nodes.final_report import final_report_generation
from agents.company_profile.nodes.research_brief import write_research_brief
from agents.company_profile.nodes.researcher import researcher, researcher_tools
from agents.company_profile.nodes.supervisor import supervisor, supervisor_tools
from agents.company_profile.state import (
    ProfileAgentInputState,
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
    - researcher: Makes LLM calls with web search/scrape tools
    - researcher_tools: Executes tool calls
    - compress_research: Compresses findings into summary

    Returns:
        Compiled researcher subgraph
    """
    researcher_builder = StateGraph(ResearcherState, output=ResearcherOutputState)

    # Add nodes
    researcher_builder.add_node("researcher", researcher)
    researcher_builder.add_node("researcher_tools", researcher_tools)
    researcher_builder.add_node("compress_research", compress_research)

    # Add edges
    researcher_builder.add_edge(START, "researcher")
    researcher_builder.add_edge("compress_research", END)

    # Compile and return
    return researcher_builder.compile()


def build_supervisor_subgraph() -> CompiledStateGraph:
    """Build and compile the supervisor subgraph.

    The supervisor subgraph coordinates multiple researchers in parallel.
    It consists of:
    - supervisor: Delegates research tasks using ConductResearch tool
    - supervisor_tools: Executes tool calls and launches researchers

    Returns:
        Compiled supervisor subgraph
    """
    supervisor_builder = StateGraph(SupervisorState)

    # Add nodes
    supervisor_builder.add_node("supervisor", supervisor)
    supervisor_builder.add_node("supervisor_tools", supervisor_tools)

    # Add edges
    supervisor_builder.add_edge(START, "supervisor")

    # Compile and return
    return supervisor_builder.compile()


def build_profile_researcher() -> CompiledStateGraph:
    """Build and compile the main profile researcher graph.

    The main graph orchestrates the entire deep research process:
    1. clarify_with_user: Check if user query needs clarification
    2. write_research_brief: Generate structured research plan
    3. research_supervisor: Delegate and coordinate research tasks
    4. final_report_generation: Synthesize findings into final report

    Returns:
        Compiled profile researcher graph
    """
    # Build supervisor subgraph
    supervisor_subgraph = build_supervisor_subgraph()

    # Build main graph
    profile_builder = StateGraph(ProfileAgentState, input_schema=ProfileAgentInputState)

    # Add nodes
    profile_builder.add_node("clarify_with_user", clarify_with_user)
    profile_builder.add_node("write_research_brief", write_research_brief)
    profile_builder.add_node("research_supervisor", supervisor_subgraph)
    profile_builder.add_node("final_report_generation", final_report_generation)

    # Add edges
    profile_builder.add_edge(START, "clarify_with_user")
    profile_builder.add_edge("clarify_with_user", "write_research_brief")
    profile_builder.add_edge("write_research_brief", "research_supervisor")
    profile_builder.add_edge("research_supervisor", "final_report_generation")
    profile_builder.add_edge("final_report_generation", END)

    # Compile and return
    return profile_builder.compile()
