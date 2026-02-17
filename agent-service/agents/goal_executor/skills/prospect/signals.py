"""Signal search skill - multi-source buying signal detection."""

from dataclasses import dataclass, field
from typing import Any

from ..base import BaseSkill, SkillContext, SkillResult, SkillStatus
from .clients import get_perplexity, get_tavily


@dataclass
class Signal:
    """A buying signal."""

    type: str  # job_posting, funding, news, competitor
    title: str
    content: str
    url: str
    strength: str = "medium"  # high, medium, low

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "strength": self.strength,
        }


@dataclass
class SignalSearchData:
    """Signal search result data."""

    query: str
    signals: list[Signal] = field(default_factory=list)
    sources_searched: list[str] = field(default_factory=list)
    total_found: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "signals": [s.to_dict() for s in self.signals],
            "sources_searched": self.sources_searched,
            "total_found": self.total_found,
        }


# Domain lists for different signal types
JOB_DOMAINS = [
    "linkedin.com/jobs",
    "indeed.com",
    "glassdoor.com",
    "lever.co",
    "greenhouse.io",
    "jobs.ashbyhq.com",
]

NEWS_DOMAINS = [
    "techcrunch.com",
    "venturebeat.com",
    "theinformation.com",
    "wired.com",
    "arstechnica.com",
    "devops.com",
    "infoq.com",
    "thenewstack.io",
    "siliconangle.com",
]

FUNDING_DOMAINS = [
    "crunchbase.com",
    "techcrunch.com",
    "pitchbook.com",
    "venturebeat.com",
    "siliconangle.com",
]

REVIEW_DOMAINS = ["g2.com", "capterra.com", "trustradius.com", "gartner.com"]


class SearchSignalsSkill(BaseSkill):
    """Search multiple sources for buying signals.

    This skill searches across:
    - Job boards (hiring signals)
    - News sites (funding, launches)
    - Review sites (competitor signals)

    It aggregates results and categorizes by signal type.
    """

    name = "search_signals"
    description = "Multi-source buying signal search (jobs, news, funding, competitors)"
    version = "1.0.0"

    def __init__(self, context: SkillContext | None = None):
        super().__init__(context)
        self.tavily = get_tavily()
        self.perplexity = get_perplexity()

    async def execute(
        self,
        query: str,
        signal_types: list[str] | None = None,
        max_per_type: int = 5,
    ) -> SkillResult[SignalSearchData]:
        """Search for buying signals.

        Args:
            query: Search query (company name or topic)
            signal_types: Types to search (jobs, news, funding, competitors)
            max_per_type: Max results per signal type

        Returns:
            SkillResult with aggregated signals
        """
        types = signal_types or ["jobs", "news", "funding"]
        signals: list[Signal] = []
        sources_searched: list[str] = []

        for signal_type in types:
            self._step(f"search_{signal_type}")

            if signal_type == "jobs":
                results = self._search_jobs(query, max_per_type)
                signals.extend(results)
                sources_searched.append("job_boards")

            elif signal_type == "news":
                results = self._search_news(query, max_per_type)
                signals.extend(results)
                sources_searched.append("news_sites")

            elif signal_type == "funding":
                results = self._search_funding(query, max_per_type)
                signals.extend(results)
                sources_searched.append("funding_sources")

            elif signal_type == "competitors":
                results = self._search_competitors(query, max_per_type)
                signals.extend(results)
                sources_searched.append("review_sites")

        # If no results from Tavily, try Perplexity
        if not signals and self.perplexity.is_configured:
            self._step("perplexity_fallback")
            perplexity_result = self._perplexity_signals(query, types)
            if perplexity_result:
                signals.append(perplexity_result)
                sources_searched.append("perplexity")

        data = SignalSearchData(
            query=query,
            signals=signals,
            sources_searched=sources_searched,
            total_found=len(signals),
        )

        if signals:
            return SkillResult(
                status=SkillStatus.SUCCESS,
                data=data,
                message=f"Found {len(signals)} signals for '{query}'",
                steps_completed=[f"search_{t}" for t in types],
            )
        else:
            return SkillResult(
                status=SkillStatus.PARTIAL,
                data=data,
                message=f"No signals found for '{query}'",
                steps_completed=[f"search_{t}" for t in types],
            )

    def _search_jobs(self, query: str, max_results: int) -> list[Signal]:
        """Search job boards."""
        if not self.tavily.is_configured:
            return []

        search_query = (
            f'hiring "{query}" DevOps OR "AI Engineer" OR "Platform Engineer"'
        )
        results = self.tavily.search(search_query, max_results, JOB_DOMAINS)

        return [
            Signal(
                type="job_posting",
                title=r.title,
                content=r.content[:300],
                url=r.url,
                strength="high"
                if any(kw in r.title.lower() for kw in ["devops", "ai", "platform"])
                else "medium",
            )
            for r in results
        ]

    def _search_news(self, query: str, max_results: int) -> list[Signal]:
        """Search news sites."""
        if not self.tavily.is_configured:
            return []

        search_query = f"{query} funding OR launch OR announces OR expansion"
        results = self.tavily.search(search_query, max_results, NEWS_DOMAINS)

        return [
            Signal(
                type="news",
                title=r.title,
                content=r.content[:300],
                url=r.url,
                strength="high"
                if "funding" in r.title.lower() or "raises" in r.title.lower()
                else "medium",
            )
            for r in results
        ]

    def _search_funding(self, query: str, max_results: int) -> list[Signal]:
        """Search funding sources."""
        if not self.tavily.is_configured:
            return []

        search_query = f"{query} series funding raised million"
        results = self.tavily.search(search_query, max_results, FUNDING_DOMAINS)

        return [
            Signal(
                type="funding",
                title=r.title,
                content=r.content[:300],
                url=r.url,
                strength="high",  # Funding is always high signal
            )
            for r in results
        ]

    def _search_competitors(self, query: str, max_results: int) -> list[Signal]:
        """Search review/competitor sites."""
        if not self.tavily.is_configured:
            return []

        search_query = f"{query} review alternative switching"
        results = self.tavily.search(search_query, max_results, REVIEW_DOMAINS)

        return [
            Signal(
                type="competitor",
                title=r.title,
                content=r.content[:300],
                url=r.url,
                strength="medium",
            )
            for r in results
        ]

    def _perplexity_signals(self, query: str, types: list[str]) -> Signal | None:
        """Fallback to Perplexity for signal research."""
        type_str = ", ".join(types)
        prompt = (
            f"Find buying signals for {query} in these categories: {type_str}. "
            "Look for job postings, funding, news, or competitor mentions. "
            "Focus on signals from the last 30 days."
        )

        result = self.perplexity.research(prompt)
        if result and "error" not in result.lower():
            return Signal(
                type="research",
                title=f"Signal Research: {query}",
                content=result[:500],
                url="perplexity",
                strength="medium",
            )
        return None
