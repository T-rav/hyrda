"""Search for similar clients from knowledge base."""

import logging
from typing import Any

from ..configuration import QualifierConfiguration
from ..state import QualifierState

logger = logging.getLogger(__name__)


async def search_similar_clients(
    state: QualifierState, config: QualifierConfiguration
) -> dict[str, Any]:
    """Search internal knowledge base for similar past clients/projects.

    In production, this would:
    1. Call RAG service to search for similar companies
    2. Call RAG service to search for similar project types
    3. Return ranked results

    For now, returns placeholder data.
    """
    logger.info("Searching for similar clients...")

    company = state.get("company", {})
    company_name = company.get("company_name", "")
    industry = company.get("industry", "")

    # Placeholder: In production, call RAG service
    # search_query = f"past clients similar to {company_name} in {industry} industry"
    # results = await rag_service.search(search_query, limit=5)

    similar_clients = [
        {"name": "Example Corp", "industry": industry, "similarity": 0.85},
        {"name": "Sample Inc", "industry": industry, "similarity": 0.78},
    ]

    similar_projects = [
        {"title": "AI Platform Build", "type": "AI Enablement", "similarity": 0.82},
        {"title": "Data Migration", "type": "Data Platform Engineering", "similarity": 0.75},
    ]

    logger.info(f"Found {len(similar_clients)} similar clients")

    return {
        "similar_clients": similar_clients,
        "similar_projects": similar_projects,
    }
