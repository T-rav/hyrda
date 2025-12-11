"""HTTP client for calling agent-service."""

import asyncio
import json
import logging
import os
import sys
import time
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

from bot_types import AgentContext, AgentInfo, AgentResponse, CircuitBreakerStatus

# Import request signing and tracing utilities from shared directory
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # Add project root to path
from shared.utils.otel_http_client import (
    SPAN_KIND_CLIENT,
    add_otel_headers,
    create_span,
    record_exception,
)
from shared.utils.request_signing import add_signature_headers
from shared.utils.tracing import add_trace_id_to_headers, get_or_create_trace_id

logger = logging.getLogger(__name__)

# Circuit breaker configuration constants
DEFAULT_FAILURE_THRESHOLD = 5  # Open circuit after this many failures
DEFAULT_RECOVERY_TIMEOUT = 60.0  # Wait this many seconds before retry
DEFAULT_SUCCESS_THRESHOLD = 2  # Successes needed to close circuit

# HTTP client configuration constants
DEFAULT_REQUEST_TIMEOUT = 30.0  # Total request timeout in seconds
DEFAULT_CONNECT_TIMEOUT = 5.0  # Connection timeout in seconds
DEFAULT_MAX_RETRIES = 3  # Maximum retry attempts
DEFAULT_RETRY_DELAY = 1.0  # Initial retry delay in seconds


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests immediately
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Simple circuit breaker to prevent cascading failures.

    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests fail immediately
    - HALF_OPEN: Testing recovery, allow limited requests

    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before trying half-open
        success_threshold: Successes needed in half-open to close circuit
    """

    def __init__(
        self,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        recovery_timeout: float = DEFAULT_RECOVERY_TIMEOUT,
        success_threshold: int = DEFAULT_SUCCESS_THRESHOLD,
    ):
        """Initialize circuit breaker."""
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float | None = None

    def call(self, func: Callable):
        """Decorator to wrap function with circuit breaker."""

        async def wrapper(*args, **kwargs):
            """Wrapper."""
            # Check if circuit is open
            if self.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if (
                    self.last_failure_time
                    and time.time() - self.last_failure_time >= self.recovery_timeout
                ):
                    logger.info("Circuit breaker: Entering HALF_OPEN state")
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    raise CircuitBreakerError(
                        f"Circuit breaker OPEN - agent service unavailable (failing fast). "
                        f"Will retry in {self.recovery_timeout}s"
                    )

            try:
                # Call the actual function
                result = await func(*args, **kwargs)

                # Success! Update state
                if self.state == CircuitState.HALF_OPEN:
                    self.success_count += 1
                    logger.info(
                        f"Circuit breaker: Success in HALF_OPEN ({self.success_count}/{self.success_threshold})"
                    )
                    if self.success_count >= self.success_threshold:
                        logger.info(
                            "Circuit breaker: Closing circuit (service recovered)"
                        )
                        self.state = CircuitState.CLOSED
                        self.failure_count = 0
                elif self.state == CircuitState.CLOSED:
                    # Reset failure count on success
                    self.failure_count = 0

                return result

            except (httpx.TimeoutException, httpx.ConnectError, AgentClientError):
                # Failure! Update state
                self.failure_count += 1
                self.last_failure_time = time.time()

                if self.state == CircuitState.HALF_OPEN:
                    # Failed in half-open, go back to open
                    logger.warning(
                        "Circuit breaker: Failed in HALF_OPEN, reopening circuit"
                    )
                    self.state = CircuitState.OPEN
                    self.success_count = 0
                elif self.state == CircuitState.CLOSED:
                    if self.failure_count >= self.failure_threshold:
                        logger.error(
                            f"Circuit breaker: Opening circuit after {self.failure_count} failures"
                        )
                        self.state = CircuitState.OPEN

                # Re-raise the original exception
                raise

        return wrapper


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    pass


class AgentClient:
    """Client for calling agent-service HTTP API with retry logic."""

    def __init__(self, base_url: str = "http://agent_service:8000"):
        """Initialize agent client.

        Args:
            base_url: Base URL of agent-service (defaults to Docker service name)
        """
        self.base_url = base_url.rstrip("/")
        # Reduced timeout from 5min to 30s to fail fast
        self.timeout = httpx.Timeout(
            DEFAULT_REQUEST_TIMEOUT, connect=DEFAULT_CONNECT_TIMEOUT
        )
        # Persistent HTTP client to reuse connections (fixes resource leak)
        self._client: httpx.AsyncClient | None = None
        self.max_retries = DEFAULT_MAX_RETRIES
        self.retry_delay = DEFAULT_RETRY_DELAY  # Start with 1 second

        # Service authentication token for agent-service
        self.service_token = os.getenv("BOT_SERVICE_TOKEN", "")
        if not self.service_token:
            logger.warning("BOT_SERVICE_TOKEN not set - agent-service calls will fail!")

        # Circuit breaker to prevent cascading failures
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=DEFAULT_FAILURE_THRESHOLD,  # Open circuit after N failures
            recovery_timeout=DEFAULT_RECOVERY_TIMEOUT,  # Wait before trying again
            success_threshold=DEFAULT_SUCCESS_THRESHOLD,  # Need N successes to close circuit
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create persistent HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self):
        """Close the HTTP client and cleanup resources."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def invoke_agent(
        self, agent_name: str, query: str, context: AgentContext
    ) -> AgentResponse:
        """Invoke an agent via HTTP with circuit breaker protection.

        Args:
            agent_name: Name of agent to invoke
            query: User query
            context: Context dictionary for agent

        Returns:
            Agent execution result with response and metadata

        Raises:
            AgentClientError: If agent execution fails
            CircuitBreakerError: If circuit breaker is open
        """
        # Wrap with circuit breaker
        wrapped_func = self.circuit_breaker.call(self._invoke_agent_internal)
        return await wrapped_func(agent_name, query, context)

    async def _invoke_agent_internal(
        self, agent_name: str, query: str, context: AgentContext
    ) -> AgentResponse:
        """Internal method that performs the actual agent invocation.

        Args:
            agent_name: Name of agent to invoke
            query: User query
            context: Context dictionary for agent

        Returns:
            Agent execution result with response and metadata

        Raises:
            AgentClientError: If agent execution fails
        """
        url = f"{self.base_url}/api/agents/{agent_name}/invoke"
        logger.info(f"Calling agent-service: {url}")

        # Serialize context - remove non-serializable objects
        serializable_context = self._prepare_context(context)

        # Prepare request body
        request_body = {"query": query, "context": serializable_context}
        request_body_str = json.dumps(
            request_body, separators=(",", ":"), sort_keys=True
        )

        # Retry with exponential backoff for transient failures
        for attempt in range(self.max_retries):
            try:
                # Prepare headers with service token
                headers = {"X-Service-Token": self.service_token}

                # Add HMAC signature for request integrity and replay attack prevention
                headers = add_signature_headers(
                    headers,
                    self.service_token,
                    request_body_str,
                )

                # Add trace ID for request tracing across services
                headers = add_trace_id_to_headers(headers)
                trace_id = get_or_create_trace_id()
                logger.info(f"[{trace_id}] Calling agent-service: {agent_name} | {url}")

                # Add OpenTelemetry trace context propagation
                headers = add_otel_headers(headers)

                # Create span for HTTP client call
                with create_span(
                    "http.client.agent_service.invoke",
                    attributes={
                        "http.method": "POST",
                        "http.url": url,
                        "agent.name": agent_name,
                        "service.name": "agent-service",
                    },
                    span_kind=SPAN_KIND_CLIENT,
                ):
                    client = await self._get_client()
                    response = await client.post(
                        url,
                        content=request_body_str,
                        headers={
                            **headers,
                            "Content-Type": "application/json",
                        },
                    )

                    if response.status_code == 404:
                        raise AgentClientError(f"Agent '{agent_name}' not found")

                    if response.status_code != 200:
                        raise AgentClientError(
                            f"Agent execution failed: {response.status_code} - {response.text}"
                        )

                    result = response.json()
                    return {
                        "response": result.get("response", ""),
                        "metadata": result.get("metadata", {}),
                    }

            except httpx.TimeoutException as e:
                record_exception(e)
                logger.warning(
                    f"Timeout on attempt {attempt + 1}/{self.max_retries}: {e}"
                )
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)  # Exponential backoff
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                raise AgentClientError("Agent execution timed out after retries") from e

            except httpx.ConnectError as e:
                record_exception(e)
                logger.warning(
                    f"Connection error on attempt {attempt + 1}/{self.max_retries}: {e}"
                )
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                raise AgentClientError(
                    "Unable to connect to agent service after retries"
                ) from e

            except Exception as e:
                record_exception(e)
                logger.error(f"Error calling agent-service: {e}", exc_info=True)
                raise AgentClientError(f"Agent execution failed: {str(e)}") from e
        # NOTE: Agent invocation metrics are tracked in agent-service itself,
        # not here. This ensures ALL invocations (Slack, LibreChat, direct API)
        # are counted at the source.

    async def list_agents(self) -> list[AgentInfo]:
        """List available agents.

        Returns:
            List of agent metadata

        Raises:
            AgentClientError: If request fails
        """
        url = f"{self.base_url}/api/agents"

        try:
            client = await self._get_client()
            response = await client.get(url)

            if response.status_code != 200:
                raise AgentClientError(f"Failed to list agents: {response.status_code}")

            result = response.json()
            return result.get("agents", [])

        except Exception as e:
            logger.error(f"Error listing agents: {e}", exc_info=True)
            raise AgentClientError(f"Failed to list agents: {str(e)}") from e

    def get_circuit_breaker_status(self) -> CircuitBreakerStatus:
        """Get current circuit breaker status for monitoring.

        Returns:
            Dictionary with circuit breaker state and metrics
        """
        return {
            "state": self.circuit_breaker.state.value,
            "failure_count": self.circuit_breaker.failure_count,
            "success_count": self.circuit_breaker.success_count,
            "last_failure_time": self.circuit_breaker.last_failure_time,
            "is_open": self.circuit_breaker.state == CircuitState.OPEN,
        }

    def _prepare_context(self, context: AgentContext) -> dict[str, Any]:
        """Prepare context for serialization.

        Removes non-serializable objects like service instances.

        Args:
            context: Original context dictionary

        Returns:
            Serializable context dictionary
        """
        serializable = {}

        # Copy simple, serializable values
        for key, value in context.items():
            # Skip service instances and other non-serializable objects
            if key in [
                "slack_service",
                "llm_service",
                "conversation_cache",
            ]:
                continue

            # Keep simple types
            if isinstance(value, (str, int, float, bool, type(None), list, dict)):  # noqa: UP038
                serializable[key] = value

        return serializable


class AgentClientError(Exception):
    """Exception raised when agent client operations fail."""

    pass


# Global client instance
_agent_client: AgentClient | None = None


def get_agent_client() -> AgentClient:
    """Get or create global agent client instance.

    Returns:
        AgentClient instance
    """
    global _agent_client  # noqa: PLW0603

    if _agent_client is None:
        import os

        base_url = os.getenv("AGENT_SERVICE_URL", "http://agent_service:8000")
        _agent_client = AgentClient(base_url=base_url)

    return _agent_client
