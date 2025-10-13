"""State definitions for MEDDPICC coach workflow.

Defines data structures that flow through the LangGraph workflow for
MEDDPICC analysis and coaching.
"""

from typing_extensions import TypedDict


class MeddpiccAgentInputState(TypedDict):
    """Input to the MEDDPICC coach graph.

    Only query (sales notes) is required for input.
    """

    query: str  # Raw sales call notes


class MeddpiccAgentState(TypedDict, total=False):
    """Main state for MEDDPICC coach workflow.

    Attributes:
        query: Raw sales call notes from user (REQUIRED)
        raw_notes: Cleaned and prepared notes
        scraped_content: Content extracted from URLs/documents
        sources: List of scraped URLs/documents
        meddpicc_breakdown: Structured MEDDPICC analysis
        coaching_insights: Maverick's coaching advice
        final_response: Combined formatted output
    """

    query: str
    raw_notes: str
    scraped_content: str
    sources: list[str]
    meddpicc_breakdown: str
    coaching_insights: str
    final_response: str


class MeddpiccAgentOutputState(TypedDict):
    """Output from the MEDDPICC coach graph."""

    final_response: str
