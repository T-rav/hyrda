"""Utilities for company profile deep research workflow.

Helper functions for tool integration, token management, and model configuration.
"""

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from agents.company_profile.configuration import ProfileConfiguration, SearchAPI

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


async def get_search_tool(
    config: RunnableConfig, webcat_client: Any = None
) -> list[Any]:
    """Get appropriate search tool based on configuration.

    Args:
        config: RunnableConfig with configuration settings
        webcat_client: Optional WebCatClient instance for web search

    Returns:
        List of search tools
    """
    configuration = ProfileConfiguration.from_runnable_config(config)
    search_api = configuration.search_api

    if search_api == SearchAPI.WEBCAT and webcat_client:
        # Use our integrated WebCat MCP server
        logger.info("Using WebCat search for profile research")
        return webcat_client.get_tool_definitions()

    elif search_api == SearchAPI.TAVILY:
        # Use Tavily if available
        try:
            from langchain_community.tools.tavily_search import TavilySearchResults

            logger.info("Using Tavily search for profile research")
            return [TavilySearchResults(max_results=5)]
        except ImportError:
            logger.warning("Tavily not available, falling back to no search")
            return []

    else:
        logger.warning("No search API configured for profile research")
        return []


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

    Args:
        research_brief: Original research plan
        notes: List of compressed research findings
        profile_type: Type of profile (company, employee, project)

    Returns:
        Formatted context string
    """
    context = "# Profile Research Context\n\n"
    context += f"**Profile Type**: {profile_type}\n\n"
    context += f"**Research Brief**:\n{research_brief}\n\n"
    context += f"**Research Findings** ({len(notes)} sections):\n\n"

    for i, note in enumerate(notes, 1):
        context += f"## Finding {i}\n\n{note}\n\n"

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
