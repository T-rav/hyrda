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

    Returns:
        InternalSearchTool singleton instance or None if not available
    """
    return _InternalSearchToolSingleton.get_instance()


async def search_tool(
    config: RunnableConfig, phase: str = "initial", perplexity_enabled: bool = False
) -> list[Any]:
    """Get appropriate search tool based on configuration and research phase.

    Args:
        config: RunnableConfig with configuration settings
        phase: Research phase - "initial" (cheap tools only) or "deep" (all tools)
        perplexity_enabled: Whether deep_research is enabled (from SEARCH_PERPLEXITY_ENABLED)

    Returns:
        List of search tools appropriate for the research phase
    """
    from services.search_clients import get_tavily_client, get_tool_definitions

    tavily_client = get_tavily_client()

    if not tavily_client:
        logger.warning("No search client available for profile research")
        return []

    # Determine if we should include deep_research based on phase and settings
    include_deep_research = False
    if phase == "deep" and perplexity_enabled:
        # Phase 2 + Perplexity enabled: Include deep_research
        include_deep_research = True
        logger.info(
            "Phase 2 (deep): Using all tools including deep_research (Tavily + Perplexity)"
        )
    else:
        # Phase 1 or Perplexity disabled: Only Tavily tools
        logger.info(
            "Phase 1 (initial): Using exploration tools only (web_search, scrape_url)"
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


def format_research_context(
    research_brief: str, notes: list[str], profile_type: str
) -> str:
    """Format research context for final report generation.

    Extracts all sources from individual research notes and creates a consolidated
    global source list, renumbering citations throughout.

    Args:
        research_brief: Original research plan
        notes: List of compressed research findings
        profile_type: Type of profile (company, employee, project)

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
