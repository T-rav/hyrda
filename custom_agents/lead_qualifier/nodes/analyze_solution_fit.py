"""Analyze solution fit for the lead."""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from ..configuration import QualifierConfiguration
from ..prompts import SOLUTION_FIT_PROMPT
from ..state import QualifierState

logger = logging.getLogger(__name__)


async def analyze_solution_fit(
    state: QualifierState, config: RunnableConfig
) -> dict[str, Any]:
    """Analyze how well the company fits 8th Light's service offerings.

    Args:
        state: Current qualifier state
        config: Qualifier configuration

    Returns:
        Updated state with solution fit analysis
    """
    logger.info("Analyzing solution fit...")
    logger.info(f"Config type: {type(config)}")
    logger.info(f"Config keys: {list(config.keys()) if isinstance(config, dict) else 'not a dict'}")
    if isinstance(config, dict) and "configurable" in config:
        logger.info(f"Configurable keys: {list(config['configurable'].keys())}")

    # Extract configuration from RunnableConfig
    try:
        configuration = QualifierConfiguration.from_runnable_config(config)
        logger.info("Successfully created configuration")
    except Exception as e:
        logger.error(f"Failed to create configuration: {e}")
        raise

    # Build context from company and contact data
    company = state.get("company", {})
    contact = state.get("contact", {})

    context = f"""
COMPANY DATA:
- Name: {company.get('company_name', 'N/A')}
- Domain: {company.get('company_domain', 'N/A')}
- Industry: {company.get('industry', 'N/A')}
- Size: {company.get('company_size', 'N/A')}
- Location: {company.get('location', 'N/A')} / {company.get('region', 'N/A')}

CONTACT DATA:
- Name: {contact.get('contact_name', 'N/A')}
- Title: {contact.get('job_title', 'N/A')}
- Seniority: {contact.get('seniority', 'N/A')}
- Department: {contact.get('department', 'N/A')}
- Lifecycle Stage: {contact.get('lifecycle_stage', 'N/A')}
- Lead Source: {contact.get('lead_source', 'N/A')}
- HubSpot Lead Score: {contact.get('hubspot_lead_score', 'N/A')}

QUERY/CONTEXT:
{state.get('query', 'Lead qualification assessment')}
"""

    # Call LLM for analysis
    llm = ChatOpenAI(model=configuration.model, temperature=configuration.temperature)

    messages = [
        SystemMessage(content=SOLUTION_FIT_PROMPT),
        HumanMessage(content=context),
    ]

    response = await llm.ainvoke(messages)
    response_text = response.content

    # Parse response (in production, use structured output)
    # For now, use simple parsing logic
    solution_fit_score = _extract_score(response_text, "solution_fit_score", 0, 40)
    reasoning = _extract_field(response_text, "solution_fit_reasoning")
    recommended = _extract_list(response_text, "recommended_solution")

    logger.info(f"Solution fit score: {solution_fit_score}/40")

    return {
        "solution_fit_score": solution_fit_score,
        "solution_fit_reasoning": reasoning,
        "recommended_solution": recommended,
    }


def _extract_score(text: str, field: str, min_val: int, max_val: int) -> int:
    """Extract score from LLM response."""
    import re

    pattern = rf"{field}:\s*(\d+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        score = int(match.group(1))
        return max(min_val, min(score, max_val))
    return min_val


def _extract_field(text: str, field: str) -> str:
    """Extract field value from LLM response."""
    import re

    pattern = rf"{field}:\s*(.+?)(?=\n\d+\.|$)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else text[:500]


def _extract_list(text: str, field: str) -> list[str]:
    """Extract list field from LLM response."""
    import re

    pattern = rf"{field}:\s*\[([^\]]+)\]"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        items = match.group(1).split(",")
        return [item.strip().strip('"').strip("'") for item in items]
    return []
