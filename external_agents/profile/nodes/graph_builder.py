"""Graph builder functions for deep research workflow.

Builds and compiles the LangGraph workflows for researcher, supervisor, and main profile agent.
"""

import logging

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from typing import Literal

from .answer_question import answer_question
from .brief_validation import (
    research_brief_router,
    validate_research_brief,
)
from .clarification import clarify_with_user
from .compression import compress_research
from .final_report import final_report_generation
from .output import output_node
from .quality_control import (
    quality_control_node,
    quality_control_router,
)
from .research_brief import write_research_brief
from .researcher import researcher, researcher_tools
from .supervisor import supervisor, supervisor_tools
from ..state import (
    ProfileAgentInputState,
    ProfileAgentOutputState,
    ProfileAgentState,
    ResearcherOutputState,
    ResearcherState,
    SupervisorState,
)

logger = logging.getLogger(__name__)


def start_router(state: ProfileAgentState) -> Literal["answer_question", "clarify_with_user"]:
    """Route to Q&A node if report exists, otherwise full workflow.

    Routing priority (inspired by MEDDIC agent):
    1. followup_mode=True → Q&A (user in active conversation)
    2. final_report exists → Q&A (follow-up after report)
    3. No report → Full workflow (initial request)

    Args:
        state: Current profile agent state

    Returns:
        "answer_question" if in follow-up mode or report exists
        "clarify_with_user" if no report (initial profile request)
    """
    followup_mode = state.get("followup_mode", False)
    final_report = state.get("final_report", "")

    # Priority 1: If in follow-up mode (from checkpoint), route to Q&A
    if followup_mode:
        logger.info(
            "🔄 In follow-up mode (from checkpoint) - routing to Q&A node"
        )
        return "answer_question"

    # Priority 2: If final_report exists, route to Q&A
    if final_report:
        logger.info("📚 Final report exists - routing to Q&A node for follow-up")
        return "answer_question"

    # Priority 3: No report - route to full workflow
    logger.info("🔬 No report found - routing to full research workflow")
    return "clarify_with_user"


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
    return researcher_builder.compile({"recursion_limit": 100})


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

    # Compile with increased recursion limit
    # Supervisor can loop many times for complex research briefs
    return supervisor_builder.compile({"recursion_limit": 100})


def build_profile_researcher(checkpointer=None) -> CompiledStateGraph:
    """Build and compile the main profile researcher graph.

    The main graph orchestrates the entire deep research process:
    1. clarify_with_user: Check if user query needs clarification
    2. write_research_brief: Generate structured research plan
    3. validate_research_brief: Validate brief quality (with revision loop)
    4. research_supervisor: Delegate and coordinate research tasks
    5. final_report_generation: Synthesize findings into final report
    6. quality_control: Validate final report (with revision loop)

    Args:
        checkpointer: Optional checkpointer for state persistence (MemorySaver, etc.)

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
    profile_builder.add_node("answer_question", answer_question)  # Q&A for follow-ups
    profile_builder.add_node("clarify_with_user", clarify_with_user)
    profile_builder.add_node("write_research_brief", write_research_brief)
    profile_builder.add_node("validate_research_brief", validate_research_brief)
    profile_builder.add_node("research_supervisor", supervisor_subgraph)
    profile_builder.add_node("final_report_generation", final_report_generation)
    profile_builder.add_node("quality_control", quality_control_node)
    profile_builder.add_node("output", output_node)

    # Add edges
    # START uses conditional routing to detect follow-up questions
    profile_builder.add_conditional_edges(
        START,
        start_router,
        {
            "answer_question": "answer_question",  # Follow-up: use Q&A
            "clarify_with_user": "clarify_with_user",  # Initial: full workflow
        },
    )

    # Q&A path goes directly to output
    profile_builder.add_edge("answer_question", "output")

    # Main research path uses static edges
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
            "end": "output",  # Quality passed, emit final output
        },
    )

    # Output node emits final result and then ends
    profile_builder.add_edge("output", END)

    # Compile and return with checkpointer if provided
    if checkpointer:
        return profile_builder.compile(checkpointer=checkpointer)
    else:
        return profile_builder.compile()
