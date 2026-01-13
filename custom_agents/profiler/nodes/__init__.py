"""LangGraph nodes for deep research workflow.

This package contains modular node implementations for the hierarchical
research system, organized by responsibility. All nodes include comprehensive
Langfuse tracing for observability.
"""

from profiler.nodes.clarification import clarify_with_user
from profiler.nodes.compression import compress_research
from profiler.nodes.final_report import final_report_generation
from profiler.nodes.graph_builder import (
    build_profile_researcher,
    build_researcher_subgraph,
    build_supervisor_subgraph,
)
from profiler.nodes.research_brief import write_research_brief
from profiler.nodes.researcher import researcher, researcher_tools
from profiler.nodes.supervisor import (
    execute_researcher,
    supervisor,
    supervisor_tools,
)

__all__ = [
    # Node functions
    "researcher",
    "researcher_tools",
    "compress_research",
    "supervisor",
    "supervisor_tools",
    "execute_researcher",
    "clarify_with_user",
    "write_research_brief",
    "final_report_generation",
    # Graph builders
    "build_researcher_subgraph",
    "build_supervisor_subgraph",
    "build_profile_researcher",
]
