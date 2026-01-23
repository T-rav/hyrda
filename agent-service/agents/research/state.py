"""State definitions for deep research workflow.

Defines data structures for the research agent with TODO tracking and file caching.
"""

from typing import Annotated

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing_extensions import TypedDict


# Tool schemas for research workflow
class CreateResearchTask(BaseModel):
    """Tool for creating a new research subtask."""

    task_description: str  # Clear description of what needs to be researched
    priority: str = "medium"  # Priority: low, medium, high
    dependencies: list[str] = []  # IDs of tasks that must complete first


class CompleteResearchTask(BaseModel):
    """Tool for marking a research task as complete."""

    task_id: str  # ID of completed task
    findings: str  # Research findings for this task


class ConductResearch(BaseModel):
    """Tool for supervisor to delegate research to a parallel researcher."""

    task_id: str  # ID of the task from research_tasks list to execute
    research_question: str  # Specific research question to investigate
    context: str = ""  # Optional context from previous research


class ResearchComplete(BaseModel):
    """Tool for supervisor to signal all research tasks are complete."""

    summary: str  # Brief summary of what was researched


class CacheFile(BaseModel):
    """Tool for caching downloaded/fetched data."""

    file_type: str  # Type: sec_filing, web_page, pdf, json_data
    content: str  # Raw content or path to content
    metadata: dict  # Source URL, company name, filing type, date, etc.


class RetrieveCache(BaseModel):
    """Tool for retrieving previously cached data."""

    query: str  # Search query to find relevant cached files
    file_type: str | None = None  # Optional filter by file type


class ResearchTask(BaseModel):
    """Individual research task in the TODO list."""

    task_id: str
    description: str
    priority: str  # low, medium, high
    status: str  # pending, in_progress, completed, blocked
    dependencies: list[str]  # Task IDs this depends on
    findings: str | None  # Research results when completed
    created_at: str
    completed_at: str | None


class CachedFile(BaseModel):
    """Metadata for cached file."""

    file_id: str  # Unique identifier
    file_type: str  # sec_filing, web_page, pdf, json_data
    file_path: str  # Path in cache directory
    metadata: dict  # Source URL, company, date, etc.
    cached_at: str
    size_bytes: int


# Main agent state - tracks entire research workflow
class _ResearchAgentStateRequired(TypedDict):
    """Required fields for ResearchAgentState."""

    query: str  # Original user research query


class ResearchAgentState(_ResearchAgentStateRequired, total=False):
    """Main state for deep research workflow.

    Tracks research planning, task execution, file caching, and report generation.

    Attributes:
        query: Original user research query (REQUIRED)
        messages: Conversation history with AI messages
        research_plan: High-level research strategy and approach
        research_tasks: List of TODO items for research execution
        completed_tasks: List of finished research tasks
        cached_files: List of files cached during research
        raw_findings: Unprocessed research data from all tasks
        synthesized_findings: Compressed and organized findings
        final_report: Generated comprehensive research report
        executive_summary: Short summary (3-5 bullets)
        report_structure: LLM-generated report outline/format
        pdf_url: Presigned URL to PDF report in S3/MinIO
        revision_count: Number of quality control revisions
        revision_prompt: Specific instructions for next revision
        passes_quality: Quality control result flag
        max_revisions_exceeded: Flag for max revision limit
        research_depth: Depth level (quick, standard, deep, exhaustive)
        research_iterations: Counter for research loops
    """

    messages: Annotated[list[MessageLikeRepresentation], add_messages]
    research_plan: str
    research_tasks: list[ResearchTask]
    completed_tasks: list[ResearchTask]
    cached_files: list[CachedFile]
    raw_findings: list[str]
    synthesized_findings: list[str]
    final_report: str
    executive_summary: str
    report_structure: str  # LLM-generated outline
    pdf_url: str  # Presigned S3 URL for PDF report
    revision_count: int
    revision_prompt: str
    passes_quality: bool
    max_revisions_exceeded: bool
    research_depth: str
    research_iterations: int


# Supervisor subgraph state
class SupervisorState(TypedDict):
    """State for supervisor coordinating parallel researchers.

    Supervisor delegates research tasks from the TODO list.
    """

    supervisor_messages: list[MessageLikeRepresentation]
    research_plan: str
    research_tasks: list[ResearchTask]
    completed_tasks: list[ResearchTask]
    research_iterations: int
    raw_findings: list[str]


# Researcher subgraph state
class ResearcherState(TypedDict):
    """State for individual researcher executing specific task.

    Each researcher focuses on one task from the TODO list.
    """

    researcher_messages: list[MessageLikeRepresentation]
    current_task: ResearchTask
    tool_call_iterations: int
    findings: str
    cached_files: list[CachedFile]
    raw_data: list[str]


# Researcher output state
class ResearcherOutputState(TypedDict):
    """Output from researcher subgraph."""

    findings: str
    cached_files: list[CachedFile]
    raw_data: list[str]


# Input state - only query required
class ResearchAgentInputState(TypedDict):
    """Input to the research agent graph."""

    query: str


# Output state
class ResearchAgentOutputState(TypedDict):
    """Output from the research agent graph."""

    messages: list[MessageLikeRepresentation]
    final_report: str
    executive_summary: str
    report_structure: str
    cached_files: list[CachedFile]
