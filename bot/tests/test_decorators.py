"""Tests for utils/decorators.py"""

import asyncio
import time
from unittest.mock import patch

import pytest

from utils.decorators import (
    circuit_breaker,
    handle_service_errors,
    measure_performance,
    retry_on_failure,
)


class TestHandleServiceErrors:
    @pytest.mark.asyncio
    async def test_async_function_success(self):
        class TestService:
            @handle_service_errors()
            async def test_method(self):
                return "success"

        service = TestService()
        result = await service.test_method()

        assert result == "success"

    def test_sync_function_success(self):
        class TestService:
            @handle_service_errors()
            def test_method(self):
                return "success"

        service = TestService()
        result = service.test_method()

        assert result == "success"

    @pytest.mark.asyncio
    async def test_async_function_error_returns_default(self):
        class TestService:
            @handle_service_errors(default_return=[])
            async def test_method(self):
                raise ValueError("Test error")

        service = TestService()
        result = await service.test_method()

        assert result == []

    def test_sync_function_error_returns_default(self):
        class TestService:
            @handle_service_errors(default_return={})
            def test_method(self):
                raise ValueError("Test error")

        service = TestService()
        result = service.test_method()

        assert result == {}

    @pytest.mark.asyncio
    async def test_async_reraise_specific_exception(self):
        class TestService:
            @handle_service_errors(default_return=None, reraise_on=(ValueError,))
            async def test_method(self):
                raise ValueError("Should be reraised")

        service = TestService()

        with pytest.raises(ValueError, match="Should be reraised"):
            await service.test_method()

    def test_sync_reraise_specific_exception(self):
        class TestService:
            @handle_service_errors(default_return=None, reraise_on=(ValueError,))
            def test_method(self):
                raise ValueError("Should be reraised")

        service = TestService()

        with pytest.raises(ValueError, match="Should be reraised"):
            service.test_method()

    @pytest.mark.asyncio
    async def test_async_custom_log_error_method(self):
        class TestService:
            def __init__(self):
                self.logged_errors = []

            def _log_error(self, func_name, error, **kwargs):
                self.logged_errors.append((func_name, str(error), kwargs))

            @handle_service_errors()
            async def test_method(self):
                raise RuntimeError("Test error")

        service = TestService()
        result = await service.test_method()

        assert result is None  # Default return
        assert len(service.logged_errors) == 1
        assert service.logged_errors[0][0] == "test_method"
        assert "Test error" in service.logged_errors[0][1]

    def test_sync_custom_log_error_method(self):
        class TestService:
            def __init__(self):
                self.logged_errors = []

            def _log_error(self, func_name, error, **kwargs):
                self.logged_errors.append((func_name, str(error), kwargs))

            @handle_service_errors()
            def test_method(self):
                raise RuntimeError("Test error")

        service = TestService()
        result = service.test_method()

        assert result is None
        assert len(service.logged_errors) == 1
        assert service.logged_errors[0][0] == "test_method"

    @pytest.mark.asyncio
    async def test_async_record_error_metric(self):
        class TestService:
            def __init__(self):
                self.recorded_errors = []

            def _record_error_metric(self, func_name, error):
                self.recorded_errors.append((func_name, type(error).__name__))

            @handle_service_errors()
            async def test_method(self):
                raise ValueError("Metric test")

        service = TestService()
        await service.test_method()

        assert len(service.recorded_errors) == 1
        assert service.recorded_errors[0] == ("test_method", "ValueError")

    def test_sync_record_error_metric(self):
        class TestService:
            def __init__(self):
                self.recorded_errors = []

            def _record_error_metric(self, func_name, error):
                self.recorded_errors.append((func_name, type(error).__name__))

            @handle_service_errors()
            def test_method(self):
                raise ValueError("Metric test")

        service = TestService()
        service.test_method()

        assert len(service.recorded_errors) == 1
        assert service.recorded_errors[0] == ("test_method", "ValueError")

    @patch("utils.decorators.logger")
    @pytest.mark.asyncio
    async def test_async_default_logging(self, mock_logger):
        class TestService:
            @handle_service_errors()
            async def test_method(self):
                raise ValueError("Default logging test")

        service = TestService()
        await service.test_method()

        # Verify logger.error was called
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "Error in" in call_args[0][0]
        assert "test_method" in call_args[0][0]

    @patch("utils.decorators.logger")
    def test_sync_default_logging(self, mock_logger):
        class TestService:
            @handle_service_errors()
            def test_method(self):
                raise ValueError("Default logging test")

        service = TestService()
        service.test_method()

        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_no_logging_when_disabled(self):
        class TestService:
            def __init__(self):
                self.logged = False

            def _log_error(self, *args, **kwargs):
                self.logged = True

            @handle_service_errors(log_errors=False)
            async def test_method(self):
                raise ValueError("Should not be logged")

        service = TestService()
        await service.test_method()

        assert service.logged is False


class TestRetryOnFailure:
    @pytest.mark.asyncio
    async def test_async_success_on_first_attempt(self):
        class TestService:
            @retry_on_failure(max_attempts=3)
            async def test_method(self):
                return "success"

        service = TestService()
        result = await service.test_method()

        assert result == "success"

    def test_sync_success_on_first_attempt(self):
        class TestService:
            @retry_on_failure(max_attempts=3)
            def test_method(self):
                return "success"

        service = TestService()
        result = service.test_method()

        assert result == "success"

    @pytest.mark.asyncio
    async def test_async_retry_and_succeed(self):
        class TestService:
            def __init__(self):
                self.attempts = 0

            @retry_on_failure(max_attempts=3, delay=0.01, backoff=1.5)
            async def test_method(self):
                self.attempts += 1
                if self.attempts < 3:
                    raise ConnectionError("Temporary failure")
                return "success"

        service = TestService()
        result = await service.test_method()

        assert result == "success"
        assert service.attempts == 3

    def test_sync_retry_and_succeed(self):
        class TestService:
            def __init__(self):
                self.attempts = 0

            @retry_on_failure(max_attempts=3, delay=0.01, backoff=1.5)
            def test_method(self):
                self.attempts += 1
                if self.attempts < 3:
                    raise ConnectionError("Temporary failure")
                return "success"

        service = TestService()
        result = service.test_method()

        assert result == "success"
        assert service.attempts == 3

    @pytest.mark.asyncio
    async def test_async_all_retries_fail(self):
        class TestService:
            @retry_on_failure(max_attempts=2, delay=0.01)
            async def test_method(self):
                raise ConnectionError("Persistent failure")

        service = TestService()

        with pytest.raises(ConnectionError, match="Persistent failure"):
            await service.test_method()

    def test_sync_all_retries_fail(self):
        class TestService:
            @retry_on_failure(max_attempts=2, delay=0.01)
            def test_method(self):
                raise ConnectionError("Persistent failure")

        service = TestService()

        with pytest.raises(ConnectionError, match="Persistent failure"):
            service.test_method()

    @pytest.mark.asyncio
    async def test_async_exponential_backoff(self):
        class TestService:
            def __init__(self):
                self.attempts = []

            @retry_on_failure(max_attempts=3, delay=0.1, backoff=2.0)
            async def test_method(self):
                self.attempts.append(time.time())
                raise ConnectionError("Test")

        service = TestService()

        with pytest.raises(ConnectionError):
            await service.test_method()

        # Should have 3 attempts
        assert len(service.attempts) == 3

        # Verify exponential backoff (0.1s, 0.2s delays)
        delay1 = service.attempts[1] - service.attempts[0]
        delay2 = service.attempts[2] - service.attempts[1]

        # Allow some tolerance for timing
        assert 0.08 < delay1 < 0.15  # ~0.1s delay
        assert 0.18 < delay2 < 0.25  # ~0.2s delay

    @pytest.mark.asyncio
    async def test_async_custom_log_operation(self):
        class TestService:
            def __init__(self):
                self.log_entries = []

            def _log_operation(self, operation, **kwargs):
                self.log_entries.append((operation, kwargs))

            @retry_on_failure(max_attempts=3, delay=0.01)
            async def test_method(self):
                raise ValueError("Test error")

        service = TestService()

        with pytest.raises(ValueError):
            await service.test_method()

        # Should have 2 log entries (attempt 1 and 2, not 3 since no sleep on last)
        assert len(service.log_entries) == 2
        assert "retry_test_method" in service.log_entries[0][0]

    def test_sync_custom_log_operation(self):
        class TestService:
            def __init__(self):
                self.log_entries = []

            def _log_operation(self, operation, **kwargs):
                self.log_entries.append((operation, kwargs))

            @retry_on_failure(max_attempts=3, delay=0.01)
            def test_method(self):
                raise ValueError("Test error")

        service = TestService()

        with pytest.raises(ValueError):
            service.test_method()

        assert len(service.log_entries) == 2

    @pytest.mark.asyncio
    async def test_async_custom_log_error_final_failure(self):
        class TestService:
            def __init__(self):
                self.error_logs = []

            def _log_error(self, operation, error, **kwargs):
                self.error_logs.append((operation, str(error), kwargs))

            @retry_on_failure(max_attempts=2, delay=0.01)
            async def test_method(self):
                raise ValueError("Final failure")

        service = TestService()

        with pytest.raises(ValueError):
            await service.test_method()

        # Should have 1 final failure log
        assert len(service.error_logs) == 1
        assert "final_failure" in service.error_logs[0][0]
        assert service.error_logs[0][2]["attempts"] == 2

    @pytest.mark.asyncio
    async def test_async_specific_exceptions_only(self):
        class TestService:
            def __init__(self):
                self.attempts = 0

            @retry_on_failure(max_attempts=3, delay=0.01, exceptions=(ConnectionError,))
            async def test_method(self):
                self.attempts += 1
                raise ValueError("Wrong exception type")

        service = TestService()

        # Should raise immediately without retrying
        with pytest.raises(ValueError):
            await service.test_method()

        assert service.attempts == 1  # No retries


class TestMeasurePerformance:
    @pytest.mark.asyncio
    async def test_async_function_performance_tracking(self):
        class TestService:
            def __init__(self):
                self.operations = []

            def _log_operation(self, operation, **kwargs):
                self.operations.append((operation, kwargs))

            @measure_performance()
            async def test_method(self):
                await asyncio.sleep(0.01)
                return "result"

        service = TestService()
        result = await service.test_method()

        assert result == "result"
        assert len(service.operations) == 1
        assert "performance_test_method" in service.operations[0][0]
        assert service.operations[0][1]["duration_ms"] > 10  # At least 10ms
        assert service.operations[0][1]["success"] is True

    def test_sync_function_performance_tracking(self):
        class TestService:
            def __init__(self):
                self.operations = []

            def _log_operation(self, operation, **kwargs):
                self.operations.append((operation, kwargs))

            @measure_performance()
            def test_method(self):
                time.sleep(0.01)
                return "result"

        service = TestService()
        result = service.test_method()

        assert result == "result"
        assert len(service.operations) == 1
        assert service.operations[0][1]["duration_ms"] > 10

    @pytest.mark.asyncio
    async def test_async_custom_operation_name(self):
        class TestService:
            def __init__(self):
                self.operations = []

            def _log_operation(self, operation, **kwargs):
                self.operations.append((operation, kwargs))

            @measure_performance("custom_search")
            async def test_method(self):
                return "result"

        service = TestService()
        await service.test_method()

        assert "performance_custom_search" in service.operations[0][0]

    @pytest.mark.asyncio
    async def test_async_performance_on_error(self):
        class TestService:
            def __init__(self):
                self.operations = []

            def _log_operation(self, operation, **kwargs):
                self.operations.append((operation, kwargs))

            @measure_performance()
            async def test_method(self):
                raise ValueError("Test error")

        service = TestService()

        with pytest.raises(ValueError):
            await service.test_method()

        # Should still log performance
        assert len(service.operations) == 1
        assert service.operations[0][1]["success"] is False

    def test_sync_performance_on_error(self):
        class TestService:
            def __init__(self):
                self.operations = []

            def _log_operation(self, operation, **kwargs):
                self.operations.append((operation, kwargs))

            @measure_performance()
            def test_method(self):
                raise ValueError("Test error")

        service = TestService()

        with pytest.raises(ValueError):
            service.test_method()

        assert len(service.operations) == 1
        assert service.operations[0][1]["success"] is False

    @pytest.mark.asyncio
    async def test_async_record_performance_metric(self):
        class TestService:
            def __init__(self):
                self.metrics = []

            def _log_operation(self, operation, **kwargs):
                pass

            def _record_performance_metric(self, op_name, duration_ms, success):
                self.metrics.append((op_name, duration_ms, success))

            @measure_performance()
            async def test_method(self):
                return "result"

        service = TestService()
        await service.test_method()

        assert len(service.metrics) == 1
        assert service.metrics[0][0] == "test_method"
        assert service.metrics[0][1] >= 0  # Has duration (may be 0 for fast functions)
        assert service.metrics[0][2] is True  # Success


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_async_circuit_closed_on_success(self):
        class TestService:
            @circuit_breaker(failure_threshold=3)
            async def test_method(self):
                return "success"

        service = TestService()
        result = await service.test_method()

        assert result == "success"

        # Should be able to call again
        result = await service.test_method()
        assert result == "success"

    def test_sync_circuit_closed_on_success(self):
        class TestService:
            @circuit_breaker(failure_threshold=3)
            def test_method(self):
                return "success"

        service = TestService()
        result = service.test_method()

        assert result == "success"

    @pytest.mark.asyncio
    async def test_async_circuit_opens_after_threshold(self):
        class TestService:
            @circuit_breaker(failure_threshold=3, timeout=1.0)
            async def test_method(self):
                raise ConnectionError("Service unavailable")

        service = TestService()

        # First 3 calls should raise ConnectionError
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await service.test_method()

        # 4th call should raise RuntimeError (circuit open)
        with pytest.raises(RuntimeError, match="Circuit breaker open"):
            await service.test_method()

    def test_sync_circuit_opens_after_threshold(self):
        class TestService:
            @circuit_breaker(failure_threshold=3, timeout=1.0)
            def test_method(self):
                raise ConnectionError("Service unavailable")

        service = TestService()

        for _ in range(3):
            with pytest.raises(ConnectionError):
                service.test_method()

        with pytest.raises(RuntimeError, match="Circuit breaker open"):
            service.test_method()

    @pytest.mark.asyncio
    async def test_async_circuit_half_open_after_timeout(self):
        class TestService:
            def __init__(self):
                self.attempts = 0

            @circuit_breaker(failure_threshold=2, timeout=0.1)
            async def test_method(self):
                self.attempts += 1
                if self.attempts <= 2:
                    raise ConnectionError("Fail")
                return "recovered"

        service = TestService()

        # Open the circuit (2 failures)
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await service.test_method()

        # Should be open now
        with pytest.raises(RuntimeError, match="Circuit breaker open"):
            await service.test_method()

        # Wait for timeout
        await asyncio.sleep(0.15)

        # Should transition to half-open and allow request
        result = await service.test_method()
        assert result == "recovered"

        # Circuit should be closed now (success in half-open state)
        result = await service.test_method()
        assert result == "recovered"

    @pytest.mark.asyncio
    async def test_async_circuit_specific_exceptions(self):
        class TestService:
            def __init__(self):
                self.call_count = 0

            @circuit_breaker(
                failure_threshold=2, expected_exceptions=(ConnectionError,)
            )
            async def test_method(self):
                self.call_count += 1
                if self.call_count == 1:
                    raise ValueError("Should not trigger circuit")
                raise ConnectionError("Should trigger circuit")

        service = TestService()

        # First call raises ValueError (doesn't trigger circuit)
        with pytest.raises(ValueError):
            await service.test_method()

        # Second call should work (circuit not triggered)
        with pytest.raises(ConnectionError):
            await service.test_method()

    @pytest.mark.asyncio
    async def test_async_circuit_logs_on_open(self):
        class TestService:
            def __init__(self):
                self.error_logs = []

            def _log_error(self, operation, error, **kwargs):
                self.error_logs.append((operation, kwargs))

            @circuit_breaker(failure_threshold=2)
            async def test_method(self):
                raise ConnectionError("Test")

        service = TestService()

        # Trigger circuit breaker
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await service.test_method()

        # Should have logged circuit opening
        assert len(service.error_logs) == 1
        assert "circuit_breaker_open" in service.error_logs[0][0]
        assert service.error_logs[0][1]["failures"] == 2
        assert service.error_logs[0][1]["threshold"] == 2

    def test_sync_circuit_half_open_recovery(self):
        class TestService:
            def __init__(self):
                self.attempts = 0

            @circuit_breaker(failure_threshold=2, timeout=0.1)
            def test_method(self):
                self.attempts += 1
                if self.attempts <= 2:
                    raise ConnectionError("Fail")
                return "recovered"

        service = TestService()

        # Open circuit
        for _ in range(2):
            with pytest.raises(ConnectionError):
                service.test_method()

        # Wait for timeout
        time.sleep(0.15)

        # Should recover
        result = service.test_method()
        assert result == "recovered"
