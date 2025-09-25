"""
Tests for Base Service Classes

Tests the base service functionality including initialization,
lifecycle management, and error handling patterns.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.base import BaseService, ManagedService


class MockBaseService(BaseService):
    """Mock implementation of BaseService for testing."""

    def __init__(self, should_fail_init: bool = False, should_fail_close: bool = False):
        super().__init__("test_service")
        self.should_fail_init = should_fail_init
        self.should_fail_close = should_fail_close
        self.init_called = False
        self.close_called = False

    async def _initialize(self):
        """Mock initialization."""
        if self.should_fail_init:
            raise RuntimeError("Initialization failed")
        self.init_called = True

    async def _close(self):
        """Mock cleanup."""
        if self.should_fail_close:
            raise RuntimeError("Close failed")
        self.close_called = True


class TestBaseService:
    """Test cases for BaseService."""

    def test_service_creation(self):
        """Test basic service creation."""
        service = MockBaseService()

        assert service.service_name == "test_service"
        assert service.is_initialized is False
        assert service.is_closed is False

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test service initialization."""
        service = MockBaseService()

        await service.initialize()

        assert service.is_initialized is True
        assert service.init_called is True

    @pytest.mark.asyncio
    async def test_initialization_idempotent(self):
        """Test that initialization can be called multiple times safely."""
        service = MockBaseService()

        # Initialize multiple times
        await service.initialize()
        await service.initialize()
        await service.initialize()

        assert service.is_initialized is True
        assert service.init_called is True  # Should only be called once

    @pytest.mark.asyncio
    async def test_initialization_failure(self):
        """Test handling of initialization failure."""
        service = MockBaseService(should_fail_init=True)

        with pytest.raises(RuntimeError, match="Initialization failed"):
            await service.initialize()

        assert service.is_initialized is False

    @pytest.mark.asyncio
    async def test_close(self):
        """Test service close."""
        service = MockBaseService()
        await service.initialize()

        await service.close()

        assert service.is_closed is True
        assert service.close_called is True

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        """Test that close can be called multiple times safely."""
        service = MockBaseService()
        await service.initialize()

        # Close multiple times
        await service.close()
        await service.close()
        await service.close()

        assert service.is_closed is True
        assert service.close_called is True  # Should only be called once

    @pytest.mark.asyncio
    async def test_close_failure(self):
        """Test handling of close failure."""
        service = MockBaseService(should_fail_close=True)
        await service.initialize()

        with pytest.raises(RuntimeError, match="Close failed"):
            await service.close()

        # Service should still be marked as closed
        assert service.is_closed is True

    @pytest.mark.asyncio
    async def test_ensure_initialized(self):
        """Test ensure_initialized method."""
        service = MockBaseService()

        # Should initialize if not initialized
        await service.ensure_initialized()
        assert service.is_initialized is True

        # Should not reinitialize
        service.init_called = False
        await service.ensure_initialized()
        assert service.init_called is False  # Not called again

    @pytest.mark.asyncio
    async def test_ensure_initialized_on_closed_service(self):
        """Test ensure_initialized on closed service."""
        service = MockBaseService()
        await service.initialize()
        await service.close()

        with pytest.raises(RuntimeError, match="Service test_service is closed"):
            await service.ensure_initialized()

    def test_health_check(self):
        """Test basic health check."""
        service = MockBaseService()

        health = service.health_check()

        assert health["service"] == "test_service"
        assert health["status"] == "unhealthy"  # Not initialized
        assert health["initialized"] is False
        assert health["closed"] is False

    @pytest.mark.asyncio
    async def test_health_check_initialized(self):
        """Test health check on initialized service."""
        service = MockBaseService()
        await service.initialize()

        health = service.health_check()

        assert health["status"] == "healthy"
        assert health["initialized"] is True

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test service as async context manager."""
        service = MockBaseService()

        async with service as ctx_service:
            assert ctx_service is service
            assert service.is_initialized is True

        assert service.is_closed is True

    @pytest.mark.asyncio
    async def test_concurrent_initialization(self):
        """Test thread-safe initialization."""
        service = MockBaseService()

        # Start multiple concurrent initializations
        tasks = [service.initialize() for _ in range(5)]
        await asyncio.gather(*tasks)

        assert service.is_initialized is True

    def test_service_repr(self):
        """Test string representation."""
        service = MockBaseService()
        repr_str = repr(service)

        assert "MockBaseService" in repr_str
        assert "test_service" in repr_str
        assert "initialized=False" in repr_str
        assert "closed=False" in repr_str

    @patch("logging.getLogger")
    def test_logging_setup(self, mock_get_logger):
        """Test that logging is set up correctly."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        service = MockBaseService()

        # Logger should be created with the module name
        mock_get_logger.assert_called_with(service.__class__.__module__)
        assert service.logger is mock_logger

    def test_log_operation(self):
        """Test operation logging helper."""
        service = MockBaseService()
        service.logger = Mock()

        service._log_operation("test_operation", user_id="123", success=True)

        service.logger.info.assert_called_once()
        call_args = service.logger.info.call_args

        assert "test_service - test_operation" in call_args[0][0]
        assert call_args[1]["extra"]["service"] == "test_service"
        assert call_args[1]["extra"]["operation"] == "test_operation"
        assert call_args[1]["extra"]["user_id"] == "123"
        assert call_args[1]["extra"]["success"] is True

    def test_log_error(self):
        """Test error logging helper."""
        service = MockBaseService()
        service.logger = Mock()

        error = ValueError("Test error")
        service._log_error("test_operation", error, user_id="123")

        service.logger.error.assert_called_once()
        call_args = service.logger.error.call_args

        assert "test_service - test_operation failed" in call_args[0][0]
        assert call_args[1]["extra"]["service"] == "test_service"
        assert call_args[1]["extra"]["operation"] == "test_operation"
        assert call_args[1]["extra"]["error_type"] == "ValueError"
        assert call_args[1]["extra"]["error_message"] == "Test error"


class MockManagedService(ManagedService):
    """Mock implementation of ManagedService for testing."""

    def __init__(self):
        super().__init__("managed_test")
        self.init_called = False
        self.close_called = False

    async def _initialize(self):
        """Mock initialization."""
        self.init_called = True

    async def _close(self):
        """Mock cleanup."""
        await super()._close()  # Call parent to close dependencies
        self.close_called = True


class MockDependency:
    """Mock dependency for testing."""

    def __init__(self, name: str):
        self.name = name
        self.closed = False

    async def close(self):
        """Mock close method."""
        self.closed = True

    def health_check(self):
        """Mock health check."""
        return {"status": "healthy", "name": self.name}


class TestManagedService:
    """Test cases for ManagedService."""

    def test_dependency_management(self):
        """Test dependency addition and retrieval."""
        service = MockManagedService()
        dependency = MockDependency("test_dep")

        service.add_dependency("test", dependency)

        retrieved = service.get_dependency("test")
        assert retrieved is dependency

    def test_get_nonexistent_dependency(self):
        """Test getting nonexistent dependency raises error."""
        service = MockManagedService()

        with pytest.raises(KeyError, match="Dependency 'nonexistent' not found"):
            service.get_dependency("nonexistent")

    @pytest.mark.asyncio
    async def test_close_with_dependencies(self):
        """Test that dependencies are closed when service closes."""
        service = MockManagedService()
        dep1 = MockDependency("dep1")
        dep2 = MockDependency("dep2")

        service.add_dependency("dep1", dep1)
        service.add_dependency("dep2", dep2)

        # Initialize the service first
        await service.initialize()

        # Then close it
        await service.close()

        # Dependencies should be closed
        assert dep1.closed is True
        assert dep2.closed is True
        assert service.close_called is True

    def test_health_check_with_dependencies(self):
        """Test health check includes dependency health."""
        service = MockManagedService()
        dependency = MockDependency("test_dep")
        service.add_dependency("test", dependency)

        health = service.health_check()

        assert "dependencies" in health
        assert "test" in health["dependencies"]
        assert health["dependencies"]["test"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_dependency_close_error_handling(self):
        """Test handling of dependency close errors."""
        service = MockManagedService()

        # Create dependency that fails to close
        failing_dep = Mock()
        failing_dep.close = AsyncMock(side_effect=RuntimeError("Close failed"))

        service.add_dependency("failing", failing_dep)

        # Should not raise exception
        await service.close()
        assert service.close_called is True
