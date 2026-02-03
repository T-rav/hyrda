"""
Tests for Base Service Classes

Tests the base service functionality including initialization,
lifecycle management, and error handling patterns using factory patterns.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.base import BaseService, ManagedService


class MockBaseService(BaseService):
    """Mock implementation of BaseService for testing."""

    def __init__(
        self,
        should_fail_init: bool = False,
        should_fail_close: bool = False,
        service_name: str = "test_service",
    ):
        super().__init__(service_name)
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


class BaseServiceFactory:
    """Factory for creating BaseService instances with different configurations"""

    @staticmethod
    def create_basic_service(service_name: str = "test_service") -> MockBaseService:
        """Create basic service instance"""
        return MockBaseService(service_name=service_name)

    @staticmethod
    def create_service_with_init_failure(
        service_name: str = "test_service",
    ) -> MockBaseService:
        """Create service that fails during initialization"""
        return MockBaseService(should_fail_init=True, service_name=service_name)

    @staticmethod
    def create_service_with_close_failure(
        service_name: str = "test_service",
    ) -> MockBaseService:
        """Create service that fails during close"""
        return MockBaseService(should_fail_close=True, service_name=service_name)

    @staticmethod
    def create_service_with_all_failures(
        service_name: str = "test_service",
    ) -> MockBaseService:
        """Create service that fails both init and close"""
        return MockBaseService(
            should_fail_init=True, should_fail_close=True, service_name=service_name
        )


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

    def __init__(
        self, name: str, should_fail_close: bool = False, health_status: str = "healthy"
    ):
        self.name = name
        self.closed = False
        self.should_fail_close = should_fail_close
        self.health_status = health_status

    async def close(self):
        """Mock close method."""
        if self.should_fail_close:
            raise RuntimeError("Close failed")
        self.closed = True

    def health_check(self):
        """Mock health check."""
        return {"status": self.health_status, "name": self.name}


class ManagedServiceFactory:
    """Factory for creating ManagedService instances and dependencies"""

    @staticmethod
    def create_basic_service() -> MockManagedService:
        """Create basic managed service"""
        return MockManagedService()

    @staticmethod
    def create_service_with_dependencies(
        dependencies: dict[str, MockDependency] | None = None,
    ) -> MockManagedService:
        """Create managed service with dependencies"""
        service = ManagedServiceFactory.create_basic_service()
        if dependencies:
            for name, dep in dependencies.items():
                service.add_dependency(name, dep)
        return service


class DependencyFactory:
    """Factory for creating mock dependencies"""

    @staticmethod
    def create_basic_dependency(name: str = "test_dep") -> MockDependency:
        """Create basic dependency"""
        return MockDependency(name=name)

    @staticmethod
    def create_failing_dependency(name: str = "failing_dep") -> MockDependency:
        """Create dependency that fails to close"""
        return MockDependency(name=name, should_fail_close=True)

    @staticmethod
    def create_unhealthy_dependency(name: str = "unhealthy_dep") -> MockDependency:
        """Create dependency with unhealthy status"""
        return MockDependency(name=name, health_status="unhealthy")

    @staticmethod
    def create_dependency_collection() -> dict[str, MockDependency]:
        """Create a collection of test dependencies"""
        return {
            "dep1": DependencyFactory.create_basic_dependency("dep1"),
            "dep2": DependencyFactory.create_basic_dependency("dep2"),
            "dep3": DependencyFactory.create_basic_dependency("dep3"),
        }


class TestBaseService:
    def test_service_creation(self):
        service = BaseServiceFactory.create_basic_service()

        assert service.service_name == "test_service"
        assert service.is_initialized is False
        assert service.is_closed is False

    @pytest.mark.asyncio
    async def test_initialization(self):
        service = BaseServiceFactory.create_basic_service()

        await service.initialize()

        assert service.is_initialized is True
        assert service.init_called is True

    @pytest.mark.asyncio
    async def test_initialization_idempotent(self):
        service = BaseServiceFactory.create_basic_service()

        # Initialize multiple times
        await service.initialize()
        await service.initialize()
        await service.initialize()

        assert service.is_initialized is True
        assert service.init_called is True  # Should only be called once

    @pytest.mark.asyncio
    async def test_initialization_failure(self):
        service = BaseServiceFactory.create_service_with_init_failure()

        with pytest.raises(RuntimeError, match="Initialization failed"):
            await service.initialize()

        assert service.is_initialized is False

    @pytest.mark.asyncio
    async def test_close(self):
        service = BaseServiceFactory.create_basic_service()
        await service.initialize()

        await service.close()

        assert service.is_closed is True
        assert service.close_called is True

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        service = BaseServiceFactory.create_basic_service()
        await service.initialize()

        # Close multiple times
        await service.close()
        await service.close()
        await service.close()

        assert service.is_closed is True
        assert service.close_called is True  # Should only be called once

    @pytest.mark.asyncio
    async def test_close_failure(self):
        service = BaseServiceFactory.create_service_with_close_failure()
        await service.initialize()

        with pytest.raises(RuntimeError, match="Close failed"):
            await service.close()

        # Service should still be marked as closed
        assert service.is_closed is True

    @pytest.mark.asyncio
    async def test_ensure_initialized(self):
        service = BaseServiceFactory.create_basic_service()

        # Should initialize if not initialized
        await service.ensure_initialized()
        assert service.is_initialized is True

        # Should not reinitialize
        service.init_called = False
        await service.ensure_initialized()
        assert service.init_called is False  # Not called again

    @pytest.mark.asyncio
    async def test_ensure_initialized_on_closed_service(self):
        service = BaseServiceFactory.create_basic_service()
        await service.initialize()
        await service.close()

        with pytest.raises(RuntimeError, match="Service test_service is closed"):
            await service.ensure_initialized()

    def test_health_check(self):
        service = BaseServiceFactory.create_basic_service()

        health = service.health_check()

        assert health.service_name == "test_service"
        assert health.status == "unhealthy"  # Not initialized
        assert "initialized=False" in health.details
        assert "closed=False" in health.details

    @pytest.mark.asyncio
    async def test_health_check_initialized(self):
        service = BaseServiceFactory.create_basic_service()
        await service.initialize()

        health = service.health_check()

        assert health.status == "healthy"
        assert "initialized=True" in health.details

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        service = BaseServiceFactory.create_basic_service()

        async with service as ctx_service:
            assert ctx_service is service
            assert service.is_initialized is True

        assert service.is_closed is True

    @pytest.mark.asyncio
    async def test_concurrent_initialization(self):
        service = BaseServiceFactory.create_basic_service()

        # Start multiple concurrent initializations
        tasks = [service.initialize() for _ in range(5)]
        await asyncio.gather(*tasks)

        assert service.is_initialized is True

    def test_service_repr(self):
        service = BaseServiceFactory.create_basic_service()
        repr_str = repr(service)

        assert "MockBaseService" in repr_str
        assert "test_service" in repr_str
        assert "initialized=False" in repr_str
        assert "closed=False" in repr_str

    @patch("logging.getLogger")
    def test_logging_setup(self, mock_get_logger):
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        service = BaseServiceFactory.create_basic_service()

        # Logger should be created with the module name
        mock_get_logger.assert_called_with(service.__class__.__module__)
        assert service.logger is mock_logger

    def test_log_operation(self):
        service = BaseServiceFactory.create_basic_service()
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
        service = BaseServiceFactory.create_basic_service()
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
    def test_dependency_management(self):
        service = ManagedServiceFactory.create_basic_service()
        dependency = DependencyFactory.create_basic_dependency("test_dep")

        service.add_dependency("test", dependency)

        retrieved = service.get_dependency("test")
        assert retrieved is dependency

    def test_get_nonexistent_dependency(self):
        service = ManagedServiceFactory.create_basic_service()

        with pytest.raises(KeyError, match="Dependency 'nonexistent' not found"):
            service.get_dependency("nonexistent")

    @pytest.mark.asyncio
    async def test_close_with_dependencies(self):
        dependencies = {
            "dep1": DependencyFactory.create_basic_dependency("dep1"),
            "dep2": DependencyFactory.create_basic_dependency("dep2"),
        }
        service = ManagedServiceFactory.create_service_with_dependencies(dependencies)

        # Initialize the service first
        await service.initialize()

        # Then close it
        await service.close()

        # Dependencies should be closed
        assert dependencies["dep1"].closed is True
        assert dependencies["dep2"].closed is True
        assert service.close_called is True

    def test_health_check_with_dependencies(self):
        dependency = DependencyFactory.create_basic_dependency("test_dep")
        service = ManagedServiceFactory.create_service_with_dependencies(
            {"test": dependency}
        )

        health = service.health_check()

        assert health.metrics is not None and "dependencies" in health.metrics
        assert health.metrics is not None
        assert "test" in health.metrics["dependencies"]
        assert health.metrics["dependencies"]["test"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_dependency_close_error_handling(self):
        service = ManagedServiceFactory.create_basic_service()

        # Create dependency that fails to close using Mock (original behavior)
        failing_dep = Mock()
        failing_dep.close = AsyncMock(side_effect=RuntimeError("Close failed"))

        service.add_dependency("failing", failing_dep)

        # Should not raise exception
        await service.close()
        assert service.close_called is True
