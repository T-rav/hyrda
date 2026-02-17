"""aiohttp middleware for distributed tracing with correlation IDs.

Similar to the FastAPI TracingMiddleware but for aiohttp applications.

Automatically:
1. Extracts trace ID from incoming X-Trace-Id header
2. Generates new trace ID if not present
3. Sets trace ID in request context
4. Adds trace ID to response headers
5. Logs request start/end with trace ID
"""

import logging
import time
from collections.abc import Awaitable, Callable

from aiohttp import web

# Import from parent to avoid circular imports
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.utils.tracing import (
    TraceContext,
    extract_trace_id_from_headers,
    format_trace_summary,
)

logger = logging.getLogger(__name__)


def create_tracing_middleware(
    service_name: str,
) -> Callable[[web.Request, Callable], Awaitable[web.StreamResponse]]:
    """Create aiohttp tracing middleware.

    Args:
        service_name: Name of this service (e.g., "bot", "dashboard-service")

    Returns:
        aiohttp middleware handler

    Example:
        app = web.Application(middlewares=[create_tracing_middleware("bot")])
    """

    @web.middleware
    async def tracing_middleware(
        request: web.Request,
        handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
    ) -> web.StreamResponse:
        """Process request with tracing."""
        start_time = time.time()

        # Extract trace ID from headers (for incoming requests from other services)
        headers_dict = {k: v for k, v in request.headers.items()}
        trace_id = extract_trace_id_from_headers(headers_dict)

        # Use TraceContext to set trace ID for this request
        with TraceContext(trace_id) as trace_id:
            # Get client IP safely
            client_ip = "unknown"
            if request.remote:
                client_ip = request.remote

            # Log request start
            logger.info(
                format_trace_summary(
                    service_name,
                    f"{request.method} {request.path}",
                    status="started",
                ),
                extra={
                    "trace_id": trace_id,
                    "method": request.method,
                    "path": request.path,
                    "client_ip": client_ip,
                },
            )

            # Process request
            try:
                response = await handler(request)

                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Log request completion
                status = "success" if response.status < 400 else "error"
                logger.info(
                    format_trace_summary(
                        service_name,
                        f"{request.method} {request.path}",
                        duration_ms,
                        status,
                    ),
                    extra={
                        "trace_id": trace_id,
                        "method": request.method,
                        "path": request.path,
                        "status_code": response.status,
                        "duration_ms": duration_ms,
                    },
                )

                # Add trace ID to response headers
                response.headers["X-Trace-Id"] = trace_id

                return response

            except web.HTTPException as e:
                # HTTP exceptions (4xx, 5xx) - log and re-raise
                duration_ms = (time.time() - start_time) * 1000
                logger.warning(
                    format_trace_summary(
                        service_name,
                        f"{request.method} {request.path}",
                        duration_ms,
                        "http_error",
                    ),
                    extra={
                        "trace_id": trace_id,
                        "method": request.method,
                        "path": request.path,
                        "status_code": e.status,
                        "duration_ms": duration_ms,
                    },
                )
                raise

            except Exception as e:
                # Unexpected errors
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    format_trace_summary(
                        service_name,
                        f"{request.method} {request.path}",
                        duration_ms,
                        "error",
                    ),
                    extra={
                        "trace_id": trace_id,
                        "method": request.method,
                        "path": request.path,
                        "error": str(e),
                        "duration_ms": duration_ms,
                    },
                    exc_info=True,
                )
                raise

    return tracing_middleware
