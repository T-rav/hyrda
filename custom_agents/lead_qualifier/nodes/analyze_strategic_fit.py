"""Analyze strategic fit and organizational readiness."""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from ..configuration import QualifierConfiguration
from ..prompts import STRATEGIC_FIT_PROMPT
from ..state import QualifierState

logger = logging.getLogger(__name__)


async def analyze_strategic_fit(
    state: QualifierState, config: RunnableConfig
) -> dict[str, Any]:
    """Analyze strategic fit and organizational readiness."""
    logger.info("Analyzing strategic fit...")

    # Extract configuration from RunnableConfig
    configuration = QualifierConfiguration(**(config.get("configurable", {})))

    company = state.get("company", {})
    contact = state.get("contact", {})

    context = f"""
COMPANY: {company.get('company_name')} ({company.get('industry')}, {company.get('company_size')})
CONTACT: {contact.get('contact_name')} - {contact.get('job_title')} ({contact.get('seniority')})
LIFECYCLE STAGE: {contact.get('lifecycle_stage')}
HUBSPOT SCORE: {contact.get('hubspot_lead_score')}
"""

    llm = ChatOpenAI(model=configuration.model, temperature=configuration.temperature)
    messages = [SystemMessage(content=STRATEGIC_FIT_PROMPT), HumanMessage(content=context)]
    response = await llm.ainvoke(messages)

    # Simple parsing (use structured output in production)
    from .analyze_solution_fit import _extract_field, _extract_list, _extract_score

    strategic_fit_score = _extract_score(response.content, "strategic_fit_score", -10, 25)
    reasoning = _extract_field(response.content, "strategic_fit_reasoning")
    initiative = _extract_field(response.content, "primary_initiative")
    risks = _extract_list(response.content, "risk_flags")

    logger.info(f"Strategic fit score: {strategic_fit_score}/25")

    return {
        "strategic_fit_score": strategic_fit_score,
        "strategic_fit_reasoning": reasoning,
        "primary_initiative": initiative,
        "risk_flags": risks,
    }
