"""FastAPI middleware for distributed tracing with correlation IDs.

Automatically:
1. Extracts trace ID from incoming X-Trace-Id header
2. Generates new trace ID if not present
3. Sets trace ID in request context
4. Adds trace ID to response headers
5. Logs request start/end with trace ID

This enables end-to-end request tracing across all services.
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

# Import tracing utilities
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.utils.tracing import (
    TraceContext,
    extract_trace_id_from_headers,
    format_trace_summary,
)

logger = logging.getLogger(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """Middleware for distributed tracing with correlation IDs.

    Adds X-Trace-Id header to all requests and responses.
    Logs all requests with trace information.
    """

    def __init__(self, app: ASGIApp, service_name: str):
        """Initialize tracing middleware.

        Args:
            app: ASGI application
            service_name: Name of this service (e.g., "bot", "agent-service")
        """
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next):
        """Process request with tracing."""
        start_time = time.time()

        # Extract trace ID from headers (for incoming requests from other services)
        trace_id = extract_trace_id_from_headers(dict(request.headers))

        # Use TraceContext to set trace ID for this request
        with TraceContext(trace_id) as trace_id:
            # Log request start
            logger.info(
                format_trace_summary(
                    self.service_name,
                    f"{request.method} {request.url.path}",
                    status="started",
                ),
                extra={
                    "trace_id": trace_id,
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": request.client.host if request.client else "unknown",
                },
            )

            # Process request
            try:
                response = await call_next(request)

                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Log request completion
                status = "success" if response.status_code < 400 else "error"
                logger.info(
                    format_trace_summary(
                        self.service_name,
                        f"{request.method} {request.url.path}",
                        duration_ms,
                        status,
                    ),
                    extra={
                        "trace_id": trace_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                    },
                )

                # Add trace ID to response headers
                response.headers["X-Trace-Id"] = trace_id

                return response

            except Exception as e:
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Log error
                logger.error(
                    format_trace_summary(
                        self.service_name,
                        f"{request.method} {request.url.path}",
                        duration_ms,
                        "error",
                    ),
                    extra={
                        "trace_id": trace_id,
                        "method": request.method,
                        "path": request.url.path,
                        "error": str(e),
                        "duration_ms": duration_ms,
                    },
                    exc_info=True,
                )

                # Re-raise to let FastAPI handle the error
                raise
