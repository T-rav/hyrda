"""Integration between Langfuse and distributed tracing.

Links Langfuse LLM observations with request trace IDs for complete
end-to-end observability from Slack message → LLM calls.

This allows you to:
- Find which user request triggered a specific LLM call
- See all LLM calls for a given trace_id
- Correlate LLM costs/latency with user requests
- Debug LLM behavior in context of the full request flow
"""

import logging
from typing import Any

from shared.utils.tracing import get_trace_id, get_parent_trace_id

logger = logging.getLogger(__name__)

# Check if Langfuse is available
try:
    from langfuse.decorators import langfuse_context

    LANGFUSE_AVAILABLE = True
except ImportError:
    logger.warning("Langfuse not available - trace linking disabled")
    LANGFUSE_AVAILABLE = False


def add_trace_to_langfuse_context() -> None:
    """Add current trace ID to Langfuse context as metadata.

    Call this at the start of any function decorated with @observe
    to link the Langfuse observation with the distributed trace.

    Example:
        @observe(name="llm_call")
        async def call_llm(query: str):
            add_trace_to_langfuse_context()  # Link trace
            response = await llm.generate(query)
            return response
    """
    if not LANGFUSE_AVAILABLE:
        return

    trace_id = get_trace_id()
    parent_trace_id = get_parent_trace_id()

    if trace_id:
        # Add as session ID (shows up in Langfuse UI)
        langfuse_context.update_current_observation(session_id=trace_id)

        # Add as metadata for querying
        metadata = {"trace_id": trace_id}
        if parent_trace_id:
            metadata["parent_trace_id"] = parent_trace_id

        langfuse_context.update_current_observation(metadata=metadata)

        logger.debug(f"Linked Langfuse observation to trace_id: {trace_id}")


def add_trace_to_langfuse_trace(trace_name: str | None = None) -> None:
    """Add trace ID to the top-level Langfuse trace.

    Use this for trace-level metadata (at the start of a request).

    Args:
        trace_name: Optional name for the Langfuse trace

    Example:
        @observe(name="handle_slack_message")
        async def handle_message(text: str, user_id: str):
            add_trace_to_langfuse_trace("slack_message")
            # ... process message
    """
    if not LANGFUSE_AVAILABLE:
        return

    trace_id = get_trace_id()
    if not trace_id:
        return

    try:
        # Update the current trace with trace_id
        langfuse_context.update_current_trace(
            session_id=trace_id, metadata={"trace_id": trace_id}
        )

        if trace_name:
            langfuse_context.update_current_trace(name=trace_name)

        logger.debug(f"Linked Langfuse trace to trace_id: {trace_id}")

    except Exception as e:
        logger.warning(f"Failed to link Langfuse trace: {e}")


def get_langfuse_trace_url() -> str | None:
    """Get the Langfuse trace URL for the current observation.

    Returns:
        Langfuse trace URL or None if not available

    Example:
        url = get_langfuse_trace_url()
        if url:
            logger.info(f"View in Langfuse: {url}")
    """
    if not LANGFUSE_AVAILABLE:
        return None

    try:
        trace_id = langfuse_context.get_current_trace_id()
        if trace_id:
            # Langfuse cloud URL format
            host = "https://us.cloud.langfuse.com"  # TODO: Get from env
            return f"{host}/trace/{trace_id}"
    except Exception as e:
        logger.debug(f"Could not get Langfuse trace URL: {e}")

    return None


def format_trace_summary_with_langfuse(
    service: str, action: str, duration_ms: float | None = None
) -> str:
    """Format trace summary with Langfuse link.

    Args:
        service: Service name
        action: Action performed
        duration_ms: Duration in milliseconds

    Returns:
        Formatted string with Langfuse link

    Example:
        >>> summary = format_trace_summary_with_langfuse("bot", "llm_call", 150.5)
        >>> print(summary)
        [bot] llm_call | 150.5ms | Langfuse: https://...
    """
    from shared.utils.tracing import format_trace_summary

    summary = format_trace_summary(service, action, duration_ms)

    langfuse_url = get_langfuse_trace_url()
    if langfuse_url:
        summary += f" | Langfuse: {langfuse_url}"

    return summary
