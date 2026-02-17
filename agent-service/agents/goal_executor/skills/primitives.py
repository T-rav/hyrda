"""Primitive skills for direct tool access.

These are low-level skills that provide direct access to underlying
tools/APIs. Use these for creative work where you need more control
than the higher-level bundled skills provide.

Available primitives:
- web_search: Direct Tavily web search
- deep_research: Direct Perplexity research
- recall_memory: Search and recall from persistent memory
- save_memory: Save information to persistent memory
- search_past_runs: Semantic search over past run summaries
- check_company_researched: Check if company was already researched
- mark_company_researched: Mark company as researched (dedup)
- list_prospects: List saved prospects from memory
- get_run_history: Get recent run history
- rephrase: Generate alternative phrases/queries (unstick tool)
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from ..services.memory import get_goal_memory
from .base import BaseSkill, SkillContext, SkillResult, SkillStatus
from .prospect.clients import get_perplexity, get_tavily
from .registry import register_skill

logger = logging.getLogger(__name__)


# =============================================================================
# Web Search Skill
# =============================================================================


@dataclass
class WebSearchData:
    """Web search result data."""

    query: str
    results: list[dict[str, Any]] = field(default_factory=list)
    total_found: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "results": self.results,
            "total_found": self.total_found,
        }


@register_skill
class WebSearchSkill(BaseSkill):
    """Direct web search using Tavily.

    Use this for custom searches not covered by signal search.
    Provides full control over query, domains, and result count.

    TIPS:
    - Use site: syntax in query for domain-specific searches:
      - "AI agents site:reddit.com" - Reddit discussions
      - "devops platform site:news.ycombinator.com" - Hacker News
      - "$TICKER earnings site:seekingalpha.com" - Seeking Alpha analysis
      - "series B funding site:techcrunch.com" - TechCrunch funding news
      - "kubernetes site:news.ycombinator.com OR site:reddit.com" - Community discussions

    - Good sources for prospect research:
      - reddit.com - Developer sentiment, product feedback
      - news.ycombinator.com - Tech community discussions
      - seekingalpha.com - Financial analysis, earnings
      - crunchbase.com - Funding rounds, company data
      - techcrunch.com - Startup news, funding announcements
      - linkedin.com/posts - Company updates, hiring signals

    Parameters:
        query: Search query (supports site: syntax)
        max_results: Maximum results (default: 10)
        include_domains: Optional list of domains to filter to
        exclude_domains: Optional list of domains to exclude

    Returns:
        List of search results with title, url, content
    """

    name = "web_search"
    description = "Direct web search using Tavily - supports site: syntax (reddit, hackernews, seekingalpha, etc.)"
    version = "1.0.0"

    def __init__(self, context: SkillContext | None = None):
        super().__init__(context)
        self.tavily = get_tavily()

    async def execute(
        self,
        query: str,
        max_results: int = 10,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> SkillResult[WebSearchData]:
        """Execute web search.

        Args:
            query: Search query
            max_results: Max results to return
            include_domains: Domains to include (site: filter)
            exclude_domains: Domains to exclude

        Returns:
            SkillResult with search results
        """
        self._step("search")

        if not self.tavily.is_configured:
            return SkillResult(
                status=SkillStatus.FAILED,
                error="Tavily API not configured (set TAVILY_API_KEY)",
                data=WebSearchData(query=query),
            )

        # Build search with domain filters
        search_query = query
        if include_domains:
            # Use site: syntax for domain filtering
            site_filter = " OR ".join(f"site:{d}" for d in include_domains[:3])
            search_query = f"({query}) AND ({site_filter})"

        results = self.tavily.search(search_query, max_results, include_domains)

        # Convert to dicts
        result_dicts = [
            {
                "title": r.title,
                "url": r.url,
                "content": r.content,
                "source": r.source,
            }
            for r in results
        ]

        data = WebSearchData(
            query=query,
            results=result_dicts,
            total_found=len(result_dicts),
        )

        if results:
            return SkillResult(
                status=SkillStatus.SUCCESS,
                data=data,
                message=f"Found {len(results)} results for '{query}'",
                steps_completed=["search"],
            )
        else:
            return SkillResult(
                status=SkillStatus.PARTIAL,
                data=data,
                message=f"No results found for '{query}'",
                steps_completed=["search"],
            )


# =============================================================================
# Deep Research Skill
# =============================================================================


@dataclass
class DeepResearchData:
    """Deep research result data."""

    query: str
    research: str = ""
    source: str = "perplexity"

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "research": self.research,
            "source": self.source,
        }


@register_skill
class DeepResearchSkill(BaseSkill):
    """Deep research using Perplexity AI.

    Use this for in-depth research that requires synthesis
    and analysis beyond simple web search. Good for:
    - Company background research
    - Market analysis
    - Technical deep dives
    - Competitive analysis

    Parameters:
        query: Research query/topic
        context: Optional additional context to guide research

    Returns:
        Research summary from Perplexity
    """

    name = "deep_research"
    description = "Deep research using Perplexity AI - for in-depth analysis"
    version = "1.0.0"

    def __init__(self, context: SkillContext | None = None):
        super().__init__(context)
        self.perplexity = get_perplexity()

    async def execute(
        self,
        query: str,
        research_context: str | None = None,
    ) -> SkillResult[DeepResearchData]:
        """Execute deep research.

        Args:
            query: Research query
            research_context: Additional context for research

        Returns:
            SkillResult with research summary
        """
        self._step("research")

        if not self.perplexity.is_configured:
            return SkillResult(
                status=SkillStatus.FAILED,
                error="Perplexity API not configured (set PERPLEXITY_API_KEY)",
                data=DeepResearchData(query=query),
            )

        # Build research prompt
        prompt = query
        if research_context:
            prompt = f"{query}\n\nContext: {research_context}"

        research = self.perplexity.research(prompt)

        if research and "error" not in research.lower():
            data = DeepResearchData(
                query=query,
                research=research,
                source="perplexity",
            )
            return SkillResult(
                status=SkillStatus.SUCCESS,
                data=data,
                message=f"Research completed: {len(research)} chars",
                steps_completed=["research"],
            )
        else:
            return SkillResult(
                status=SkillStatus.FAILED,
                error=research or "Research failed",
                data=DeepResearchData(query=query),
            )


# =============================================================================
# Memory Skills
# =============================================================================


@dataclass
class MemoryData:
    """Memory operation result data."""

    key: str
    value: Any = None
    found: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "found": self.found,
        }


@dataclass
class MemorySearchData:
    """Memory search result data."""

    query: str
    memories: dict[str, Any] = field(default_factory=dict)
    count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "memories": self.memories,
            "count": self.count,
        }


@register_skill
class RecallMemorySkill(BaseSkill):
    """Recall information from persistent memory.

    Use this to retrieve learnings, patterns, or information
    saved from previous runs. Good for:
    - Recalling successful approaches
    - Getting historical data
    - Checking what's been learned

    Parameters:
        key: Optional specific key to recall
        search_all: If True, returns all memories

    Returns:
        Recalled value or all memories
    """

    name = "recall_memory"
    description = (
        "Recall information from persistent memory - learnings, patterns, history"
    )
    version = "1.0.0"

    async def execute(
        self,
        key: str | None = None,
        search_all: bool = False,
    ) -> SkillResult[MemoryData | MemorySearchData]:
        """Recall from memory.

        Args:
            key: Specific key to recall (if None and not search_all, lists keys)
            search_all: If True, returns all memories

        Returns:
            SkillResult with recalled data
        """
        self._step("recall")

        memory = get_goal_memory(self.context.bot_id)

        if search_all:
            # Get all memories
            all_memories = memory.recall_all()
            return SkillResult(
                status=SkillStatus.SUCCESS,
                data=MemorySearchData(
                    query="*",
                    memories=all_memories,
                    count=len(all_memories),
                ),
                message=f"Recalled {len(all_memories)} memories",
                steps_completed=["recall_all"],
            )

        if key:
            # Get specific key
            value = memory.recall(key)
            if value is not None:
                return SkillResult(
                    status=SkillStatus.SUCCESS,
                    data=MemoryData(key=key, value=value, found=True),
                    message=f"Recalled '{key}'",
                    steps_completed=["recall"],
                )
            else:
                return SkillResult(
                    status=SkillStatus.PARTIAL,
                    data=MemoryData(key=key, found=False),
                    message=f"Memory '{key}' not found",
                    steps_completed=["recall"],
                )

        # No key specified - list what we have
        all_memories = memory.recall_all()
        keys = list(all_memories.keys())
        return SkillResult(
            status=SkillStatus.SUCCESS,
            data=MemorySearchData(
                query="keys",
                memories={k: type(v).__name__ for k, v in all_memories.items()},
                count=len(keys),
            ),
            message=f"Found {len(keys)} memory keys: {', '.join(keys[:10])}{'...' if len(keys) > 10 else ''}",
            steps_completed=["list_keys"],
        )


@register_skill
class SaveMemorySkill(BaseSkill):
    """Save information to persistent memory.

    Use this to persist learnings, patterns, or data for future runs.
    Good for:
    - Saving successful patterns
    - Recording learnings
    - Storing processed data

    Parameters:
        key: Memory key (e.g., "successful_signals", "icp_patterns")
        value: Value to store (any JSON-serializable data)

    Returns:
        Confirmation of save
    """

    name = "save_memory"
    description = "Save information to persistent memory - for learnings and patterns"
    version = "1.0.0"

    async def execute(
        self,
        key: str,
        value: Any,
    ) -> SkillResult[MemoryData]:
        """Save to memory.

        Args:
            key: Memory key
            value: Value to store

        Returns:
            SkillResult confirming save
        """
        self._step("save")

        memory = get_goal_memory(self.context.bot_id)
        success = memory.remember(key, value)

        if success:
            return SkillResult(
                status=SkillStatus.SUCCESS,
                data=MemoryData(key=key, value=value, found=True),
                message=f"Saved '{key}' to memory",
                steps_completed=["save"],
            )
        else:
            return SkillResult(
                status=SkillStatus.PARTIAL,
                data=MemoryData(key=key, value=value, found=False),
                message="Memory not persisted (MinIO not configured) but cached for session",
                steps_completed=["save"],
            )


# =============================================================================
# Semantic Memory Search Skill
# =============================================================================


@dataclass
class PastRunData:
    """Data from a past run search."""

    query: str
    runs: list[dict[str, Any]] = field(default_factory=list)
    total_found: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "runs": self.runs,
            "total_found": self.total_found,
        }


@register_skill
class SearchPastRunsSkill(BaseSkill):
    """Search past runs using semantic similarity.

    Use this to find relevant context from previous goal executions.
    Searches over LLM-generated summaries of past sessions.

    POWERFUL FOR:
    - "What did we learn about companies with funding?"
    - "Find previous research on AI infrastructure"
    - "What prospects did we find in DevOps space?"
    - "Any past runs about Series B startups?"

    Features:
    - Hybrid search: vector similarity + keyword matching
    - Temporal decay: recent runs rank higher
    - MMR diversity: avoids redundant results

    Parameters:
        query: Natural language query (semantic search)
        limit: Maximum results (default: 5)
        use_hybrid: Enable BM25 keyword matching (default: True)

    Returns:
        List of matching past runs with summaries and metadata
    """

    name = "search_past_runs"
    description = "Semantic search over past runs - find relevant context and learnings"
    version = "1.0.0"

    async def execute(
        self,
        query: str,
        limit: int = 5,
        use_hybrid: bool = True,
    ) -> SkillResult[PastRunData]:
        """Search past runs semantically.

        Args:
            query: Natural language query
            limit: Max results
            use_hybrid: Use vector + BM25 (default: True)

        Returns:
            SkillResult with matching past runs
        """
        self._step("search")

        # Import vector memory
        from ..services.vector_memory import get_vector_memory

        vector_memory = get_vector_memory(self.context.bot_id)

        try:
            results = await vector_memory.search(
                query=query,
                limit=limit,
                use_hybrid=use_hybrid,
                use_mmr=True,  # Always use diversity
                apply_temporal_decay=True,
            )

            # Format for agent consumption
            runs = []
            for r in results:
                runs.append(
                    {
                        "summary": r.get("summary", ""),
                        "outcome": r.get("outcome", ""),
                        "goal": r.get("goal", ""),
                        "companies": r.get("companies", []),
                        "queries": r.get("queries", []),
                        "score": round(r.get("score", 0), 3),
                        "created_at": r.get("created_at", ""),
                    }
                )

            if runs:
                return SkillResult(
                    status=SkillStatus.SUCCESS,
                    data=PastRunData(
                        query=query,
                        runs=runs,
                        total_found=len(runs),
                    ),
                    message=f"Found {len(runs)} relevant past runs",
                    steps_completed=["search"],
                )
            else:
                return SkillResult(
                    status=SkillStatus.PARTIAL,
                    data=PastRunData(query=query, runs=[], total_found=0),
                    message="No matching past runs found",
                    steps_completed=["search"],
                )

        except Exception as e:
            logger.warning(f"Past runs search failed: {e}")
            return SkillResult(
                status=SkillStatus.FAILED,
                data=PastRunData(query=query, runs=[], total_found=0),
                message=f"Search failed: {e}",
                error=str(e),
                steps_completed=["search"],
            )


@register_skill
class CheckCompanyResearchedSkill(BaseSkill):
    """Check if a company was already researched in any past run.

    Use this to avoid duplicate work - check before researching a company.

    Parameters:
        company_name: Company name to check

    Returns:
        Whether the company was previously researched
    """

    name = "check_company_researched"
    description = "Check if a company was already researched - avoid duplicates"
    version = "1.0.0"

    async def execute(
        self,
        company_name: str,
    ) -> SkillResult[dict[str, Any]]:
        """Check if company was researched.

        Args:
            company_name: Company to check

        Returns:
            SkillResult with researched status
        """
        self._step("check")

        memory = get_goal_memory(self.context.bot_id)
        was_researched = memory.was_company_researched(company_name)

        return SkillResult(
            status=SkillStatus.SUCCESS,
            data={
                "company": company_name,
                "previously_researched": was_researched,
            },
            message=f"{company_name}: {'already researched' if was_researched else 'not yet researched'}",
            steps_completed=["check"],
        )


@register_skill
class MarkCompanyResearchedSkill(BaseSkill):
    """Mark a company as researched (for deduplication).

    Call this after researching a company to prevent duplicate work
    in future runs.

    Parameters:
        company_name: Company name to mark

    Returns:
        Confirmation
    """

    name = "mark_company_researched"
    description = "Mark a company as researched - for deduplication"
    version = "1.0.0"

    async def execute(
        self,
        company_name: str,
    ) -> SkillResult[dict[str, Any]]:
        """Mark company as researched.

        Args:
            company_name: Company to mark

        Returns:
            SkillResult confirming mark
        """
        self._step("mark")

        memory = get_goal_memory(self.context.bot_id)
        memory.log_company_researched(company_name)

        return SkillResult(
            status=SkillStatus.SUCCESS,
            data={
                "company": company_name,
                "marked": True,
            },
            message=f"Marked '{company_name}' as researched",
            steps_completed=["mark"],
        )


@register_skill
class ListProspectsSkill(BaseSkill):
    """List saved prospects from memory.

    Use this to review prospects that have been saved
    by previous research runs.

    Parameters:
        limit: Maximum number of prospects to return (default: 20)

    Returns:
        List of saved prospects
    """

    name = "list_prospects"
    description = "List saved prospects from memory - review previous research"
    version = "1.0.0"

    async def execute(
        self,
        limit: int = 20,
    ) -> SkillResult[dict[str, Any]]:
        """List prospects.

        Args:
            limit: Max prospects to return

        Returns:
            SkillResult with prospect list
        """
        self._step("list")

        memory = get_goal_memory(self.context.bot_id)
        prospects = memory.list_prospects(limit=limit)

        return SkillResult(
            status=SkillStatus.SUCCESS,
            data={"prospects": prospects, "count": len(prospects)},
            message=f"Found {len(prospects)} saved prospects",
            steps_completed=["list"],
        )


@register_skill
class GetRunHistorySkill(BaseSkill):
    """Get recent run history.

    Use this to review what happened in previous runs.

    Parameters:
        limit: Maximum number of runs to return (default: 10)

    Returns:
        List of recent runs with status and results
    """

    name = "get_run_history"
    description = "Get recent run history - review previous executions"
    version = "1.0.0"

    async def execute(
        self,
        limit: int = 10,
    ) -> SkillResult[dict[str, Any]]:
        """Get run history.

        Args:
            limit: Max runs to return

        Returns:
            SkillResult with run history
        """
        self._step("get_history")

        memory = get_goal_memory(self.context.bot_id)
        runs = memory.get_recent_runs(limit=limit)

        return SkillResult(
            status=SkillStatus.SUCCESS,
            data={"runs": runs, "count": len(runs)},
            message=f"Found {len(runs)} recent runs",
            steps_completed=["get_history"],
        )


# =============================================================================
# Rephrase / Unstick Skill
# =============================================================================


@dataclass
class RephraseData:
    """Rephrase result data."""

    original: str
    alternatives: list[str] = field(default_factory=list)
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "original": self.original,
            "alternatives": self.alternatives,
            "reasoning": self.reasoning,
        }


@register_skill
class RephraseSkill(BaseSkill):
    """Generate alternative phrases, queries, or approaches.

    Use this when stuck - searches returning nothing, need fresh angles,
    or want to explore a topic from different perspectives.

    Good for:
    - Alternative search queries when results are empty
    - Company name variations (Inc, Corp, Labs, etc.)
    - Signal keyword expansion (hiring → growing team, open roles)
    - Brainstorming different angles on a problem
    - Finding synonyms and related terms

    Parameters:
        text: The phrase/query to rephrase
        goal: What you're trying to achieve (guides the rephrasing)
        count: Number of alternatives to generate (default: 5)
        style: Rephrasing style - "search" (query-optimized), "expand" (broader),
               "narrow" (more specific), "creative" (lateral thinking)

    Returns:
        List of alternative phrases with reasoning

    Examples:
        rephrase(text="Acme Corp DevOps hiring", goal="find job postings")
        rephrase(text="series B funding", goal="find investment signals", style="expand")
        rephrase(text="kubernetes platform", goal="search queries", count=10)
    """

    name = "rephrase"
    description = (
        "Generate alternative phrases/queries - unstick tool for when searches fail"
    )
    version = "1.0.0"

    def __init__(self, context: SkillContext | None = None):
        super().__init__(context)
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

    async def execute(
        self,
        text: str,
        goal: str = "find alternative search queries",
        count: int = 5,
        style: str = "search",
    ) -> SkillResult[RephraseData]:
        """Generate alternative phrases.

        Args:
            text: Original phrase to rephrase
            goal: What you're trying to achieve
            count: Number of alternatives
            style: Rephrasing style (search, expand, narrow, creative)

        Returns:
            SkillResult with alternatives
        """
        self._step("rephrase")

        data = RephraseData(original=text)

        # Style-specific instructions
        style_prompts = {
            "search": "Optimize for search engines and databases. Use exact phrases, boolean operators, site: syntax where helpful.",
            "expand": "Broaden the scope. Include synonyms, related concepts, parent categories, and adjacent topics.",
            "narrow": "Make more specific. Add qualifiers, specific terms, exact matches, and filters.",
            "creative": "Think laterally. What are unexpected angles, contrarian views, or non-obvious connections?",
        }

        style_instruction = style_prompts.get(style, style_prompts["search"])

        prompt = f"""Generate {count} alternative phrasings for the following.

Original: "{text}"
Goal: {goal}
Style: {style_instruction}

Return ONLY a JSON object with this structure:
{{
  "alternatives": ["phrase 1", "phrase 2", ...],
  "reasoning": "Brief explanation of the approach"
}}

Be practical and actionable. Each alternative should be directly usable."""

        if not self.openai_api_key:
            # Fallback: simple variations without LLM
            alternatives = self._generate_simple_alternatives(text, count)
            data.alternatives = alternatives
            data.reasoning = "Generated without LLM (API key not configured)"
            return SkillResult(
                status=SkillStatus.PARTIAL,
                data=data,
                message=f"Generated {len(alternatives)} simple alternatives (no LLM)",
                steps_completed=["rephrase_fallback"],
            )

        try:
            import json

            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 500,
                        "response_format": {"type": "json_object"},
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    parsed = json.loads(content)

                    data.alternatives = parsed.get("alternatives", [])[:count]
                    data.reasoning = parsed.get("reasoning", "")

                    return SkillResult(
                        status=SkillStatus.SUCCESS,
                        data=data,
                        message=f"Generated {len(data.alternatives)} alternatives ({style} style)",
                        steps_completed=["rephrase"],
                    )
                else:
                    # Fallback on API error
                    alternatives = self._generate_simple_alternatives(text, count)
                    data.alternatives = alternatives
                    data.reasoning = f"API error {response.status_code}, used fallback"
                    return SkillResult(
                        status=SkillStatus.PARTIAL,
                        data=data,
                        message=f"Generated {len(alternatives)} fallback alternatives",
                        steps_completed=["rephrase_fallback"],
                    )

        except Exception as e:
            logger.error(f"Rephrase error: {e}")
            alternatives = self._generate_simple_alternatives(text, count)
            data.alternatives = alternatives
            data.reasoning = f"Error: {e}, used fallback"
            return SkillResult(
                status=SkillStatus.PARTIAL,
                data=data,
                message=f"Generated {len(alternatives)} fallback alternatives",
                steps_completed=["rephrase_fallback"],
            )

    def _generate_simple_alternatives(self, text: str, count: int) -> list[str]:
        """Generate simple alternatives without LLM."""
        alternatives = []
        words = text.split()

        # Original with quotes
        alternatives.append(f'"{text}"')

        # Remove common suffixes
        for suffix in [" Inc", " Corp", " LLC", " Ltd", " Labs", " AI", " HQ"]:
            if text.endswith(suffix):
                alternatives.append(text[: -len(suffix)])

        # Add common suffixes if not present
        if not any(text.endswith(s) for s in [" Inc", " Corp", " Labs"]):
            alternatives.append(f"{text} Inc")

        # Reorder words
        if len(words) >= 2:
            alternatives.append(" ".join(reversed(words)))

        # Key terms only (longer phrases)
        if len(words) >= 3:
            alternatives.append(" ".join(words[:2]))
            alternatives.append(" ".join(words[-2:]))

        # Add site filters for common use cases
        if any(kw in text.lower() for kw in ["hire", "job", "hiring", "career"]):
            alternatives.append(f"{text} site:linkedin.com")
        if any(kw in text.lower() for kw in ["fund", "series", "raise", "invest"]):
            alternatives.append(f"{text} site:techcrunch.com")

        return alternatives[:count]
