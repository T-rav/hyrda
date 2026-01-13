"""State definitions for company profile deep research workflow.

Defines data structures that flow through the LangGraph workflow for
profile research, enrichment, and report generation.
"""

from typing import Annotated

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing_extensions import TypedDict


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
# Use two-class pattern to make query required while keeping other fields optional
class _ProfileAgentStateRequired(TypedDict):
    """Required fields for ProfileAgentState."""

    query: str


class ProfileAgentState(_ProfileAgentStateRequired, total=False):
    """Main state for company profile research workflow.

    Attributes:
        query: Original user query (REQUIRED from input)
        messages: Conversation history
        supervisor_messages: Supervisor agent conversation
        research_brief: Generated research plan for the profile
        raw_notes: Unprocessed research data from all researchers
        notes: Compressed and synthesized research findings
        final_report: Generated comprehensive profile report
        executive_summary: Short summary for Slack display (3-5 bullets)
        profile_type: Type of profile (company or employee)
        focus_area: Specific intent/aspect to emphasize (e.g., "AI needs", "hiring challenges")
        revision_count: Number of quality control revisions attempted
        revision_prompt: Specific instructions for next revision
        passes_quality: Quality control result flag
        max_revisions_exceeded: Flag indicating max revision limit reached
        brief_passes_validation: Research brief validation result flag
        brief_revision_count: Number of brief validation revisions attempted
        brief_revision_prompt: Specific instructions for brief revision
        brief_max_revisions_exceeded: Flag indicating max brief revision limit reached
        brief_revision_instructions: Validation instructions for brief revision

    """

    messages: Annotated[list[MessageLikeRepresentation], add_messages]
    supervisor_messages: list[MessageLikeRepresentation]
    research_brief: str
    research_iterations: int  # Used by supervisor subgraph
    raw_notes: list[str]
    notes: list[str]
    final_report: str
    executive_summary: str
    profile_type: str
    focus_area: str
    revision_count: int
    revision_prompt: str
    passes_quality: bool
    max_revisions_exceeded: bool
    brief_passes_validation: bool
    brief_revision_count: int
    brief_revision_prompt: str
    brief_max_revisions_exceeded: bool
    brief_revision_instructions: str


# Supervisor state - manages research delegation
class SupervisorState(TypedDict, total=False):
    """State for supervisor agent that delegates research tasks.

    The supervisor breaks down profile research into parallel sub-tasks
    and manages the overall research strategy.

    All fields are optional to allow inheritance from parent ProfileAgentState.
    """

    supervisor_messages: list[MessageLikeRepresentation]
    research_brief: str
    notes: list[str]
    research_iterations: int
    raw_notes: list[str]
    profile_type: str
    focus_area: str


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
    focus_area: str


# Output state from researcher subgraph
class ResearcherOutputState(TypedDict):
    """Output from researcher subgraph passed back to supervisor."""

    compressed_research: str
    raw_notes: list[str]


# Input state for main graph - only query is required
class ProfileAgentInputState(TypedDict):
    """Input to the profile agent graph.

    Only query is required for input.
    """

    query: str


# Output state from main graph
class ProfileAgentOutputState(TypedDict):
    """Output from the profile agent graph."""

    messages: list[MessageLikeRepresentation]
    final_report: str
    executive_summary: str
