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


async def search_tool(
    config: RunnableConfig, phase: str = "initial", perplexity_enabled: bool = False
) -> list[Any]:
    """Get appropriate search tools based on configuration.

    Args:
        config: RunnableConfig with configuration settings
        phase: "initial" (web_search/scrape_url only) or "deep" (includes deep_research)
        perplexity_enabled: Whether deep_research is enabled (from SEARCH_PERPLEXITY_ENABLED)

    Returns:
        List of search tools (always includes web_search/scrape_url, adds deep_research if phase="deep")
    """
    from services.search_clients import get_tavily_client, get_tool_definitions

    tavily_client = get_tavily_client()

    if not tavily_client:
        logger.warning("No search client available for profile research")
        return []

    # Determine if we should include deep_research based on phase and settings
    include_deep_research = False
    if phase == "deep" and perplexity_enabled:
        # Deep research enabled: Include all tools including Perplexity
        include_deep_research = True
        logger.info(
            "Research tools: Using full toolkit (web_search, scrape_url, deep_research)"
        )
    else:
        # Deep research not available: Only Tavily tools
        logger.info(
            "Research tools: Using exploration tools only (web_search, scrape_url)"
        )

    # Get tool definitions
    tools = get_tool_definitions(include_deep_research=include_deep_research)
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
        min_deep_research = min(5, len(deep_research_indices))
        min_internal = min(3, len(internal_search_indices))

        selection_prompt = f"""You are selecting the top {max_sources} most relevant and important sources from a list of {len(global_sources)} sources for a company profile report.

**All Available Sources:**
{sources_text}

**Selection Criteria (IN ORDER OF PRIORITY):**
1. **CRITICAL**: Include AT LEAST {min_deep_research} sources marked [DEEP_RESEARCH] - comprehensive Perplexity AI analyses (expensive, high-value)
2. **CRITICAL**: Include AT LEAST {min_internal} sources marked [INTERNAL_KB] - internal knowledge base data (proprietary information)
3. Prioritize authoritative sources (official company sites, SEC filings, reputable news)
4. Include diverse source types (company site, news, financial data, industry analysis)
5. Prefer sources with detailed descriptions (indicates rich content)
6. Balance recency with authority
7. Avoid duplicate or redundant sources

**Your Task:**
Return a JSON array of the source numbers (1-{len(global_sources)}) you want to keep, in order of importance.
You MUST select exactly {max_sources} sources.
You MUST include at least {min_deep_research} [DEEP_RESEARCH] and {min_internal} [INTERNAL_KB] sources (premium research).

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

    return context


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
    """Extract specific focus area or intent from user query.

    Identifies if user is asking about a specific aspect like "AI needs",
    "hiring challenges", "cloud strategy", etc.

    Args:
        query: User query
        llm_service: Optional LLM service for extraction (if not provided, uses patterns)

    Returns:
        Focus area description or empty string if general profile requested

    Examples:
        "profile tesla" -> ""
        "profile tesla's ai needs" -> "AI needs and capabilities"
        "tell me about acme's hiring challenges" -> "hiring challenges and talent acquisition"
        "what are stripe's product strategy" -> "product strategy and roadmap"
    """
    import re

    query_lower = query.lower()

    # Pattern-based extraction for common focus areas
    focus_patterns = {
        r"ai\s+(?:needs|capabilities|strategy|initiatives|plans)": "AI needs and capabilities",
        r"hiring|talent|recruiting|recruitment": "hiring challenges and talent acquisition",
        r"product\s+(?:strategy|roadmap|initiatives|plans)": "product strategy and roadmap",
        r"engineering\s+(?:challenges|needs|team|practices)": "engineering challenges and team structure",
        r"cloud\s+(?:strategy|infrastructure|migration)": "cloud strategy and infrastructure",
        r"sales|revenue|go-to-market|gtm": "sales strategy and revenue generation",
        r"marketing\s+(?:strategy|initiatives|campaigns)": "marketing strategy and initiatives",
        r"technical\s+debt": "technical debt and code quality",
        r"security|compliance|privacy": "security and compliance posture",
        r"data\s+(?:strategy|infrastructure|analytics)": "data strategy and analytics capabilities",
        r"mobile\s+(?:strategy|apps|development)": "mobile strategy and applications",
        r"customer\s+(?:success|support|experience)": "customer success and support operations",
    }

    # Check each pattern
    for pattern, focus_description in focus_patterns.items():
        if re.search(pattern, query_lower):
            logger.info(f"Extracted focus area from query: '{focus_description}'")
            return focus_description

    # If llm_service is provided, use it for more nuanced extraction
    if llm_service:
        try:
            import json

            from langchain_openai import ChatOpenAI

            from config.settings import Settings

            settings = Settings()

            extraction_prompt = f"""Analyze this user query and extract the specific focus area or aspect they're interested in.

Query: "{query}"

If the user is asking about a SPECIFIC aspect (like AI needs, hiring challenges, product strategy, etc.),
extract and return that focus area. If they're asking for a general profile with no specific focus, return an empty string.

Examples:
- "profile tesla" → ""
- "profile tesla's ai needs" → "AI needs and capabilities"
- "tell me about stripe's payment infrastructure" → "payment infrastructure and processing capabilities"
- "what are snowflake's data governance practices" → "data governance and compliance practices"
- "acme corp hiring challenges" → "hiring challenges and talent acquisition"

Return ONLY a JSON object: {{"focus_area": "extracted focus or empty string"}}"""

            llm = ChatOpenAI(
                model="gpt-4o-mini",
                api_key=settings.llm.api_key,
                temperature=0.0,
                max_completion_tokens=50,
            )

            response = await llm.ainvoke(extraction_prompt)
            result_text = response.content.strip()

            # Parse JSON response
            result_data = json.loads(result_text)
            focus_area = result_data.get("focus_area", "").strip()

            if focus_area:
                logger.info(f"LLM extracted focus area: '{focus_area}'")
            else:
                logger.info("LLM determined no specific focus area (general profile)")

            return focus_area

        except Exception as e:
            logger.warning(
                f"Error using LLM for focus extraction, falling back to pattern matching: {e}"
            )

    # No specific focus detected
    logger.info("No specific focus area detected - general profile request")
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
