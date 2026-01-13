"""
Service Decorators for Error Handling and Observability

Provides consistent error handling, retry logic, and observability
patterns across all services.
"""

import asyncio
import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


def handle_service_errors(
    default_return: Any = None,
    log_errors: bool = True,
    reraise_on: tuple[type, ...] | None = None,
):
    """
    Decorator for consistent error handling across service methods.

    Args:
        default_return: Value to return on error (default: None)
        log_errors: Whether to log errors (default: True)
        reraise_on: Exception types to reraise instead of handling

    Example:
        @handle_service_errors(default_return=[], reraise_on=(ValueError,))
        async def get_documents(self, query: str) -> list:
            # Implementation that might raise exceptions
            return documents

    """

    def decorator(func: Callable[..., T]) -> Callable[..., T | Any]:
        @functools.wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            try:
                return await func(self, *args, **kwargs)
            except Exception as e:
                # Reraise specific exceptions if configured
                if reraise_on and isinstance(e, reraise_on):
                    raise

                # Log error with service context
                if log_errors and hasattr(self, "_log_error"):
                    self._log_error(func.__name__, e, args=args, kwargs=kwargs)
                elif log_errors:
                    logger.error(
                        f"Error in {func.__qualname__}: {e}",
                        extra={
                            "function": func.__qualname__,
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                        },
                    )

                # Record metric if metrics service is available
                if hasattr(self, "_record_error_metric"):
                    self._record_error_metric(func.__name__, e)

                return default_return

        @functools.wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                # Reraise specific exceptions if configured
                if reraise_on and isinstance(e, reraise_on):
                    raise

                # Log error with service context
                if log_errors and hasattr(self, "_log_error"):
                    self._log_error(func.__name__, e, args=args, kwargs=kwargs)
                elif log_errors:
                    logger.error(
                        f"Error in {func.__qualname__}: {e}",
                        extra={
                            "function": func.__qualname__,
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                        },
                    )

                # Record metric if metrics service is available
                if hasattr(self, "_record_error_metric"):
                    self._record_error_metric(func.__name__, e)

                return default_return

        # Return appropriate wrapper based on function type
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper  # type: ignore[return-value]

    return decorator


def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type, ...] = (Exception,),
):
    """
    Decorator for retry logic with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier for exponential backoff
        exceptions: Exception types to retry on

    Example:
        @retry_on_failure(max_attempts=3, delay=0.5, exceptions=(ConnectionError,))
        async def make_api_call(self) -> dict:
            # API call that might fail
            return response

    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return await func(self, *args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts - 1:  # Don't sleep on last attempt
                        if hasattr(self, "_log_operation"):
                            self._log_operation(
                                f"retry_{func.__name__}",
                                attempt=attempt + 1,
                                delay=current_delay,
                                error=str(e),
                            )

                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    # Final attempt failed
                    elif hasattr(self, "_log_error"):
                        self._log_error(
                            f"{func.__name__}_final_failure", e, attempts=max_attempts
                        )

            # Reraise the last exception if all attempts failed
            if last_exception:
                raise last_exception

        @functools.wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return func(self, *args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts - 1:  # Don't sleep on last attempt
                        if hasattr(self, "_log_operation"):
                            self._log_operation(
                                f"retry_{func.__name__}",
                                attempt=attempt + 1,
                                delay=current_delay,
                                error=str(e),
                            )

                        time.sleep(current_delay)
                        current_delay *= backoff
                    # Final attempt failed
                    elif hasattr(self, "_log_error"):
                        self._log_error(
                            f"{func.__name__}_final_failure", e, attempts=max_attempts
                        )

            # Reraise the last exception if all attempts failed
            if last_exception:
                raise last_exception

        # Return appropriate wrapper based on function type
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper  # type: ignore[return-value]

    return decorator


def measure_performance(operation_name: str | None = None):
    """
    Decorator to measure and log operation performance.

    Args:
        operation_name: Optional custom operation name for metrics

    Example:
        @measure_performance("document_search")
        async def search_documents(self, query: str) -> list:
            # Search implementation
            return results

    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        op_name = operation_name or func.__name__

        @functools.wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            start_time = time.time()
            success = True
            result = None

            try:
                result = await func(self, *args, **kwargs)
                return result
            except Exception:
                success = False
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000

                # Log performance
                if hasattr(self, "_log_operation"):
                    self._log_operation(
                        f"performance_{op_name}",
                        duration_ms=duration_ms,
                        success=success,
                    )

                # Record metric if available
                if hasattr(self, "_record_performance_metric"):
                    self._record_performance_metric(op_name, duration_ms, success)

        @functools.wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            start_time = time.time()
            success = True
            result = None

            try:
                result = func(self, *args, **kwargs)
                return result
            except Exception:
                success = False
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000

                # Log performance
                if hasattr(self, "_log_operation"):
                    self._log_operation(
                        f"performance_{op_name}",
                        duration_ms=duration_ms,
                        success=success,
                    )

                # Record metric if available
                if hasattr(self, "_record_performance_metric"):
                    self._record_performance_metric(op_name, duration_ms, success)

        # Return appropriate wrapper based on function type
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper  # type: ignore[return-value]

    return decorator


def circuit_breaker(
    failure_threshold: int = 5,
    timeout: float = 60.0,
    expected_exceptions: tuple[type, ...] = (Exception,),
):
    """
    Circuit breaker pattern for external service calls.

    Args:
        failure_threshold: Number of failures before opening circuit
        timeout: Time in seconds before attempting to close circuit
        expected_exceptions: Exception types that count as failures

    Example:
        @circuit_breaker(failure_threshold=3, timeout=30.0)
        async def call_external_api(self) -> dict:
            # External API call
            return response

    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Circuit breaker state (shared across all instances)
        state = {
            "failures": 0,
            "last_failure_time": 0,
            "state": "closed",  # closed, open, half-open
        }

        @functools.wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            current_time = time.time()

            # Check if circuit should be half-open
            if (
                state["state"] == "open"
                and current_time - state["last_failure_time"] > timeout
            ):
                state["state"] = "half-open"

            # Fail fast if circuit is open
            if state["state"] == "open":
                raise RuntimeError(f"Circuit breaker open for {func.__name__}")

            try:
                result = await func(self, *args, **kwargs)

                # Reset on success
                if state["state"] == "half-open":
                    state["state"] = "closed"
                    state["failures"] = 0

                return result

            except expected_exceptions as e:
                state["failures"] += 1
                state["last_failure_time"] = current_time

                # Open circuit if threshold reached
                if state["failures"] >= failure_threshold:
                    state["state"] = "open"

                    if hasattr(self, "_log_error"):
                        self._log_error(
                            f"circuit_breaker_open_{func.__name__}",
                            e,
                            failures=state["failures"],
                            threshold=failure_threshold,
                        )

                raise

        @functools.wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            current_time = time.time()

            # Check if circuit should be half-open
            if (
                state["state"] == "open"
                and current_time - state["last_failure_time"] > timeout
            ):
                state["state"] = "half-open"

            # Fail fast if circuit is open
            if state["state"] == "open":
                raise RuntimeError(f"Circuit breaker open for {func.__name__}")

            try:
                result = func(self, *args, **kwargs)

                # Reset on success
                if state["state"] == "half-open":
                    state["state"] = "closed"
                    state["failures"] = 0

                return result

            except expected_exceptions as e:
                state["failures"] += 1
                state["last_failure_time"] = current_time

                # Open circuit if threshold reached
                if state["failures"] >= failure_threshold:
                    state["state"] = "open"

                    if hasattr(self, "_log_error"):
                        self._log_error(
                            f"circuit_breaker_open_{func.__name__}",
                            e,
                            failures=state["failures"],
                            threshold=failure_threshold,
                        )

                raise

        # Return appropriate wrapper based on function type
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper  # type: ignore[return-value]

    return decorator
