"""
Tests for Service Container

Tests the dependency injection container functionality including
service registration, lifecycle management, and error handling.
"""

import asyncio

import pytest

from services.container import ServiceContainer


class MockService:
    """Mock service for testing."""

    def __init__(self, name: str = "mock"):
        self.name = name
        self.initialized = False
        self.closed = False

    async def initialize(self):
        """Mock initialization."""
        self.initialized = True

    async def close(self):
        """Mock cleanup."""
        self.closed = True

    def health_check(self):
        """Mock health check."""
        return {"status": "healthy", "name": self.name}


class TestServiceContainer:
    """Test cases for ServiceContainer."""

    @pytest.fixture
    async def container(self):
        """Create a fresh container for each test."""
        container = ServiceContainer()
        yield container
        await container.close_all()

    def test_register_factory(self, container):
        """Test factory registration."""

        def create_mock_service():
            return MockService("test")

        container.register_factory(MockService, create_mock_service)

        # Should not raise
        assert MockService in container._factories

    def test_register_singleton(self, container):
        """Test singleton registration."""
        service = MockService("singleton")
        container.register_singleton(MockService, service)

        assert MockService in container._services
        assert container._services[MockService] is service

    @pytest.mark.asyncio
    async def test_get_service_lazy_initialization(self, container):
        """Test lazy service creation."""

        def create_mock_service():
            return MockService("lazy")

        container.register_factory(MockService, create_mock_service)

        # Service should not exist yet
        assert MockService not in container._services

        # Get service should create it
        service = await container.get(MockService)

        assert isinstance(service, MockService)
        assert service.name == "lazy"
        assert service.initialized is True
        assert MockService in container._services

    @pytest.mark.asyncio
    async def test_get_service_singleton_behavior(self, container):
        """Test that services are singletons."""

        def create_mock_service():
            return MockService("singleton")

        container.register_factory(MockService, create_mock_service)

        # Get service twice
        service1 = await container.get(MockService)
        service2 = await container.get(MockService)

        # Should be the same instance
        assert service1 is service2

    @pytest.mark.asyncio
    async def test_get_unregistered_service(self, container):
        """Test getting unregistered service raises error."""
        with pytest.raises(ValueError, match="No factory registered"):
            await container.get(MockService)

    @pytest.mark.asyncio
    async def test_async_factory(self, container):
        """Test async factory functions."""

        async def create_async_service():
            service = MockService("async")
            await service.initialize()
            return service

        container.register_factory(MockService, create_async_service)

        service = await container.get(MockService)
        assert service.initialized is True

    @pytest.mark.asyncio
    async def test_concurrent_initialization(self, container):
        """Test thread-safe concurrent initialization."""
        initialization_count = 0

        async def create_service():
            nonlocal initialization_count
            # Simulate slow initialization
            await asyncio.sleep(0.1)
            initialization_count += 1
            return MockService("concurrent")

        container.register_factory(MockService, create_service)

        # Start multiple concurrent gets
        tasks = [container.get(MockService) for _ in range(5)]
        services = await asyncio.gather(*tasks)

        # Should only initialize once
        assert initialization_count == 1

        # All should be the same instance
        for service in services:
            assert service is services[0]

    @pytest.mark.asyncio
    async def test_close_all_services(self, container):
        """Test graceful service shutdown."""
        services_created = []

        class Service0:
            def __init__(self):
                self.name = "service_0"
                self.closed = False
                services_created.append(self)

            async def initialize(self):
                pass

            async def close(self):
                self.closed = True

        class Service1:
            def __init__(self):
                self.name = "service_1"
                self.closed = False
                services_created.append(self)

            async def initialize(self):
                pass

            async def close(self):
                self.closed = True

        class Service2:
            def __init__(self):
                self.name = "service_2"
                self.closed = False
                services_created.append(self)

            async def initialize(self):
                pass

            async def close(self):
                self.closed = True

        # Register and create multiple services
        container.register_factory(Service0, Service0)
        container.register_factory(Service1, Service1)
        container.register_factory(Service2, Service2)

        await container.get(Service0)
        await container.get(Service1)
        await container.get(Service2)

        # Close all services
        await container.close_all()

        # All services should be closed
        for service in services_created:
            assert service.closed is True

        # Container should be closed
        assert container._closed is True

    @pytest.mark.asyncio
    async def test_health_check(self, container):
        """Test health check functionality."""
        container.register_factory(MockService, lambda: MockService("healthy"))

        # Create service
        await container.get(MockService)

        # Get health check
        health = await container.health_check()

        assert health["container"] == "healthy"
        assert health["service_count"] == 1
        assert "MockService" in health["services"]
        assert health["services"]["MockService"]["status"] == "healthy"

    def test_list_services(self, container):
        """Test service listing functionality."""
        # Register but don't create
        container.register_factory(MockService, lambda: MockService("test"))

        services = container.list_services()
        assert "MockService" in services
        assert services["MockService"] == "registered"

    @pytest.mark.asyncio
    async def test_error_handling_in_factory(self, container):
        """Test error handling during service creation."""

        def failing_factory():
            raise ValueError("Factory failed")

        container.register_factory(MockService, failing_factory)

        with pytest.raises(ValueError, match="Factory failed"):
            await container.get(MockService)

    @pytest.mark.asyncio
    async def test_closed_container_operations(self, container):
        """Test operations on closed container."""
        await container.close_all()

        # Should raise errors
        with pytest.raises(RuntimeError, match="closed container"):
            container.register_factory(MockService, lambda: MockService())

        with pytest.raises(RuntimeError, match="closed container"):
            await container.get(MockService)

    @pytest.mark.asyncio
    async def test_service_with_no_initialize_method(self, container):
        """Test services without initialize method."""

        class SimpleService:
            def __init__(self):
                self.created = True

        container.register_factory(SimpleService, SimpleService)
        service = await container.get(SimpleService)

        assert service.created is True

    @pytest.mark.asyncio
    async def test_service_initialization_failure(self, container):
        """Test handling of service initialization failure."""

        class FailingService:
            async def initialize(self):
                raise RuntimeError("Initialization failed")

        container.register_factory(FailingService, FailingService)

        with pytest.raises(RuntimeError, match="Initialization failed"):
            await container.get(FailingService)

    @pytest.mark.asyncio
    async def test_service_close_failure(self, container):
        """Test handling of service close failure."""

        class FailingCloseService:
            def __init__(self):
                self.initialized = False
                self.close_called = False

            async def initialize(self):
                self.initialized = True

            async def close(self):
                self.close_called = True
                raise RuntimeError("Close failed")

        container.register_factory(FailingCloseService, FailingCloseService)

        # Create service
        service = await container.get(FailingCloseService)
        assert service.initialized is True

        # Close should handle the error gracefully
        await container.close_all()
        assert service.close_called is True
