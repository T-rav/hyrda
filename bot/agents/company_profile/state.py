"""State definitions for company profile deep research workflow.

Defines data structures that flow through the LangGraph workflow for
profile research, enrichment, and report generation.
"""

from typing import TypedDict

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import MessagesState
from pydantic import BaseModel


# Structured output models for research workflow
class ConductResearch(BaseModel):
    """Tool for supervisor to delegate research to sub-researchers."""

    research_topic: str  # Detailed topic description for sub-researcher


class ResearchComplete(BaseModel):
    """Signal that research is complete and ready for final report."""

    pass


class ClarifyWithUser(BaseModel):
    """Clarification workflow output."""

    need_clarification: bool
    question: str
    verification: str


class ProfileResearchBrief(BaseModel):
    """Research planning output."""

    research_brief: str


# Main agent state - tracks entire workflow
class ProfileAgentState(MessagesState):
    """Main state for company profile research workflow.

    Attributes:
        messages: LangGraph MessagesState for conversation history
        supervisor_messages: Supervisor agent conversation
        research_brief: Generated research plan for the profile
        raw_notes: Unprocessed research data from all researchers
        notes: Compressed and synthesized research findings
        final_report: Generated comprehensive profile report
        profile_type: Type of profile (company, employee, project)
        query: Original user query
    """

    supervisor_messages: list[MessageLikeRepresentation]
    research_brief: str
    raw_notes: list[str]
    notes: list[str]
    final_report: str
    profile_type: str  # "company", "employee", "project"
    query: str


# Supervisor state - manages research delegation
class SupervisorState(TypedDict):
    """State for supervisor agent that delegates research tasks.

    The supervisor breaks down profile research into parallel sub-tasks
    and manages the overall research strategy.
    """

    supervisor_messages: list[MessageLikeRepresentation]
    research_brief: str
    notes: list[str]
    research_iterations: int
    raw_notes: list[str]
    profile_type: str


# Individual researcher state
class ResearcherState(TypedDict):
    """State for individual researcher performing specific research task.

    Each researcher focuses on a specific aspect of the profile
    (e.g., company history, leadership team, recent projects).
    """

    researcher_messages: list[MessageLikeRepresentation]
    tool_call_iterations: int
    research_topic: str
    compressed_research: str
    raw_notes: list[str]
    profile_type: str


# Output state from researcher subgraph
class ResearcherOutputState(TypedDict):
    """Output from researcher subgraph passed back to supervisor."""

    compressed_research: str
    raw_notes: list[str]


# Input state for main graph
class ProfileAgentInputState(TypedDict):
    """Input to the profile agent graph."""

    messages: list[MessageLikeRepresentation]
    query: str
    profile_type: str
