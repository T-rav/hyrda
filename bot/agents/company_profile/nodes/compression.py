"""Research compression node for deep research workflow.

Compresses and synthesizes research findings into concise summaries.
Includes Langfuse tracing for observability.
"""

import logging

from langchain_core.runnables import RunnableConfig

from agents.company_profile.state import ResearcherState

logger = logging.getLogger(__name__)


async def compress_research(state: ResearcherState, config: RunnableConfig) -> dict:
    """Pass through full research findings without compression.

    Compression now happens only at final report generation if needed to fit context.
    This preserves maximum detail in research notes.

    Args:
        state: Current researcher state
        config: Runtime configuration

    Returns:
        Dict with compressed_research (full notes) and raw_notes
    """
    research_topic = state["research_topic"]
    messages = state["researcher_messages"]
    raw_notes = state.get("raw_notes", [])

    logger.info(
        f"Preserving full research notes for: {research_topic[:50]}... (no compression)"
    )

    # Extract tool outputs from messages (the actual research findings)
    research_content = []
    for msg in messages:
        # Tool messages contain the actual research data
        if hasattr(msg, "type") and msg.type == "tool":
            research_content.append(msg.content)

    # Combine all research content with topic header
    full_research = f"## Research Topic: {research_topic}\n\n"
    if research_content:
        full_research += "\n\n".join(research_content)
    else:
        # Fallback: join raw notes if no tool messages found
        full_research += (
            "\n\n".join(raw_notes) if raw_notes else "No research content captured."
        )

    logger.info(f"Full research preserved: {len(full_research)} characters")

    return {
        "compressed_research": full_research,  # Not compressed - full detail preserved
        "raw_notes": raw_notes,
    }
