"""Trace context propagation across HTTP service boundaries.

This module provides utilities for propagating Langfuse trace context
across microservice HTTP boundaries to maintain unified waterfall traces.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# HTTP header names for trace context propagation
TRACE_ID_HEADER = "X-Langfuse-Trace-ID"
PARENT_SPAN_ID_HEADER = "X-Langfuse-Parent-Span-ID"


def create_trace_headers(trace_context: dict[str, str] | None) -> dict[str, str]:
    """
    Create HTTP headers from trace context for cross-service propagation.

    Args:
        trace_context: Trace context with trace_id (32 hex) and parent_span_id (16 hex)

    Returns:
        Dictionary of HTTP headers to include in requests

    Example:
        context = langfuse_service.get_current_trace_context()
        headers = create_trace_headers(context)
        response = await client.post("/api/endpoint", headers=headers)
    """
    headers = {}

    if trace_context:
        if "trace_id" in trace_context:
            headers[TRACE_ID_HEADER] = trace_context["trace_id"]
            logger.debug(f"Added trace_id to headers: {trace_context['trace_id']}")

        if "parent_span_id" in trace_context:
            headers[PARENT_SPAN_ID_HEADER] = trace_context["parent_span_id"]
            logger.debug(
                f"Added parent_span_id to headers: {trace_context['parent_span_id']}"
            )

    return headers


def extract_trace_context(
    headers: dict[str, Any] | None,
) -> dict[str, str] | None:
    """
    Extract trace context from incoming HTTP headers.

    Args:
        headers: HTTP request headers (case-insensitive)

    Returns:
        Trace context dictionary or None if no trace headers present

    Example:
        # In FastAPI endpoint
        @app.post("/api/endpoint")
        async def endpoint(request: Request):
            trace_context = extract_trace_context(dict(request.headers))
            # Use trace_context for linking observations
    """
    if not headers:
        return None

    # Normalize headers to lowercase for case-insensitive lookup
    normalized_headers = {k.lower(): v for k, v in headers.items()}

    trace_id = normalized_headers.get(TRACE_ID_HEADER.lower())
    parent_span_id = normalized_headers.get(PARENT_SPAN_ID_HEADER.lower())

    if trace_id:
        context = {"trace_id": trace_id}

        if parent_span_id:
            context["parent_span_id"] = parent_span_id

        logger.debug(f"Extracted trace context from headers: {context}")
        return context

    return None


def merge_trace_contexts(
    current_context: dict[str, str] | None,
    incoming_context: dict[str, str] | None,
) -> dict[str, str] | None:
    """
    Merge current and incoming trace contexts, preferring incoming.

    This is useful when receiving a request with trace context while
    also being in a decorator context. The incoming context takes precedence.

    Args:
        current_context: Current trace context (e.g., from @observe decorator)
        incoming_context: Incoming trace context (e.g., from HTTP headers)

    Returns:
        Merged trace context, preferring incoming over current

    Example:
        current = LangfuseService.get_current_trace_context()
        incoming = extract_trace_context(request.headers)
        context = merge_trace_contexts(current, incoming)
    """
    if incoming_context:
        return incoming_context

    return current_context


def add_trace_headers_to_request(
    headers: dict[str, str] | None,
    trace_context: dict[str, str] | None,
) -> dict[str, str]:
    """
    Add trace context headers to existing request headers.

    Args:
        headers: Existing request headers (will be copied, not modified)
        trace_context: Trace context to add

    Returns:
        New headers dictionary with trace headers added

    Example:
        headers = {"Content-Type": "application/json"}
        context = langfuse_service.get_current_trace_context()
        headers_with_trace = add_trace_headers_to_request(headers, context)
        response = await client.post(url, headers=headers_with_trace, json=data)
    """
    # Copy existing headers
    result_headers = dict(headers) if headers else {}

    # Add trace headers
    trace_headers = create_trace_headers(trace_context)
    result_headers.update(trace_headers)

    return result_headers
