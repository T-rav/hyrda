"""Synthesize final qualification assessment."""

import logging
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..configuration import QualifierConfiguration
from ..prompts import SYNTHESIS_PROMPT
from ..state import QualifierState

logger = logging.getLogger(__name__)


async def synthesize_qualification(
    state: QualifierState, config: QualifierConfiguration
) -> dict[str, Any]:
    """Synthesize final qualification score and summary."""
    logger.info("Synthesizing qualification assessment...")

    # Calculate total score
    solution_fit = state.get("solution_fit_score", 0)
    strategic_fit = state.get("strategic_fit_score", 0)
    historical_similarity = state.get("historical_similarity_score", 0)

    total_score = solution_fit + strategic_fit + historical_similarity
    # Normalize to 0-100 scale (max possible is 90)
    qualification_score = min(100, int((total_score / 90) * 100))

    # Determine tier
    if qualification_score >= config.high_tier_threshold:
        fit_tier: Literal["High", "Medium", "Low"] = "High"
    elif qualification_score >= config.medium_tier_threshold:
        fit_tier = "Medium"
    else:
        fit_tier = "Low"

    logger.info(f"Final qualification score: {qualification_score}/100 ({fit_tier} tier)")

    # Generate seller-facing summary
    prompt_filled = SYNTHESIS_PROMPT.format(
        solution_fit_score=solution_fit,
        strategic_fit_score=strategic_fit,
        historical_similarity_score=historical_similarity,
        total_score=total_score,
        qualification_score=qualification_score,
    )

    context = f"""
REASONING:
Solution Fit: {state.get('solution_fit_reasoning', 'N/A')}

Strategic Fit: {state.get('strategic_fit_reasoning', 'N/A')}

Historical Similarity: {state.get('historical_similarity_reasoning', 'N/A')}

PRIMARY INITIATIVE: {state.get('primary_initiative', 'Unknown')}
RECOMMENDED SOLUTIONS: {state.get('recommended_solution', [])}
RISK FLAGS: {state.get('risk_flags', [])}
"""

    llm = ChatOpenAI(model=config.model, temperature=config.temperature)
    messages = [SystemMessage(content=prompt_filled), HumanMessage(content=context)]
    response = await llm.ainvoke(messages)

    qualification_summary = response.content

    return {
        "qualification_score": qualification_score,
        "fit_tier": fit_tier,
        "qualification_summary": qualification_summary,
    }
