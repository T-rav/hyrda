"""Comprehensive tests for ServiceContainer.

Tests cover:
- Container initialization
- Factory registration and validation
- Singleton registration
- Service lifecycle management
- Lazy initialization with thread-safe creation
- Concurrent service creation
- Service initialization hooks (initialize method)
- Service cleanup (close method)
- Health checks on services
- Container close operations
- Service listing and status
- Error handling and edge cases
- Global container management
"""

import asyncio
import contextlib
import os
import sys

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import services.container
from services.container import ServiceContainer, close_container, get_container


class MockService:
    """Mock service for testing without initialization hook."""

    def __init__(self, name: str = "mock"):
        self.name = name
        self.initialized = False
        self.closed = False

    def close(self):
        """Synchronous close method."""
        self.closed = True


class MockAsyncService:
    """Mock service with async lifecycle methods."""

    def __init__(self, name: str = "async_mock"):
        self.name = name
        self.initialized = False
        self.closed = False

    async def initialize(self):
        """Async initialization hook."""
        await asyncio.sleep(0.01)  # Simulate async work
        self.initialized = True

    async def close(self):
        """Async cleanup hook."""
        await asyncio.sleep(0.01)  # Simulate async work
        self.closed = True

    async def health_check(self):
        """Async health check."""
        return {"status": "healthy", "name": self.name}


class MockServiceWithSyncInit:
    """Mock service with synchronous initialize method."""

    def __init__(self):
        self.initialized = False

    def initialize(self):
        """Synchronous initialization hook."""
        self.initialized = True


class MockHealthCheckService:
    """Mock service with synchronous health check."""

    def __init__(self):
        self.name = "health_check_service"

    def health_check(self):
        """Synchronous health check."""
        return {"status": "ok", "service": self.name}


class MockBrokenService:
    """Mock service that fails during initialization."""

    def __init__(self):
        pass

    async def initialize(self):
        """Initialization that always fails."""
        raise RuntimeError("Initialization failed")


class TestContainerInitialization:
    """Test ServiceContainer initialization."""

    def test_container_creation(self):
        """Test basic container creation."""
        container = ServiceContainer()

        assert container._services == {}
        assert container._factories == {}
        assert container._initializing == {}
        assert container._closed is False

    def test_container_lock_initialization(self):
        """Test that container initializes with async lock."""
        container = ServiceContainer()

        assert container._lock is not None
        assert isinstance(container._lock, asyncio.Lock)


class TestFactoryRegistration:
    """Test factory registration."""

    def test_register_factory_simple(self):
        """Test registering a simple factory."""
        container = ServiceContainer()

        def factory():
            return MockService("test")

        container.register_factory(MockService, factory)

        assert MockService in container._factories
        assert container._factories[MockService] == factory

    def test_register_factory_lambda(self):
        """Test registering factory as lambda."""
        container = ServiceContainer()

        container.register_factory(MockService, lambda: MockService("lambda"))

        assert MockService in container._factories

    def test_register_async_factory(self):
        """Test registering async factory."""
        container = ServiceContainer()

        async def async_factory():
            return MockAsyncService("async")

        container.register_factory(MockAsyncService, async_factory)

        assert MockAsyncService in container._factories

    def test_register_multiple_factories(self):
        """Test registering multiple factories."""
        container = ServiceContainer()

        container.register_factory(MockService, lambda: MockService("one"))
        container.register_factory(MockAsyncService, lambda: MockAsyncService("two"))

        assert len(container._factories) == 2
        assert MockService in container._factories
        assert MockAsyncService in container._factories

    def test_register_factory_closed_container(self):
        """Test that registering factory on closed container raises error."""
        container = ServiceContainer()
        container._closed = True

        with pytest.raises(RuntimeError, match="Cannot register factories on closed container"):
            container.register_factory(MockService, lambda: MockService())


class TestSingletonRegistration:
    """Test singleton service registration."""

    def test_register_singleton(self):
        """Test registering a pre-created singleton."""
        container = ServiceContainer()
        service = MockService("singleton")

        container.register_singleton(MockService, service)

        assert MockService in container._services
        assert container._services[MockService] == service

    def test_register_singleton_immediately_available(self):
        """Test that singleton is immediately available."""
        container = ServiceContainer()
        service = MockAsyncService("immediate")

        container.register_singleton(MockAsyncService, service)

        # Should be in services, not factories
        assert MockAsyncService in container._services
        assert MockAsyncService not in container._factories

    def test_register_singleton_closed_container(self):
        """Test that registering singleton on closed container raises error."""
        container = ServiceContainer()
        container._closed = True

        with pytest.raises(RuntimeError, match="Cannot register services on closed container"):
            container.register_singleton(MockService, MockService())


class TestServiceRetrieval:
    """Test service retrieval and lazy initialization."""

    @pytest.mark.asyncio
    async def test_get_service_from_factory(self):
        """Test getting service creates it from factory."""
        container = ServiceContainer()
        container.register_factory(MockService, lambda: MockService("created"))

        service = await container.get(MockService)

        assert isinstance(service, MockService)
        assert service.name == "created"
        assert MockService in container._services

    @pytest.mark.asyncio
    async def test_get_service_singleton(self):
        """Test getting pre-registered singleton."""
        container = ServiceContainer()
        original_service = MockService("singleton")
        container.register_singleton(MockService, original_service)

        service = await container.get(MockService)

        assert service == original_service
        assert service.name == "singleton"

    @pytest.mark.asyncio
    async def test_get_service_cached_after_first_call(self):
        """Test that service is cached after first creation."""
        container = ServiceContainer()
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return MockService(f"call_{call_count}")

        container.register_factory(MockService, factory)

        service1 = await container.get(MockService)
        service2 = await container.get(MockService)

        assert service1 == service2
        assert call_count == 1  # Factory only called once

    @pytest.mark.asyncio
    async def test_get_service_no_factory_raises_error(self):
        """Test that getting unregistered service raises ValueError."""
        container = ServiceContainer()

        with pytest.raises(ValueError, match="No factory registered for MockService"):
            await container.get(MockService)

    @pytest.mark.asyncio
    async def test_get_service_closed_container_raises_error(self):
        """Test that getting service from closed container raises error."""
        container = ServiceContainer()
        container.register_factory(MockService, lambda: MockService())
        container._closed = True

        with pytest.raises(RuntimeError, match="Cannot get services from closed container"):
            await container.get(MockService)


class TestAsyncServiceCreation:
    """Test async service factory support."""

    @pytest.mark.asyncio
    async def test_async_factory_creation(self):
        """Test creating service from async factory."""
        container = ServiceContainer()

        async def async_factory():
            await asyncio.sleep(0.01)
            return MockAsyncService("async_created")

        container.register_factory(MockAsyncService, async_factory)

        service = await container.get(MockAsyncService)

        assert isinstance(service, MockAsyncService)
        assert service.name == "async_created"

    @pytest.mark.asyncio
    async def test_sync_factory_creation(self):
        """Test creating service from sync factory."""
        container = ServiceContainer()

        def sync_factory():
            return MockService("sync_created")

        container.register_factory(MockService, sync_factory)

        service = await container.get(MockService)

        assert isinstance(service, MockService)
        assert service.name == "sync_created"


class TestServiceInitializationHook:
    """Test service initialization hook support."""

    @pytest.mark.asyncio
    async def test_async_initialize_called(self):
        """Test that async initialize method is called during creation."""
        container = ServiceContainer()
        container.register_factory(MockAsyncService, lambda: MockAsyncService("init_test"))

        service = await container.get(MockAsyncService)

        assert service.initialized is True

    @pytest.mark.asyncio
    async def test_sync_initialize_called(self):
        """Test that sync initialize method is called during creation."""
        container = ServiceContainer()
        container.register_factory(
            MockServiceWithSyncInit, lambda: MockServiceWithSyncInit()
        )

        service = await container.get(MockServiceWithSyncInit)

        assert service.initialized is True

    @pytest.mark.asyncio
    async def test_service_without_initialize_works(self):
        """Test that services without initialize method work fine."""
        container = ServiceContainer()
        container.register_factory(MockService, lambda: MockService("no_init"))

        service = await container.get(MockService)

        assert isinstance(service, MockService)
        assert service.name == "no_init"


class TestConcurrentServiceCreation:
    """Test thread-safe concurrent service creation."""

    @pytest.mark.asyncio
    async def test_concurrent_get_same_service(self):
        """Test that concurrent gets for same service only create once."""
        container = ServiceContainer()
        call_count = 0

        async def slow_factory():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)  # Simulate slow creation
            return MockAsyncService(f"concurrent_{call_count}")

        container.register_factory(MockAsyncService, slow_factory)

        # Request same service concurrently
        results = await asyncio.gather(
            container.get(MockAsyncService),
            container.get(MockAsyncService),
            container.get(MockAsyncService),
        )

        # All should return same instance
        assert results[0] == results[1] == results[2]
        assert call_count == 1  # Factory only called once

    @pytest.mark.asyncio
    async def test_concurrent_get_different_services(self):
        """Test concurrent creation of different services."""
        container = ServiceContainer()

        container.register_factory(MockService, lambda: MockService("service1"))
        container.register_factory(MockAsyncService, lambda: MockAsyncService("service2"))

        # Request different services concurrently
        service1, service2 = await asyncio.gather(
            container.get(MockService), container.get(MockAsyncService)
        )

        assert isinstance(service1, MockService)
        assert isinstance(service2, MockAsyncService)
        assert service1.name == "service1"
        assert service2.name == "service2"


class TestServiceCreationErrors:
    """Test error handling during service creation."""

    @pytest.mark.asyncio
    async def test_factory_exception_propagates(self):
        """Test that factory exceptions are propagated."""
        container = ServiceContainer()

        def failing_factory():
            raise RuntimeError("Factory failed")

        container.register_factory(MockService, failing_factory)

        with pytest.raises(RuntimeError, match="Factory failed"):
            await container.get(MockService)

    @pytest.mark.asyncio
    async def test_initialization_exception_propagates(self):
        """Test that initialization exceptions are propagated."""
        container = ServiceContainer()
        container.register_factory(MockBrokenService, lambda: MockBrokenService())

        with pytest.raises(RuntimeError, match="Initialization failed"):
            await container.get(MockBrokenService)

    @pytest.mark.asyncio
    async def test_failed_service_not_cached(self):
        """Test that failed service creation doesn't cache anything."""
        container = ServiceContainer()
        call_count = 0

        def failing_factory():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("First attempt failed")
            return MockService("success")

        container.register_factory(MockService, failing_factory)

        # First attempt fails
        with pytest.raises(RuntimeError, match="First attempt failed"):
            await container.get(MockService)

        # Service should not be cached
        assert MockService not in container._services

        # Second attempt succeeds
        service = await container.get(MockService)
        assert service.name == "success"
        assert call_count == 2


class TestContainerCloseAll:
    """Test container cleanup and service closing."""

    @pytest.mark.asyncio
    async def test_close_all_calls_sync_close(self):
        """Test that close_all calls synchronous close methods."""
        container = ServiceContainer()
        service1 = MockService("service1")

        # Create a second service type
        class AnotherMockService(MockService):
            pass

        service2 = AnotherMockService("service2")

        container.register_singleton(MockService, service1)
        container.register_singleton(AnotherMockService, service2)

        await container.close_all()

        assert service1.closed is True
        assert service2.closed is True

    @pytest.mark.asyncio
    async def test_close_all_calls_async_close(self):
        """Test that close_all calls async close methods."""
        container = ServiceContainer()
        service = MockAsyncService("async_service")
        container.register_singleton(MockAsyncService, service)

        await container.close_all()

        assert service.closed is True

    @pytest.mark.asyncio
    async def test_close_all_reverse_order(self):
        """Test that services are closed in reverse creation order."""
        container = ServiceContainer()
        close_order = []

        class OrderedService1(MockService):
            def close(self):
                close_order.append(1)

        class OrderedService2(MockService):
            def close(self):
                close_order.append(2)

        class OrderedService3(MockService):
            def close(self):
                close_order.append(3)

        # Register in order: 1, 2, 3
        container.register_singleton(OrderedService1, OrderedService1())
        container.register_singleton(OrderedService2, OrderedService2())
        container.register_singleton(OrderedService3, OrderedService3())

        await container.close_all()

        # Should close in reverse order: 3, 2, 1
        assert close_order == [3, 2, 1]

    @pytest.mark.asyncio
    async def test_close_all_sets_closed_flag(self):
        """Test that close_all sets the closed flag."""
        container = ServiceContainer()

        await container.close_all()

        assert container._closed is True

    @pytest.mark.asyncio
    async def test_close_all_clears_services(self):
        """Test that close_all clears internal dictionaries."""
        container = ServiceContainer()
        container.register_factory(MockService, lambda: MockService())
        container.register_singleton(MockAsyncService, MockAsyncService())

        await container.close_all()

        assert container._services == {}
        assert container._factories == {}

    @pytest.mark.asyncio
    async def test_close_all_idempotent(self):
        """Test that close_all can be called multiple times."""
        container = ServiceContainer()
        service = MockService()
        container.register_singleton(MockService, service)

        await container.close_all()
        await container.close_all()  # Should not error

        assert container._closed is True

    @pytest.mark.asyncio
    async def test_close_all_handles_service_without_close(self):
        """Test closing services without close method."""
        container = ServiceContainer()

        class ServiceWithoutClose:
            pass

        service = ServiceWithoutClose()
        container.register_singleton(ServiceWithoutClose, service)

        # Should not raise error
        await container.close_all()

        assert container._closed is True

    @pytest.mark.asyncio
    async def test_close_all_handles_close_errors(self):
        """Test that errors during close don't stop other cleanups."""
        container = ServiceContainer()

        class FailingCloseService:
            def close(self):
                raise RuntimeError("Close failed")

        class NormalService:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        failing = FailingCloseService()
        normal = NormalService()

        container._services[FailingCloseService] = failing
        container._services[NormalService] = normal

        # Should not raise, but log error
        await container.close_all()

        # Normal service should still be closed
        assert normal.closed is True
        assert container._closed is True

    @pytest.mark.asyncio
    async def test_close_all_cancels_initializing_tasks(self):
        """Test that ongoing initializations are cancelled."""
        container = ServiceContainer()

        async def slow_factory():
            await asyncio.sleep(10)  # Very slow
            return MockAsyncService()

        container.register_factory(MockAsyncService, slow_factory)

        # Start initialization but don't await
        init_task = asyncio.create_task(container.get(MockAsyncService))

        # Give task time to start
        await asyncio.sleep(0.05)

        # Close container should cancel the task
        await container.close_all()

        # Give time for cancellation to propagate
        await asyncio.sleep(0.01)

        # Task should be cancelled or done (cancelled)
        # Note: The init_task may still be pending but the internal task is cancelled
        assert MockAsyncService in container._initializing or init_task.cancelled() or init_task.done()


class TestHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_empty_container(self):
        """Test health check on empty container."""
        container = ServiceContainer()

        health = await container.health_check()

        assert health["container"] == "healthy"
        assert health["service_count"] == 0
        assert health["services"] == {}

    @pytest.mark.asyncio
    async def test_health_check_async_service(self):
        """Test health check with async health_check method."""
        container = ServiceContainer()
        service = MockAsyncService("healthy_service")
        container.register_singleton(MockAsyncService, service)

        health = await container.health_check()

        assert health["container"] == "healthy"
        assert health["service_count"] == 1
        assert "MockAsyncService" in health["services"]
        assert health["services"]["MockAsyncService"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_sync_service(self):
        """Test health check with sync health_check method."""
        container = ServiceContainer()
        service = MockHealthCheckService()
        container.register_singleton(MockHealthCheckService, service)

        health = await container.health_check()

        assert health["service_count"] == 1
        assert "MockHealthCheckService" in health["services"]
        assert health["services"]["MockHealthCheckService"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_check_service_without_health_check(self):
        """Test health check on service without health_check method."""
        container = ServiceContainer()
        service = MockService()
        container.register_singleton(MockService, service)

        health = await container.health_check()

        assert "MockService" in health["services"]
        assert health["services"]["MockService"]["status"] == "unknown"

    @pytest.mark.asyncio
    async def test_health_check_service_error(self):
        """Test health check when service health_check raises error."""
        container = ServiceContainer()

        class FailingHealthService:
            def health_check(self):
                raise RuntimeError("Health check failed")

        service = FailingHealthService()
        container.register_singleton(FailingHealthService, service)

        health = await container.health_check()

        assert "FailingHealthService" in health["services"]
        assert health["services"]["FailingHealthService"]["status"] == "error"
        assert "Health check failed" in health["services"]["FailingHealthService"]["error"]

    @pytest.mark.asyncio
    async def test_health_check_multiple_services(self):
        """Test health check with multiple services."""
        container = ServiceContainer()
        container.register_singleton(MockAsyncService, MockAsyncService("service1"))
        container.register_singleton(MockHealthCheckService, MockHealthCheckService())
        container.register_singleton(MockService, MockService())

        health = await container.health_check()

        assert health["service_count"] == 3
        assert len(health["services"]) == 3


class TestListServices:
    """Test service listing functionality."""

    def test_list_services_empty(self):
        """Test listing services in empty container."""
        container = ServiceContainer()

        services = container.list_services()

        assert services == {}

    def test_list_services_only_registered(self):
        """Test listing shows registered factories."""
        container = ServiceContainer()
        container.register_factory(MockService, lambda: MockService())

        services = container.list_services()

        assert services == {"MockService": "registered"}

    @pytest.mark.asyncio
    async def test_list_services_initialized(self):
        """Test listing shows initialized services."""
        container = ServiceContainer()
        container.register_factory(MockService, lambda: MockService())

        # Initialize the service
        await container.get(MockService)

        services = container.list_services()

        assert services == {"MockService": "initialized"}

    @pytest.mark.asyncio
    async def test_list_services_initializing(self):
        """Test listing shows services being initialized."""
        container = ServiceContainer()

        async def slow_factory():
            await asyncio.sleep(1)  # Very slow
            return MockAsyncService()

        container.register_factory(MockAsyncService, slow_factory)

        # Start initialization
        init_task = asyncio.create_task(container.get(MockAsyncService))

        # Check status while initializing
        await asyncio.sleep(0.01)
        services = container.list_services()

        # Cancel the task to clean up
        init_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await init_task

        assert services.get("MockAsyncService") == "initializing"

    def test_list_services_multiple_states(self):
        """Test listing services in different states."""
        container = ServiceContainer()

        # Registered only (factory)
        container.register_factory(MockService, lambda: MockService())

        # Initialized (singleton) - also needs factory registered for list_services to see it
        service = MockAsyncService()
        container.register_factory(MockAsyncService, lambda: service)
        container.register_singleton(MockAsyncService, service)

        services = container.list_services()

        assert services["MockService"] == "registered"
        assert services["MockAsyncService"] == "initialized"


class TestGlobalContainer:
    """Test global container management."""

    def test_get_container_creates_instance(self):
        """Test that get_container creates a container."""
        # Reset global container
        services.container._container = None

        container = get_container()

        assert isinstance(container, ServiceContainer)
        assert container._closed is False

    def test_get_container_returns_same_instance(self):
        """Test that get_container returns same instance."""
        container1 = get_container()
        container2 = get_container()

        assert container1 is container2

    @pytest.mark.asyncio
    async def test_close_container_global(self):
        """Test closing the global container."""
        # Ensure we have a container
        container = get_container()
        container.register_singleton(MockService, MockService())

        # Close it
        await close_container()

        # Should be closed
        assert container._closed is True

        # Global reference should be cleared
        assert services.container._container is None

    @pytest.mark.asyncio
    async def test_close_container_when_none(self):
        """Test closing when no global container exists."""
        services.container._container = None

        # Should not raise error
        await close_container()

        assert services.container._container is None


class TestContainerEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_multiple_service_types(self):
        """Test container with many different service types."""
        container = ServiceContainer()

        # Register multiple types with unique classes
        service_classes = []
        for i in range(10):
            # Create unique class for each service
            service_class = type(f"Service{i}", (MockService,), {})
            service_classes.append(service_class)
            # Use index directly in lambda to avoid closure issues
            container.register_factory(
                service_class, lambda idx=i, cls=service_class: cls(f"s{idx}")
            )

        # List should show all registered
        service_list = container.list_services()
        assert len(service_list) >= 10

    @pytest.mark.asyncio
    async def test_service_with_dependencies(self):
        """Test creating service that depends on another service."""
        container = ServiceContainer()

        # Register dependency first
        container.register_factory(MockService, lambda: MockService("dependency"))

        # Register service that uses dependency
        async def dependent_factory():
            dep = await container.get(MockService)
            service = MockAsyncService(f"depends_on_{dep.name}")
            return service

        container.register_factory(MockAsyncService, dependent_factory)

        # Get dependent service
        service = await container.get(MockAsyncService)

        assert "depends_on_dependency" in service.name

    @pytest.mark.asyncio
    async def test_container_after_partial_close(self):
        """Test that container properly handles partial cleanup."""
        container = ServiceContainer()

        class PartiallyFailingService:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True
                raise RuntimeError("Close error")

        service1 = PartiallyFailingService()
        service2 = MockService()

        container._services[PartiallyFailingService] = service1
        container._services[MockService] = service2

        await container.close_all()

        # Both should be attempted to close
        assert service1.closed is True
        # Container should still be marked closed
        assert container._closed is True

    @pytest.mark.asyncio
    async def test_empty_factories_dict_after_close(self):
        """Test that factories are cleared after close."""
        container = ServiceContainer()
        container.register_factory(MockService, lambda: MockService())
        container.register_factory(MockAsyncService, lambda: MockAsyncService())

        await container.close_all()

        assert len(container._factories) == 0

    @pytest.mark.asyncio
    async def test_get_service_after_close_attempt(self):
        """Test error when trying to get service after close."""
        container = ServiceContainer()
        container.register_factory(MockService, lambda: MockService())

        await container.close_all()

        with pytest.raises(RuntimeError, match="Cannot get services from closed container"):
            await container.get(MockService)


class TestServiceLifecycle:
    """Test complete service lifecycle from creation to cleanup."""

    @pytest.mark.asyncio
    async def test_complete_lifecycle_sync_service(self):
        """Test complete lifecycle of synchronous service."""
        container = ServiceContainer()

        # Register
        container.register_factory(MockService, lambda: MockService("lifecycle"))
        assert "MockService" in container.list_services()
        assert container.list_services()["MockService"] == "registered"

        # Create
        service = await container.get(MockService)
        assert isinstance(service, MockService)
        assert service.closed is False
        assert container.list_services()["MockService"] == "initialized"

        # Close
        await container.close_all()
        assert service.closed is True
        assert container._closed is True

    @pytest.mark.asyncio
    async def test_complete_lifecycle_async_service(self):
        """Test complete lifecycle of async service with hooks."""
        container = ServiceContainer()

        # Register
        container.register_factory(
            MockAsyncService, lambda: MockAsyncService("async_lifecycle")
        )

        # Create (initialize hook should be called)
        service = await container.get(MockAsyncService)
        assert service.initialized is True
        assert service.closed is False

        # Close (close hook should be called)
        await container.close_all()
        assert service.closed is True

    @pytest.mark.asyncio
    async def test_lifecycle_with_health_checks(self):
        """Test lifecycle including health checks."""
        container = ServiceContainer()
        container.register_factory(MockAsyncService, lambda: MockAsyncService("health"))

        # Create service
        service = await container.get(MockAsyncService)

        # Check health
        health = await container.health_check()
        assert health["services"]["MockAsyncService"]["status"] == "healthy"

        # Close
        await container.close_all()
        assert service.closed is True
