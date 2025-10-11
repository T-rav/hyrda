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
from services.langfuse_service import get_langfuse_service

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

    # Start Langfuse span for compression
    langfuse_service = get_langfuse_service()
    span = None
    if langfuse_service and langfuse_service.client:
        span = langfuse_service.client.start_span(
            name="deep_research_compress_research",
            input={
                "research_topic": research_topic,
                "message_count": len(messages),
                "raw_notes_count": len(raw_notes),
            },
            metadata={
                "node_type": "compression",
                "max_tokens": configuration.compression_model_max_tokens,
            },
        )

    # Use LangChain ChatOpenAI directly
    from langchain_openai import ChatOpenAI

    from config.settings import Settings

    settings = Settings()
    llm = ChatOpenAI(
        model=settings.llm.model,
        api_key=settings.llm.api_key,
        temperature=0.7,
        max_tokens=configuration.compression_model_max_tokens,
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
            # Trace LLM generation
            generation = None
            if langfuse_service and langfuse_service.client:
                generation = langfuse_service.client.start_generation(
                    name="compression_llm_call",
                    input={
                        "compression_messages": compression_messages,
                        "attempt": attempt + 1,
                    },
                    metadata={
                        "research_topic": research_topic,
                        "max_tokens": configuration.compression_model_max_tokens,
                    },
                )

            # Use LangChain ChatOpenAI
            response = await llm.ainvoke(compression_messages)
            compressed = (
                response.content if hasattr(response, "content") else str(response)
            )
            logger.info(f"Research compressed to {len(compressed)} characters")

            # End generation trace
            if generation:
                generation.end(
                    output={
                        "compressed_length": len(compressed),
                        "compression_ratio": len(compressed)
                        / max(len("\n\n".join([str(msg) for msg in messages[-5:]])), 1),
                    }
                )

            # End span
            if span:
                span.end(
                    output={
                        "compressed_length": len(compressed),
                        "raw_notes_count": len(raw_notes),
                        "success": True,
                    }
                )

            return {"compressed_research": compressed, "raw_notes": raw_notes}

        except Exception as e:
            if is_token_limit_exceeded(e, configuration.compression_model):
                logger.warning(f"Token limit on compression attempt {attempt + 1}")
                compression_messages = remove_up_to_last_ai_message(
                    compression_messages
                )
                continue

            logger.error(f"Compression error: {e}")
            if generation:
                generation.end(level="ERROR", status_message=str(e))
            if span:
                span.end(level="ERROR", status_message=str(e))
            break

    # Fallback: return raw notes
    if span:
        span.end(
            output={
                "fallback": True,
                "raw_notes_count": len(raw_notes),
                "success": False,
            }
        )

    return {
        "compressed_research": "Compression failed. Raw notes: "
        + "\n".join(raw_notes[:3]),
        "raw_notes": raw_notes,
    }
