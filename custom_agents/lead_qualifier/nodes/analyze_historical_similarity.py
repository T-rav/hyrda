"""Analyze historical similarity to past successful engagements."""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from ..configuration import QualifierConfiguration
from ..prompts import HISTORICAL_SIMILARITY_PROMPT
from ..state import QualifierState

logger = logging.getLogger(__name__)


async def analyze_historical_similarity(
    state: QualifierState, config: RunnableConfig
) -> dict[str, Any]:
    """Analyze how closely prospect matches past successful clients."""
    logger.info("Analyzing historical similarity...")

    # Extract configuration from RunnableConfig
    configuration = QualifierConfiguration.from_runnable_config(config)

    company = state.get("company", {})
    similar_clients = state.get("similar_clients", [])
    similar_projects = state.get("similar_projects", [])

    context = f"""
PROSPECT COMPANY:
{company.get('company_name')} - {company.get('industry')} ({company.get('company_size')})

SIMILAR PAST CLIENTS:
{_format_list(similar_clients)}

SIMILAR PAST PROJECTS:
{_format_list(similar_projects)}
"""

    llm = ChatOpenAI(model=configuration.model, temperature=configuration.temperature)
    messages = [SystemMessage(content=HISTORICAL_SIMILARITY_PROMPT), HumanMessage(content=context)]
    response = await llm.ainvoke(messages)

    from .analyze_solution_fit import _extract_field, _extract_list, _extract_score

    similarity_score = _extract_score(response.content, "historical_similarity_score", -10, 25)
    reasoning = _extract_field(response.content, "historical_similarity_reasoning")
    examples = _extract_list(response.content, "similar_client_example")

    logger.info(f"Historical similarity score: {similarity_score}/25")

    return {
        "historical_similarity_score": similarity_score,
        "historical_similarity_reasoning": reasoning,
        "similar_client_example": examples,
    }


def _format_list(items: list[dict]) -> str:
    """Format list of items for LLM prompt."""
    if not items:
        return "None found"
    return "\n".join([f"- {item}" for item in items])
