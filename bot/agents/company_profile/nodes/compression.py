"""Research compression node for deep research workflow.

Compresses and synthesizes research findings into concise summaries.
Includes Langfuse tracing for observability.
"""

import logging

from langchain_core.runnables import RunnableConfig

from agents.company_profile import prompts
from agents.company_profile.configuration import ProfileConfiguration
from agents.company_profile.state import ResearcherState
from agents.company_profile.utils import (
    create_human_message,
    create_system_message,
    is_token_limit_exceeded,
    remove_up_to_last_ai_message,
    select_messages_within_budget,
)

logger = logging.getLogger(__name__)


async def compress_research(state: ResearcherState, config: RunnableConfig) -> dict:
    """Compress and synthesize research findings.

    Args:
        state: Current researcher state
        config: Runtime configuration

    Returns:
        Dict with compressed_research and raw_notes
    """
    configuration = ProfileConfiguration.from_runnable_config(config)
    research_topic = state["research_topic"]
    messages = state["researcher_messages"]
    raw_notes = state.get("raw_notes", [])

    logger.info(f"Compressing research for: {research_topic[:50]}...")

    # Use LangChain ChatOpenAI directly
    from langchain_openai import ChatOpenAI

    from config.settings import Settings

    settings = Settings()
    llm = ChatOpenAI(
        model=settings.llm.model,
        api_key=settings.llm.api_key,
        temperature=0.7,
        max_completion_tokens=configuration.compression_model_max_tokens,
    )

    # Build compression prompt
    system_prompt = prompts.compress_research_system_prompt.format(
        research_topic=research_topic
    )

    # Create compression messages with smart token management
    # Budget: 128K context - 16K output - 2K system prompt = ~110K available
    # Use 90K for better coverage (still 20K buffer for encoding overhead)
    compression_cache = {}  # Cache compressed messages across retries
    selected_content = select_messages_within_budget(
        messages, max_tokens=90000, compression_cache=compression_cache
    )

    compression_messages = [
        create_system_message(system_prompt),
        create_human_message(selected_content),
    ]

    # Try compression with retry on token limits
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # Use LangChain ChatOpenAI
            response = await llm.ainvoke(compression_messages)
            compressed = (
                response.content if hasattr(response, "content") else str(response)
            )
            logger.info(f"Research compressed to {len(compressed)} characters")

            return {"compressed_research": compressed, "raw_notes": raw_notes}

        except Exception as e:
            if is_token_limit_exceeded(e, configuration.compression_model):
                logger.warning(f"Token limit on compression attempt {attempt + 1}")
                compression_messages = remove_up_to_last_ai_message(
                    compression_messages
                )
                continue

            logger.error(f"Compression error: {e}")
            break

    # Fallback: return raw notes
    return {
        "compressed_research": "Compression failed. Raw notes: "
        + "\n".join(raw_notes[:3]),
        "raw_notes": raw_notes,
    }
