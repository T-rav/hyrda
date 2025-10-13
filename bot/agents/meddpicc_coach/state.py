"""State definitions for MEDDPICC coach workflow.

Defines data structures that flow through the LangGraph workflow for
MEDDPICC analysis and coaching.
"""

from typing_extensions import TypedDict


class MeddpiccAgentInputState(TypedDict, total=False):
    """Input to the MEDDPICC coach graph.

    Query is the main input, but Q&A state fields can also be provided
    (typically restored from checkpoint when continuing a conversation).
    """

    query: str  # Raw sales call notes
    question_mode: bool  # Whether in Q&A mode (restored from checkpoint)
    current_question_index: int  # Current question index (restored from checkpoint)
    gathered_answers: dict[str, str]  # Collected answers (restored from checkpoint)


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
        question_mode: Whether we're in Q&A gathering mode
        current_question_index: Which question we're asking (0-7 for MEDDPICC)
        gathered_answers: Dictionary of answers to questions
    """

    query: str
    raw_notes: str
    scraped_content: str
    sources: list[str]
    meddpicc_breakdown: str
    coaching_insights: str
    final_response: str
    question_mode: bool
    current_question_index: int
    gathered_answers: dict[str, str]


class MeddpiccAgentOutputState(TypedDict):
    """Output from the MEDDPICC coach graph."""

    final_response: str
