"""LangGraph nodes for deep research workflow.

This package contains modular node implementations for the hierarchical
research system, organized by responsibility. All nodes include comprehensive
Langfuse tracing for observability.
"""

from agents.company_profile.nodes.clarification import clarify_with_user
from agents.company_profile.nodes.compression import compress_research
from agents.company_profile.nodes.final_report import final_report_generation
from agents.company_profile.nodes.graph_builder import (
    build_profile_researcher,
    build_researcher_subgraph,
    build_supervisor_subgraph,
)
from agents.company_profile.nodes.research_brief import write_research_brief
from agents.company_profile.nodes.researcher import researcher, researcher_tools
from agents.company_profile.nodes.supervisor import (
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
