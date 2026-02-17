"""Shared API clients for prospect skills.

These clients wrap external APIs (Tavily, Perplexity, HubSpot) with
proper error handling, caching, and logging.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# API Configuration
HUBSPOT_API_BASE = "https://api.hubapi.com"


@dataclass
class SearchResult:
    """A single search result."""

    title: str
    url: str
    content: str
    source: str = ""


@dataclass
class CompanyInfo:
    """Company information from HubSpot."""

    company_id: str
    name: str
    domain: str | None = None
    industry: str | None = None
    employees: int | None = None
    lifecycle_stage: str | None = None
    is_customer: bool = False
    has_active_deal: bool = False
    last_contacted: str | None = None
    deal_count: int = 0


class TavilyClient:
    """Tavily search client."""

    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search(
        self,
        query: str,
        max_results: int = 5,
        include_domains: list[str] | None = None,
    ) -> list[SearchResult]:
        """Execute Tavily search.

        Args:
            query: Search query
            max_results: Max results to return
            include_domains: Domain filter

        Returns:
            List of search results
        """
        if not self.api_key:
            logger.warning("Tavily API key not configured")
            return []

        try:
            from tavily import TavilyClient as TavilySDK

            client = TavilySDK(api_key=self.api_key)
            kwargs: dict[str, Any] = {"query": query, "max_results": max_results}
            if include_domains:
                kwargs["include_domains"] = include_domains

            response = client.search(**kwargs)

            return [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    content=r.get("content", ""),
                    source="tavily",
                )
                for r in response.get("results", [])
            ]
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return []


class PerplexityClient:
    """Perplexity deep research client."""

    def __init__(self):
        self.api_key = os.getenv("PERPLEXITY_API_KEY")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def research(self, query: str) -> str:
        """Execute Perplexity deep research.

        Args:
            query: Research query

        Returns:
            Research summary
        """
        if not self.api_key:
            return "Perplexity API not configured"

        try:
            import requests

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": "llama-3.1-sonar-large-128k-online",
                "messages": [{"role": "user", "content": query}],
            }

            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"Perplexity error: {response.status_code}"
        except Exception as e:
            logger.error(f"Perplexity error: {e}")
            return f"Research error: {e}"


class HubSpotClient:
    """HubSpot CRM client."""

    def __init__(self):
        self.access_token = os.getenv("HUBSPOT_ACCESS_TOKEN")

    @property
    def is_configured(self) -> bool:
        return bool(self.access_token)

    async def search_companies(
        self,
        query: str = "",
        industry: str = "",
        limit: int = 10,
    ) -> list[CompanyInfo]:
        """Search HubSpot for companies.

        Args:
            query: Company name search
            industry: Industry filter
            limit: Max results

        Returns:
            List of company info
        """
        if not self.access_token:
            logger.warning("HubSpot access token not configured")
            return []

        filters = []
        if query:
            filters.append(
                {
                    "propertyName": "name",
                    "operator": "CONTAINS_TOKEN",
                    "value": query,
                }
            )
        if industry:
            filters.append(
                {
                    "propertyName": "industry",
                    "operator": "EQ",
                    "value": industry,
                }
            )

        payload = {
            "filterGroups": [{"filters": filters}] if filters else [],
            "properties": [
                "name",
                "domain",
                "industry",
                "numberofemployees",
                "lifecyclestage",
                "notes_last_contacted",
                "num_associated_deals",
            ],
            "limit": limit,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{HUBSPOT_API_BASE}/crm/v3/objects/companies/search",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                if response.status_code != 200:
                    logger.warning(f"HubSpot search error: {response.status_code}")
                    return []

                data = response.json()
                companies = []

                for c in data.get("results", []):
                    props = c.get("properties", {})
                    stage = props.get("lifecyclestage", "")

                    companies.append(
                        CompanyInfo(
                            company_id=c.get("id", ""),
                            name=props.get("name", "Unknown"),
                            domain=props.get("domain"),
                            industry=props.get("industry"),
                            employees=int(props.get("numberofemployees") or 0) or None,
                            lifecycle_stage=stage,
                            is_customer=stage in ["customer", "evangelist"],
                            has_active_deal=stage == "opportunity",
                            last_contacted=props.get("notes_last_contacted"),
                            deal_count=int(props.get("num_associated_deals") or 0),
                        )
                    )

                return companies
        except Exception as e:
            logger.error(f"HubSpot search error: {e}")
            return []

    async def check_company(self, company_name: str) -> CompanyInfo | None:
        """Check if company exists in HubSpot.

        Args:
            company_name: Company to check

        Returns:
            CompanyInfo or None if not found
        """
        companies = await self.search_companies(query=company_name, limit=5)

        # Find best match
        name_lower = company_name.lower()
        for company in companies:
            if company.name.lower() == name_lower:
                return company

        # Return first partial match
        if companies:
            return companies[0]

        return None


# Singleton instances
_tavily: TavilyClient | None = None
_perplexity: PerplexityClient | None = None
_hubspot: HubSpotClient | None = None


def get_tavily() -> TavilyClient:
    """Get Tavily client singleton."""
    global _tavily
    if _tavily is None:
        _tavily = TavilyClient()
    return _tavily


def get_perplexity() -> PerplexityClient:
    """Get Perplexity client singleton."""
    global _perplexity
    if _perplexity is None:
        _perplexity = PerplexityClient()
    return _perplexity


def get_hubspot() -> HubSpotClient:
    """Get HubSpot client singleton."""
    global _hubspot
    if _hubspot is None:
        _hubspot = HubSpotClient()
    return _hubspot
