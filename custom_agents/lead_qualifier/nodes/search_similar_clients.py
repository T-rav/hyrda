"""Search for similar clients from knowledge base."""

import logging
import os
from typing import Any

import httpx
from langchain_core.runnables import RunnableConfig

from ..state import QualifierState

logger = logging.getLogger(__name__)


async def search_similar_clients(
    state: QualifierState, config: RunnableConfig
) -> dict[str, Any]:
    """Search internal knowledge base for similar past clients/projects.

    Uses the RAG service API to find similar companies and projects
    from historical data via vector search.
    """
    logger.info("Searching for similar clients via RAG service...")

    company = state.get("company", {})
    company_name = company.get("company_name", "")
    industry = company.get("industry", "")
    company_size = company.get("company_size", "")

    similar_clients = []
    similar_projects = []

    try:
        # Build search query for similar clients/projects
        search_query = f"past clients similar to {company_name} in {industry} industry with {company_size} employees, case studies, engagements, projects"

        # Get RAG service URL from environment
        rag_service_url = os.getenv("RAG_SERVICE_URL", "http://localhost:8002")
        service_token = os.getenv("BOT_SERVICE_TOKEN", "")

        if not service_token:
            logger.warning("BOT_SERVICE_TOKEN not set - using fallback data")
            raise Exception("No service token")

        # Call RAG service to search for similar content
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            rag_url = f"{rag_service_url}/api/v1/search"
            search_payload = {
                "query": search_query,
                "limit": 10,
                "similarity_threshold": 0.6
            }

            headers = {
                "X-Service-Token": service_token,
                "Content-Type": "application/json"
            }

            logger.info(f"Calling RAG service: {search_query[:80]}...")
            response = await http_client.post(rag_url, json=search_payload, headers=headers)

            if response.status_code == 200:
                results = response.json().get("results", [])
                logger.info(f"RAG service returned {len(results)} similar documents")

                # Extract client/project info from results
                for result in results[:10]:  # Limit to top 10
                    score = result.get("similarity", 0)
                    content = result.get("content", "")
                    metadata = result.get("metadata", {})
                    file_name = metadata.get("file_name", "Unknown Document")

                    content_preview = content[:200]

                    # Categorize based on content and metadata
                    if any(word in content_preview.lower() for word in ["client", "company", "engagement", "partner"]):
                        similar_clients.append({
                            "name": file_name.replace(".txt", "").replace("_", " ").replace(".pdf", ""),
                            "industry": metadata.get("industry", industry),
                            "similarity": round(score, 2),
                            "source": file_name
                        })

                    if any(word in content_preview.lower() for word in ["project", "platform", "implementation", "modernization", "migration"]):
                        similar_projects.append({
                            "title": file_name.replace(".txt", "").replace("_", " ").replace(".pdf", ""),
                            "type": metadata.get("project_type", "Similar Engagement"),
                            "similarity": round(score, 2),
                            "source": file_name
                        })

                # Deduplicate based on name/title
                seen_clients = set()
                unique_clients = []
                for client in similar_clients:
                    if client["name"] not in seen_clients:
                        seen_clients.add(client["name"])
                        unique_clients.append(client)
                similar_clients = unique_clients[:5]  # Top 5

                seen_projects = set()
                unique_projects = []
                for project in similar_projects:
                    if project["title"] not in seen_projects:
                        seen_projects.add(project["title"])
                        unique_projects.append(project)
                similar_projects = unique_projects[:5]  # Top 5

            elif response.status_code == 404:
                logger.info("RAG service search endpoint not found - may need to implement")
                raise Exception("Search endpoint not available")
            else:
                logger.warning(f"RAG service search failed: {response.status_code}")
                raise Exception(f"HTTP {response.status_code}")

    except Exception as e:
        logger.warning(f"Error searching via RAG service: {e}. Using fallback data.")
        # Fallback to placeholder data if RAG search fails
        similar_clients = [
            {"name": "Example Healthcare Tech Co", "industry": industry, "similarity": 0.75, "source": "fallback"},
        ]
        similar_projects = [
            {"title": "Similar Platform Modernization", "type": "Platform Modernization", "similarity": 0.70, "source": "fallback"},
        ]

    logger.info(f"Found {len(similar_clients)} similar clients, {len(similar_projects)} similar projects")

    return {
        "similar_clients": similar_clients,
        "similar_projects": similar_projects,
    }
