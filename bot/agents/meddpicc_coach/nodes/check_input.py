"""Check if input has enough information for analysis.

This node determines if the sales notes contain sufficient information
to warrant a full MEDDPICC analysis, or if clarifying questions should
be asked first.
"""

import logging
import re

from langgraph.graph.state import RunnableConfig

from agents.meddpicc_coach.state import MeddpiccAgentState

logger = logging.getLogger(__name__)


def check_input_completeness(
    state: MeddpiccAgentState, config: RunnableConfig
) -> dict[str, str | bool]:
    """Check if input has enough information for meaningful analysis.

    Determines if the notes are too sparse and need clarification.
    Criteria for "needs clarification":
    - Very short input (< 50 chars)
    - Single sentence with minimal context
    - Only mentions a name/company and basic interest

    Args:
        state: Current MEDDPICC agent state
        config: Runtime configuration

    Returns:
        Dict with needs_clarification flag and optional clarification message
    """
    query = state["query"]

    logger.info(f"Checking input completeness ({len(query)} chars)")

    # Check 1: Very short input
    if len(query.strip()) < 50:
        logger.info("Input too short - needs clarification")
        return {
            "needs_clarification": True,
            "clarification_message": _generate_clarification_message(query),
        }

    # Check 2: Count sentences (rough heuristic)
    sentences = re.split(r"[.!?]+", query.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    # Check 3: Look for any MEDDPICC indicators
    meddpicc_indicators = [
        # Metrics
        r"\$\d+|\d+%|\d+x|ROI|revenue|cost|savings|faster|improve",
        # Economic Buyer / Decision Process
        r"CEO|CFO|CTO|VP|director|manager|board|executive|decision",
        # Pain
        r"problem|pain|issue|challenge|struggle|frustrated|slow|difficult",
        # Timeline
        r"Q\d|quarter|month|year|week|deadline|timeline|ASAP|urgent",
        # Competition
        r"competitor|alternative|versus|vs\.|comparing|looking at",
        # Champion
        r"enthusiastic|champion|advocate|excited|supporter",
    ]

    indicator_count = 0
    for pattern in meddpicc_indicators:
        if re.search(pattern, query, re.IGNORECASE):
            indicator_count += 1

    # Decision: If 1 sentence or fewer, AND fewer than 2 indicators, ask for more
    if len(sentences) <= 1 and indicator_count < 2:
        logger.info(
            f"Minimal context detected ({len(sentences)} sentence(s), {indicator_count} indicators) - needs clarification"
        )
        return {
            "needs_clarification": True,
            "clarification_message": _generate_clarification_message(query),
        }

    # Input seems sufficient
    logger.info(
        f"Input has sufficient context ({len(sentences)} sentences, {indicator_count} indicators)"
    )
    return {
        "needs_clarification": False,
    }


def _generate_clarification_message(query: str) -> str:
    """Generate a friendly message asking for more context.

    Args:
        query: Original query

    Returns:
        Clarification message with specific questions
    """
    # Extract any name/company mentioned
    name_match = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", query)
    company_match = re.search(r"\b(from|at)\s+([A-Z][^\s]+(?:\s+[A-Z][^\s]+)*)", query)

    entity = None
    if company_match:
        entity = company_match.group(2)
    elif name_match:
        entity = name_match.group(1)

    context = f"your conversation with {entity}" if entity else "this opportunity"

    return f"""Hey! I'd love to help you with the MEDDPICC analysis for {context}, but I need a bit more context to give you solid coaching. 🎯

Can you share more about the call? For example:
- **What specific problems or pain points came up?** (e.g., "They're frustrated with 2-week deployment times")
- **Any numbers or metrics mentioned?** (e.g., "$200K budget", "50-person team", "need 3x faster")
- **Who did you talk to, and who makes the final decision?** (e.g., "Spoke with Bob, but CTO Sarah approves purchases")
- **Timeline or urgency?** (e.g., "Need solution by Q2", "Urgent priority")
- **Any competitors or alternatives they mentioned?**

The more details you provide, the better I can coach you on closing this deal! Feel free to paste raw notes or bullet points. 📝"""
