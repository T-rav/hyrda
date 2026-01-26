"""Distributed tracing utilities for LangGraph agent nodes.

Provides helpers for linking agent node observations to parent traces
for full distributed tracing waterfall in Langfuse.
"""

import functools
import logging
from typing import Callable

from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)


def get_trace_context_from_config(config: RunnableConfig) -> dict[str, str] | None:
    """Extract trace context from LangGraph config.

    Args:
        config: LangGraph RunnableConfig passed to nodes

    Returns:
        Trace context dict with trace_id and parent_span_id, or None
    """
    if not config:
        return None

    # Check if trace_context was passed in the config
    # It would be in the top-level config dict or in configurable
    trace_context = None

    # Try direct access first
    if isinstance(config, dict):
        trace_context = config.get("trace_context")

        # Try configurable section
        if not trace_context:
            configurable = config.get("configurable", {})
            if isinstance(configurable, dict):
                trace_context = configurable.get("trace_context")

    return trace_context


def trace_agent_node(node_name: str):
    """Decorator to automatically trace agent nodes with distributed tracing.

    Links node observations to parent trace for full waterfall view.

    Args:
        node_name: Name of the node for tracing (e.g., "supervisor", "researcher")

    Example:
        @trace_agent_node("supervisor")
        async def supervisor_node(state: AgentState, config: RunnableConfig):
            # Node logic here
            return {"key": "value"}
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract config from args/kwargs
            config = None
            if len(args) > 1 and isinstance(args[1], dict):
                config = args[1]
            elif "config" in kwargs:
                config = kwargs["config"]

            # Try to get trace context
            trace_context = get_trace_context_from_config(config)

            if trace_context:
                # Import here to avoid circular imports
                from services.langfuse_service import get_langfuse_service

                langfuse_service = get_langfuse_service()

                if langfuse_service and langfuse_service.enabled and langfuse_service.client:
                    try:
                        # Create a span linked to parent trace
                        span = langfuse_service.client.span(
                            trace_id=trace_context.get("trace_id"),
                            parent_observation_id=trace_context.get("parent_span_id"),
                            name=node_name,
                            input={"node": node_name},
                            metadata={"agent_node": node_name},
                        )

                        # Execute the node
                        result = await func(*args, **kwargs)

                        # End the span with output
                        span.end(output=result)

                        return result
                    except Exception as e:
                        logger.warning(f"Failed to trace node {node_name}: {e}")
                        # Still execute the function even if tracing fails
                        return await func(*args, **kwargs)
                else:
                    # No Langfuse service, just execute normally
                    return await func(*args, **kwargs)
            else:
                # No trace context, just execute normally
                return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Extract config from args/kwargs
            config = None
            if len(args) > 1 and isinstance(args[1], dict):
                config = args[1]
            elif "config" in kwargs:
                config = kwargs["config"]

            # Try to get trace context
            trace_context = get_trace_context_from_config(config)

            if trace_context:
                # Import here to avoid circular imports
                from services.langfuse_service import get_langfuse_service

                langfuse_service = get_langfuse_service()

                if langfuse_service and langfuse_service.enabled and langfuse_service.client:
                    try:
                        # Create a span linked to parent trace
                        span = langfuse_service.client.span(
                            trace_id=trace_context.get("trace_id"),
                            parent_observation_id=trace_context.get("parent_span_id"),
                            name=node_name,
                            input={"node": node_name},
                            metadata={"agent_node": node_name},
                        )

                        # Execute the node
                        result = func(*args, **kwargs)

                        # End the span with output
                        span.end(output=result)

                        return result
                    except Exception as e:
                        logger.warning(f"Failed to trace node {node_name}: {e}")
                        # Still execute the function even if tracing fails
                        return func(*args, **kwargs)
                else:
                    # No Langfuse service, just execute normally
                    return func(*args, **kwargs)
            else:
                # No trace context, just execute normally
                return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
