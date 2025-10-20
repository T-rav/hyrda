"""Utilities for company profile deep research workflow.

Helper functions for tool integration, token management, and model configuration.
"""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# Reflection tool for strategic thinking
@tool
def think_tool(reflection: str) -> str:
    """Use this tool to record your strategic thinking and planning.

    Args:
        reflection: Your thoughts about the research progress, what to do next,
                   or when to stop researching.

    Returns:
        Confirmation message
    """
    logger.info(f"Researcher reflection: {reflection[:100]}...")
    return f"Reflection recorded: {reflection}"


# Internal search tool - singleton pattern
class _InternalSearchToolSingleton:
    """Singleton holder for internal search tool."""

    _instance = None

    @classmethod
    def get_instance(cls):
        """Get or create singleton instance."""
        if cls._instance is not None:
            return cls._instance

        try:
            from agents.company_profile.tools import InternalSearchTool

            cls._instance = InternalSearchTool()
            logger.info("Internal search tool singleton initialized")
            return cls._instance
        except Exception as e:
            logger.warning(f"Failed to create internal search tool: {e}")
            return None


def internal_search_tool():
    """Get internal search tool singleton instance.

    The tool searches the internal knowledge base (vector database) for existing information.
    Use this FIRST before web search to check if we already have information about:
    - Existing customers or past clients
    - Previous projects or engagements
    - Internal documentation
    - Historical company data

    IMPORTANT: Only call with specific company names or topics (minimum 3 characters).
    DO NOT call with empty queries.

    Returns:
        InternalSearchTool singleton instance or None if not available
    """
    return _InternalSearchToolSingleton.get_instance()


class _SECQueryToolSingleton:
    """Singleton for SEC query tool."""

    _instance = None

    @classmethod
    def get_instance(cls):
        """Get or create singleton instance."""
        if cls._instance is None:
            try:
                from agents.company_profile.tools.sec_query import SECQueryTool

                cls._instance = SECQueryTool()
                logger.info("Initialized sec_query tool singleton")
            except Exception as e:
                logger.error(f"Failed to initialize sec_query tool: {e}")
                return None

        return cls._instance


def sec_query_tool():
    """Get SEC query tool singleton instance.

    The tool fetches and searches SEC filings on-demand (10-K annual reports, 8-K events):
    - Risk factors and strategic challenges
    - Financial performance and trends
    - Executive changes and leadership movements (8-K Item 5.02)
    - Material events, acquisitions, partnerships
    - Strategic priorities and initiatives
    - Technology investments and R&D spending

    Uses on-demand fetching (no pre-indexing) with in-memory vectorization.
    Fetches latest 10-K + 4 most recent 8-Ks when called.

    IMPORTANT: Must include company name or ticker symbol in query (minimum 3 characters).
    DO NOT call with empty queries.

    Returns:
        SECQueryTool singleton instance or None if not available
    """
    return _SECQueryToolSingleton.get_instance()


async def search_tool(
    config: RunnableConfig, perplexity_enabled: bool = False
) -> list[Any]:
    """Get appropriate search tools based on configuration.

    Args:
        config: RunnableConfig with configuration settings
        perplexity_enabled: Whether deep_research is enabled (from SEARCH_PERPLEXITY_ENABLED)

    Returns:
        List of search tools (always includes web_search/scrape_url, adds deep_research if enabled)
    """
    from services.search_clients import get_tavily_client, get_tool_definitions

    tavily_client = get_tavily_client()

    # Determine if we should include deep_research based on settings
    if perplexity_enabled:
        # Deep research enabled: Include all tools including Perplexity
        logger.info(
            "Research tools: Using full toolkit (web_search, scrape_url, deep_research)"
        )
    else:
        if not tavily_client:
            logger.warning("No search client available for profile research")
            return []
        # Deep research not available: Only Tavily tools
        logger.info(
            "Research tools: Using exploration tools only (web_search, scrape_url)"
        )

    # Get tool definitions
    tools = get_tool_definitions(include_deep_research=perplexity_enabled)
    return tools


def is_token_limit_exceeded(exception: Exception, model_name: str) -> bool:
    """Detect if exception is due to token limit being exceeded.

    Args:
        exception: Exception raised by LLM call
        model_name: Model name being used

    Returns:
        True if token limit error, False otherwise
    """
    error_msg = str(exception).lower()

    # OpenAI error patterns
    openai_patterns = [
        "maximum context length",
        "context_length_exceeded",
        "tokens exceed",
        "too many tokens",
    ]

    # Anthropic error patterns
    anthropic_patterns = [
        "prompt is too long",
        "maximum context",
        "context length",
    ]

    all_patterns = openai_patterns + anthropic_patterns

    for pattern in all_patterns:
        if pattern in error_msg:
            logger.warning(f"Token limit exceeded for {model_name}: {error_msg[:100]}")
            return True

    return False


def remove_up_to_last_ai_message(messages: list) -> list:
    """Remove messages up to and including the last AI message for retry.

    Used when token limits are exceeded - truncates history for retry.

    Args:
        messages: List of messages

    Returns:
        Truncated message list
    """
    # Find last AI message
    last_ai_index = -1
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if hasattr(msg, "type") and msg.type == "ai":
            last_ai_index = i
            break

    if last_ai_index > 0:
        # Keep messages after last AI message
        truncated = messages[last_ai_index + 1 :]
        logger.info(f"Truncated {last_ai_index + 1} messages for retry")
        return truncated

    # If no AI message found, remove first half
    midpoint = len(messages) // 2
    logger.info(f"No AI message found, removing first {midpoint} messages")
    return messages[midpoint:]


def get_api_key_for_model(model_name: str, config: RunnableConfig) -> str | None:
    """Extract API key from config based on model provider.

    Args:
        model_name: Model name in format "provider:model"
        config: RunnableConfig

    Returns:
        API key string or None
    """
    # Model name format: "provider:model" or just "model"
    provider = model_name.split(":")[0].lower() if ":" in model_name else "openai"

    # Try to get from config first
    if config and "configurable" in config:
        configurable = config["configurable"]
        api_key = configurable.get(f"{provider}_api_key")
        if api_key:
            return api_key

    # Fallback to environment (handled by LLM service in main app)
    return None


async def format_research_context(
    research_brief: str,
    notes: list[str],
    profile_type: str,
    max_sources: int = 25,
) -> str:
    """Format research context for final report generation.

    Extracts all sources from individual research notes and creates a consolidated
    global source list, renumbering citations throughout. Limits sources to top N
    to fit within token budgets.

    Args:
        research_brief: Original research plan
        notes: List of compressed research findings
        profile_type: Type of profile (company, employee, project)
        max_sources: Maximum number of sources to include (default 25)

    Returns:
        Formatted context string with global source numbering
    """
    import re

    # Extract all sources from all notes
    global_sources = []  # List of (url, description) tuples
    source_url_to_global_num = {}  # Map URL -> global citation number
    renumbered_notes = []

    for note in notes:
        # Find ### Sources section in this note
        sources_match = re.search(
            r"### Sources\s*\n(.*?)(?=\n###|\n##|$)", note, re.DOTALL
        )

        if sources_match:
            sources_section = sources_match.group(1).strip()
            # Split sources into main content and sources
            note_content = note[: sources_match.start()].strip()

            # Parse individual sources from this note
            # Format: "1. URL - description" or "1. URL"
            source_lines = []
            for line in sources_section.split("\n"):
                match = re.match(r"^\d+\.\s+(.+?)(?:\s+-\s+(.+))?$", line.strip())
                if match:
                    url = match.group(1).strip()
                    desc = match.group(2).strip() if match.group(2) else ""
                    source_lines.append((url, desc))

            # Map local citation numbers to global numbers
            local_to_global = {}
            for local_num, (url, desc) in enumerate(source_lines, 1):
                # Check if we've seen this URL before
                if url not in source_url_to_global_num:
                    global_sources.append((url, desc))
                    source_url_to_global_num[url] = len(global_sources)

                local_to_global[local_num] = source_url_to_global_num[url]

            # Renumber citations in note content
            # Replace [1], [2], etc. with global numbers
            # Use lambda to avoid loop variable binding issues
            renumbered_content = re.sub(
                r"\[(\d+)\]",
                lambda m,
                mapping=local_to_global: f"[{mapping.get(int(m.group(1)), int(m.group(1)))}]",
                note_content,
            )
            renumbered_notes.append(renumbered_content)
        else:
            # No sources section found, keep note as-is
            renumbered_notes.append(note)

    # Prune sources to max_sources if needed (use LLM to select top N)
    original_source_count = len(global_sources)
    if len(global_sources) > max_sources:
        logger.info(
            f"Pruning sources from {len(global_sources)} to {max_sources} using LLM selection"
        )

        # Use LLM to intelligently select top N most relevant sources
        import json

        from langchain_openai import ChatOpenAI

        from config.settings import Settings

        settings = Settings()

        # Identify premium sources (deep research from Perplexity, internal knowledge base)
        deep_research_indices = []
        internal_search_indices = []
        regular_sources_indices = []

        for i, (url, desc) in enumerate(global_sources, 1):
            # Check if this source came from deep_research tool (comprehensive Perplexity analysis)
            if "Deep Research Results" in desc or "perplexity" in url.lower():
                deep_research_indices.append(i)
            # Check if this source came from internal_search_tool (internal knowledge base)
            elif "Internal search" in desc or "internal knowledge" in desc.lower():
                internal_search_indices.append(i)
            else:
                regular_sources_indices.append(i)

        logger.info(
            f"Source breakdown: {len(deep_research_indices)} deep research, "
            f"{len(internal_search_indices)} internal knowledge, "
            f"{len(regular_sources_indices)} regular"
        )

        # Build source list for LLM with markers
        sources_text = "\n".join(
            [
                f"{i}. {url} - {desc} [DEEP_RESEARCH]"
                if i in deep_research_indices
                else (
                    f"{i}. {url} - {desc} [INTERNAL_KB]"
                    if i in internal_search_indices
                    else (f"{i}. {url} - {desc}" if desc else f"{i}. {url}")
                )
                for i, (url, desc) in enumerate(global_sources, 1)
            ]
        )

        # Calculate minimum premium sources to include
        # IMPORTANT: Require at least 5 deep research, 2 internal (or all available if less)
        # Don't let LLM skip expensive Perplexity sources
        min_deep_research = min(5, len(deep_research_indices))
        min_internal = min(2, len(internal_search_indices))

        selection_prompt = f"""You are selecting the top {max_sources} most relevant and important sources from a list of {len(global_sources)} sources for a company profile report.

**All Available Sources:**
{sources_text}

**Selection Criteria (IN ORDER OF PRIORITY):**
1. **CRITICAL - NON-NEGOTIABLE**: You MUST include AT LEAST {min_deep_research} sources marked [DEEP_RESEARCH]
   - These are comprehensive Perplexity AI analyses (expensive, high-value)
   - If {min_deep_research} > 0, you CANNOT submit a selection without at least that many [DEEP_RESEARCH] sources
   - These are the MOST IMPORTANT sources to include
2. **CRITICAL**: Include AT LEAST {min_internal} sources marked [INTERNAL_KB] - internal knowledge base data (proprietary information)
3. Prioritize authoritative sources (official company sites, SEC filings, reputable news)
4. Include diverse source types (company site, news, financial data, industry analysis)
5. Prefer sources with detailed descriptions (indicates rich content)
6. Balance recency with authority
7. Avoid duplicate or redundant sources

**Your Task:**
Return a JSON array of the source numbers (1-{len(global_sources)}) you want to keep, in order of importance.
You MUST select exactly {max_sources} sources.

**MANDATORY REQUIREMENT:**
- If {min_deep_research} > 0: You MUST include at least {min_deep_research} sources with [DEEP_RESEARCH] tag
- If {min_internal} > 0: You MUST include at least {min_internal} sources with [INTERNAL_KB] tag
- Failure to meet these requirements is NOT ACCEPTABLE

Example response format:
```json
[1, 5, 8, 12, 15, 18, 20, 23, 25, 28, 30, 32, 35, 38, 40, 42, 45, 48, 50, 52, 55, 58, 60, 62, 65]
```

Return ONLY the JSON array, no explanation."""

        try:
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                api_key=settings.llm.api_key,
                temperature=0.0,
                max_completion_tokens=200,
            )

            response = await llm.ainvoke(selection_prompt)
            response_text = response.content.strip()

            # Parse JSON response
            json_match = re.search(
                r"```json\s*(\[.*?\])\s*```", response_text, re.DOTALL
            )
            if json_match:
                selected_indices = json.loads(json_match.group(1))
            else:
                # Try to parse directly
                selected_indices = json.loads(response_text)

            logger.info(
                f"LLM selected {len(selected_indices)} sources: {selected_indices[:5]}..."
            )

            # Validate premium source inclusion
            deep_research_selected = [
                idx for idx in selected_indices if idx in deep_research_indices
            ]
            internal_selected = [
                idx for idx in selected_indices if idx in internal_search_indices
            ]
            logger.info(
                f"Premium sources selected: {len(deep_research_selected)}/{min_deep_research} deep research, "
                f"{len(internal_selected)}/{min_internal} internal KB"
            )

            # ENFORCE MINIMUM: If LLM didn't include enough deep research sources, force them in
            if len(deep_research_selected) < min_deep_research:
                logger.warning(
                    f"LLM only selected {len(deep_research_selected)}/{min_deep_research} deep research sources - forcing missing ones"
                )
                # Add missing deep research sources
                missing_count = min_deep_research - len(deep_research_selected)
                unselected_deep_research = [
                    idx for idx in deep_research_indices if idx not in selected_indices
                ]
                for idx in unselected_deep_research[:missing_count]:
                    selected_indices.append(idx)
                    logger.info(f"Forced inclusion of deep research source {idx}")

            # ENFORCE MINIMUM: If LLM didn't include enough internal sources, force them in
            if len(internal_selected) < min_internal:
                logger.warning(
                    f"LLM only selected {len(internal_selected)}/{min_internal} internal sources - forcing missing ones"
                )
                # Add missing internal sources
                missing_count = min_internal - len(internal_selected)
                unselected_internal = [
                    idx
                    for idx in internal_search_indices
                    if idx not in selected_indices
                ]
                for idx in unselected_internal[:missing_count]:
                    selected_indices.append(idx)
                    logger.info(f"Forced inclusion of internal source {idx}")

            # If we now have too many sources (after forcing), trim lowest priority non-premium sources
            if len(selected_indices) > max_sources:
                logger.warning(
                    f"After forcing premium sources, have {len(selected_indices)} sources - trimming to {max_sources}"
                )
                # Keep all forced premium sources, trim regular ones
                premium_indices = set(deep_research_indices + internal_search_indices)
                regular_selected = [
                    idx for idx in selected_indices if idx not in premium_indices
                ]
                premium_selected = [
                    idx for idx in selected_indices if idx in premium_indices
                ]
                # Trim regular sources to fit
                trim_count = len(selected_indices) - max_sources
                selected_indices = (
                    premium_selected
                    + regular_selected[: -trim_count if trim_count > 0 else None]
                )

            logger.info(f"Final selection: {len(selected_indices)} sources")

            # Build mapping: old index -> new index (or None if pruned)
            old_to_new = {}
            new_sources = []
            for new_idx, old_idx in enumerate(selected_indices, 1):
                if 1 <= old_idx <= len(global_sources):
                    old_to_new[old_idx] = new_idx
                    new_sources.append(global_sources[old_idx - 1])  # 0-indexed

            global_sources = new_sources

            # Renumber citations in notes based on new mapping
            remapped_notes = []
            for note in renumbered_notes:
                # Replace citations with new numbers or remove if pruned
                remapped_note = re.sub(
                    r"\[(\d+)\]",
                    lambda m: f"[{old_to_new[int(m.group(1))]}]"
                    if int(m.group(1)) in old_to_new
                    else "",
                    note,
                )
                remapped_notes.append(remapped_note)
            renumbered_notes = remapped_notes

        except Exception as e:
            logger.error(
                f"LLM source selection failed: {e}, falling back to first {max_sources}"
            )
            # Fallback: keep first N
            global_sources = global_sources[:max_sources]

            # Remove citations beyond max_sources
            pruned_notes = []
            for note in renumbered_notes:
                pruned_note = re.sub(
                    r"\[(\d+)\]",
                    lambda m: (m.group(0) if int(m.group(1)) <= max_sources else ""),
                    note,
                )
                pruned_notes.append(pruned_note)
            renumbered_notes = pruned_notes

    # Build context with renumbered notes
    context = "# Profile Research Context\n\n"
    context += f"**Profile Type**: {profile_type}\n\n"
    context += f"**Research Brief**:\n{research_brief}\n\n"
    context += f"**Research Findings** ({len(renumbered_notes)} sections):\n\n"

    for i, note in enumerate(renumbered_notes, 1):
        context += f"## Finding {i}\n\n{note}\n\n"

    # Add consolidated global sources list
    if global_sources:
        context += "\n\n---\n\n"
        context += "# CONSOLIDATED SOURCE LIST FOR YOUR REFERENCE\n\n"
        context += "**All sources from research findings (use these citation numbers in your report):**\n\n"
        for num, (url, desc) in enumerate(global_sources, 1):
            if desc:
                context += f"{num}. {url} - {desc}\n"
            else:
                context += f"{num}. {url}\n"
        context += f"\n**Total sources available: {len(global_sources)}**\n\n"
        context += "**IMPORTANT**: When writing your report, use these source numbers [1] through"
        context += f" [{len(global_sources)}] and ensure your ## Sources section lists ALL {len(global_sources)} sources.\n"

    if original_source_count > max_sources:
        logger.info(
            f"Formatted context: {len(renumbered_notes)} notes, {len(global_sources)} sources (pruned from {original_source_count})"
        )
    else:
        logger.info(
            f"Formatted context: {len(renumbered_notes)} notes, {len(global_sources)} unique sources"
        )

    # Check context size and truncate if needed
    # Gemini 2.5 Pro: 1M input + 64K output = use ~900K for context (100K buffer)
    # Rough estimate: 1 token ≈ 4 characters
    max_context_chars = 900000 * 4  # ~3.6M characters for 900K tokens

    if len(context) > max_context_chars:
        logger.warning(
            f"Context too large ({len(context)} chars ≈ {len(context) // 4} tokens). "
            f"Truncating to fit within {max_context_chars // 4}K token budget."
        )

        # Keep header and sources, truncate notes proportionally
        header_end = context.find("## Finding 1")
        sources_start = context.find("\n\n---\n\n# CONSOLIDATED SOURCE LIST")

        if header_end > 0 and sources_start > 0:
            header = context[:header_end]
            sources = context[sources_start:]
            notes_text = context[header_end:sources_start]

            # Calculate how much space we have for notes
            available_for_notes = max_context_chars - len(header) - len(sources)

            if len(notes_text) > available_for_notes:
                # Truncate notes_text
                notes_text = notes_text[:available_for_notes]
                # Cut at last complete sentence
                last_period = notes_text.rfind(".\n")
                if (
                    last_period > available_for_notes * 0.9
                ):  # Only cut if we find a period in last 10%
                    notes_text = notes_text[: last_period + 2]

                notes_text += "\n\n[... additional research notes truncated to fit context window ...]\n\n"
                logger.info(
                    f"Truncated notes from {context[header_end:sources_start].__len__()} to {len(notes_text)} chars"
                )

            context = header + notes_text + sources

    logger.info(
        f"Final context size: {len(context)} chars ≈ {len(context) // 4} tokens"
    )
    return context


async def extract_company_from_url(url: str) -> str | None:
    """Extract company name from a URL by fetching and parsing the page.

    Fetches the URL and extracts the company name from:
    - <title> tag
    - og:site_name meta tag
    - og:title meta tag
    - Twitter card site name

    Args:
        url: URL to fetch and extract company name from

    Returns:
        Extracted company name or None if extraction fails

    Examples:
        "https://www.costco.com" → "Costco"
        "https://stripe.com" → "Stripe"
        "www.tesla.com" → "Tesla"
    """
    import re

    import requests
    from bs4 import BeautifulSoup

    try:
        # Ensure URL has protocol
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        logger.info(f"Fetching URL to extract company name: {url}")

        # Fetch the page with timeout
        response = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )
        response.raise_for_status()

        # Parse HTML
        soup = BeautifulSoup(response.content, "html.parser")

        # Try multiple extraction methods in order of preference
        company_name = None

        # 1. og:site_name (most reliable for company name)
        og_site_name = soup.find("meta", property="og:site_name")
        if og_site_name and hasattr(og_site_name, "get"):
            content = og_site_name.get("content")  # type: ignore[union-attr]
            if content:
                company_name = str(content).strip()
                logger.info(f"Extracted from og:site_name: {company_name}")
                return company_name

        # 2. Twitter card site name
        twitter_site = soup.find("meta", attrs={"name": "twitter:site"})
        if twitter_site and hasattr(twitter_site, "get"):
            content = twitter_site.get("content")  # type: ignore[union-attr]
            if content:
                # Remove @ symbol if present
                company_name = str(content).strip().lstrip("@")
                logger.info(f"Extracted from twitter:site: {company_name}")
                return company_name

        # 3. <title> tag (extract company name, remove common suffixes)
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title = title_tag.string.strip()
            # Remove common suffixes like " | Home", " - Official Site", etc.
            cleaned_title = re.split(r"[\|\-\–:]", title)[0].strip()
            # Remove common words
            cleaned_title = re.sub(
                r"\b(Home|Official Site|Welcome|Homepage)\b",
                "",
                cleaned_title,
                flags=re.IGNORECASE,
            ).strip()
            if cleaned_title:
                logger.info(f"Extracted from title tag: {cleaned_title}")
                return cleaned_title

        # 4. og:title (fallback)
        og_title = soup.find("meta", property="og:title")
        if og_title and hasattr(og_title, "get"):
            content = og_title.get("content")  # type: ignore[union-attr]
            if content:
                company_name = str(content).strip()
                logger.info(f"Extracted from og:title: {company_name}")
                return company_name

        logger.warning(f"Could not extract company name from URL: {url}")
        return None

    except Exception as e:
        logger.error(f"Error extracting company from URL {url}: {e}")
        return None


def detect_profile_type(query: str) -> str:
    """Detect the type of profile from the query.

    This agent is scoped to company profiles only.

    Args:
        query: User query

    Returns:
        Profile type: always "company"
    """
    # Scoped to company profiles only
    return "company"


async def extract_focus_area(query: str, llm_service: Any = None) -> str:
    """Extract specific focus area or intent from user query using LLM.

    Identifies if user is asking about a specific aspect like "AI needs",
    "hiring challenges", "cloud strategy", etc.

    Args:
        query: User query
        llm_service: Optional LLM service for extraction (if not provided, creates one)

    Returns:
        Focus area description or empty string if general profile requested

    Examples:
        "profile tesla" -> ""
        "profile tesla's ai needs" -> "AI needs and capabilities"
        "profile tesla and its ai needs" -> "AI needs and capabilities"
        "tell me about acme's hiring challenges" -> "hiring challenges and talent acquisition"
        "what are stripe's product strategy" -> "product strategy and roadmap"
    """
    import json

    from langchain_openai import ChatOpenAI

    from config.settings import Settings

    try:
        settings = Settings()

        extraction_prompt = f"""Analyze this user query and extract the specific focus area or aspect they're interested in.

Query: "{query}"

Look for ANY specific aspect or focus the user is asking about, such as:
- AI/ML needs, capabilities, strategy, initiatives
- Hiring, talent, recruiting challenges
- Product strategy, roadmap, initiatives
- Engineering challenges, team structure, practices
- DevOps, infrastructure, cloud strategy
- Security, compliance, privacy
- Sales, revenue, go-to-market strategy
- Technical debt, code quality
- Data strategy, analytics
- Mobile strategy, apps
- Customer success, support

Pay attention to phrases like:
- "and its X" → extract X as focus
- "X needs" → extract X needs as focus
- "about X" → extract X as focus
- "X strategy" → extract X strategy as focus

If the user is asking about a SPECIFIC aspect, extract and return that focus area.
If they're asking for a general profile with no specific focus, return an empty string.

Examples:
- "profile tesla" → ""
- "profile tesla's ai needs" → "AI needs and capabilities"
- "profile tesla and its ai needs" → "AI needs and capabilities"
- "tell me about stripe's payment infrastructure" → "payment infrastructure and processing capabilities"
- "what are snowflake's data governance practices" → "data governance and compliance practices"
- "acme corp hiring challenges" → "hiring challenges and talent acquisition"
- "profile google devops practices" → "DevOps practices and infrastructure"

Return ONLY a JSON object: {{"focus_area": "extracted focus or empty string"}}"""

        llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.llm.api_key,
            temperature=0.0,
            max_completion_tokens=100,
            model_kwargs={"response_format": {"type": "json_object"}},
        )

        response = await llm.ainvoke(extraction_prompt)
        result_text = response.content.strip()

        # Parse JSON response (guaranteed to be valid JSON with response_format)
        result_data = json.loads(result_text)
        focus_area = result_data.get("focus_area", "").strip()

        if focus_area:
            logger.info(f"LLM extracted focus area: '{focus_area}'")
        else:
            logger.info("LLM determined no specific focus area (general profile)")

        return focus_area

    except Exception as e:
        logger.error(f"Error using LLM for focus extraction: {e}", exc_info=True)
        # Return empty string on error (general profile)
        logger.info("Falling back to general profile due to extraction error")
        return ""


def create_system_message(prompt: str, **kwargs: Any) -> SystemMessage:
    """Create a system message with formatted prompt.

    Args:
        prompt: Prompt template string
        **kwargs: Variables to format into prompt

    Returns:
        SystemMessage instance
    """
    formatted_prompt = prompt.format(**kwargs)
    return SystemMessage(content=formatted_prompt)


def create_human_message(content: str) -> HumanMessage:
    """Create a human message.

    Args:
        content: Message content

    Returns:
        HumanMessage instance
    """
    return HumanMessage(content=content)


def estimate_tokens(text: str) -> int:
    """Estimate token count for text (rough approximation).

    Args:
        text: Text to estimate

    Returns:
        Estimated token count (chars / 4)
    """
    return len(str(text)) // 4


def compress_message_if_needed(
    message: Any, max_tokens: int = 2000, compression_cache: dict | None = None
) -> str:
    """Compress a message if it exceeds token budget.

    Caches compressed summaries to avoid re-compression.

    Args:
        message: Message to compress (LangChain message object or string)
        max_tokens: Maximum tokens for this message
        compression_cache: Optional cache dict to store summaries

    Returns:
        Message content (compressed if needed)
    """
    # Extract content from message
    if hasattr(message, "content"):
        content = message.content
        msg_type = getattr(message, "type", "unknown")
    else:
        content = str(message)
        msg_type = "string"

    # Estimate current size
    estimated_tokens = estimate_tokens(content)

    # If under budget, return as-is
    if estimated_tokens <= max_tokens:
        return content

    # Check cache first
    if compression_cache is not None:
        cache_key = f"{msg_type}:{hash(str(content)[:1000])}"
        if cache_key in compression_cache:
            logger.debug(f"Using cached compression for {msg_type} message")
            return compression_cache[cache_key]

    # Compress by truncating intelligently
    # For ToolMessages: Keep first and last portions (usually have results)
    # For AIMessages: Keep reasoning summary
    if msg_type == "tool":
        # Keep beginning (context) and end (results)
        max_chars = max_tokens * 4
        quarter = max_chars // 4
        compressed = (
            content[: quarter * 2]
            + f"\n\n... [compressed {estimated_tokens - max_tokens} tokens] ...\n\n"
            + content[-quarter:]
        )
    else:
        # Simple truncation for other message types
        max_chars = max_tokens * 4
        compressed = (
            content[:max_chars]
            + f"\n\n... [compressed {estimated_tokens - max_tokens} tokens] ..."
        )

    # Cache result
    if compression_cache is not None:
        cache_key = f"{msg_type}:{hash(str(content)[:1000])}"
        compression_cache[cache_key] = compressed

    logger.info(
        f"Compressed {msg_type} message: {estimated_tokens} → {estimate_tokens(compressed)} tokens"
    )
    return compressed


def select_messages_within_budget(
    messages: list,
    max_tokens: int = 80000,
    compression_cache: dict | None = None,
) -> str:
    """Select and compress messages to fit within token budget.

    Args:
        messages: List of messages to process
        max_tokens: Maximum total tokens allowed
        compression_cache: Optional cache for compressed messages

    Returns:
        Formatted string of selected messages within budget
    """
    # Start from most recent messages (they're usually most relevant)
    selected = []
    total_tokens = 0
    tokens_per_message_budget = max_tokens // 40  # ~2000 tokens per message budget

    for msg in reversed(messages[-40:]):  # Start with last 40
        # Compress message if needed
        compressed_content = compress_message_if_needed(
            msg,
            max_tokens=tokens_per_message_budget,
            compression_cache=compression_cache,
        )

        msg_tokens = estimate_tokens(compressed_content)

        # Check if adding this message exceeds budget
        if total_tokens + msg_tokens > max_tokens:
            logger.info(
                f"Reached token budget at {total_tokens} tokens with {len(selected)} messages"
            )
            break

        selected.append(compressed_content)
        total_tokens += msg_tokens

    # Reverse back to chronological order
    selected.reverse()

    logger.info(
        f"Selected {len(selected)} messages totaling ~{total_tokens} tokens (budget: {max_tokens})"
    )

    return "\n\n".join(selected)
