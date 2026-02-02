"""
Tests for Service Factory

Tests the service factory functionality including service registration,
dependency injection, lifecycle management, and error handling.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config.settings import Settings
from services.container import ServiceContainer
from services.factory import ServiceFactory, create_service_factory
from services.protocols import (
    LangfuseServiceProtocol,
    LLMServiceProtocol,
    MetricsServiceProtocol,
    RAGServiceProtocol,
    SlackServiceProtocol,
    VectorServiceProtocol,
)


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


class TestServiceFactory:
    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock(spec=Settings)
        settings.langfuse = MagicMock()
        settings.langfuse.enabled = True
        settings.vector = MagicMock()
        settings.slack = MagicMock()
        settings.slack.bot_token = MagicMock()
        settings.slack.bot_token.get_secret_value = MagicMock(
            return_value="xoxb-test-token"
        )
        settings.rag_service_url = "http://rag-service:8002"
        return settings

    @pytest.fixture
    async def container(self):
        """Create a fresh container for each test."""
        container = ServiceContainer()
        yield container
        await container.close_all()

    @pytest.fixture
    def factory(self, container, mock_settings):
        return ServiceFactory(container, mock_settings)

    def test_init(self, container, mock_settings):
        factory = ServiceFactory(container, mock_settings)

        assert factory.container is container
        assert factory.settings is mock_settings

    @pytest.mark.asyncio
    async def test_register_all_services_logs_start(self, factory, container, caplog):
        with caplog.at_level(logging.INFO):
            await factory.register_all_services()

        assert "Registering service factories..." in caplog.text
        assert "Service factories registered successfully" in caplog.text

    @pytest.mark.asyncio
    async def test_register_all_services_registers_metrics(self, factory, container):
        await factory.register_all_services()

        assert MetricsServiceProtocol in container._factories

    @pytest.mark.asyncio
    async def test_register_all_services_registers_langfuse_when_enabled(
        self, factory, container, mock_settings
    ):
        mock_settings.langfuse.enabled = True

        await factory.register_all_services()

        assert LangfuseServiceProtocol in container._factories

    @pytest.mark.asyncio
    async def test_register_all_services_skips_langfuse_when_disabled(
        self, factory, container, mock_settings
    ):
        mock_settings.langfuse.enabled = False

        await factory.register_all_services()

        assert LangfuseServiceProtocol not in container._factories

    @pytest.mark.asyncio
    async def test_register_all_services_registers_vector(self, factory, container):
        await factory.register_all_services()

        assert VectorServiceProtocol in container._factories

    @pytest.mark.asyncio
    async def test_register_all_services_registers_rag(self, factory, container):
        await factory.register_all_services()

        assert RAGServiceProtocol in container._factories

    @pytest.mark.asyncio
    async def test_register_all_services_registers_slack(self, factory, container):
        await factory.register_all_services()

        assert SlackServiceProtocol in container._factories

    @pytest.mark.asyncio
    async def test_register_all_services_registers_llm(self, factory, container):
        await factory.register_all_services()

        assert LLMServiceProtocol in container._factories

    @pytest.mark.asyncio
    async def test_create_metrics_service(self, factory):
        with patch("services.metrics_service.MetricsService") as MockMetricsService:
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            MockMetricsService.return_value = mock_service

            service = await factory._create_metrics_service()

            MockMetricsService.assert_called_once_with(factory.settings)
            mock_service.initialize.assert_called_once()
            assert service is mock_service

    @pytest.mark.asyncio
    async def test_create_langfuse_service(self, factory):
        with patch("services.langfuse_service.LangfuseService") as MockLangfuseService:
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            MockLangfuseService.return_value = mock_service

            service = await factory._create_langfuse_service()

            MockLangfuseService.assert_called_once_with(factory.settings.langfuse)
            mock_service.initialize.assert_called_once()
            assert service is mock_service

    @pytest.mark.asyncio
    async def test_create_vector_service(self, factory):
        with patch(
            "services.vector_stores.qdrant_store.QdrantVectorStore"
        ) as MockQdrantVectorStore:
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            MockQdrantVectorStore.return_value = mock_service

            service = await factory._create_vector_service()

            MockQdrantVectorStore.assert_called_once_with(factory.settings.vector)
            mock_service.initialize.assert_called_once()
            assert service is mock_service

    @pytest.mark.asyncio
    async def test_create_rag_service(self, factory):
        with patch("services.rag_client.RAGClient") as MockRAGClient:
            mock_service = AsyncMock()
            MockRAGClient.return_value = mock_service

            service = await factory._create_rag_service()

            # Verify RAGClient was instantiated with base_url
            MockRAGClient.assert_called_once_with(
                base_url=factory.settings.rag_service_url
            )
            assert service is mock_service

    @pytest.mark.asyncio
    async def test_create_slack_service(self, factory, mock_settings):
        pytest.skip("Slack service creation requires slack_sdk package")

    @pytest.mark.asyncio
    async def test_create_llm_service(self, factory):
        with patch("services.llm_service.LLMService") as MockLLMService:
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock()
            MockLLMService.return_value = mock_service

            service = await factory._create_llm_service()

            MockLLMService.assert_called_once_with(settings=factory.settings)
            mock_service.initialize.assert_called_once()
            assert service is mock_service

    @pytest.mark.asyncio
    async def test_get_service_delegates_to_container(self, factory, container):
        mock_service = MockService("test")
        container.register_singleton(MockService, mock_service)

        service = await factory.get_service(MockService)

        assert service is mock_service

    @pytest.mark.asyncio
    async def test_close_all_delegates_to_container(self, factory, container):
        # Register and create a service
        container.register_factory(MockService, lambda: MockService("test"))
        service = await container.get(MockService)

        # Close all
        await factory.close_all()

        # Verify service was closed
        assert service.closed is True
        assert container._closed is True

    @pytest.mark.asyncio
    async def test_health_check_delegates_to_container(self, factory, container):
        # Register and create a service
        container.register_factory(MockService, lambda: MockService("test"))
        await container.get(MockService)

        # Get health check
        health = await factory.health_check()

        assert health["container"] == "healthy"
        assert "MockService" in health["services"]

    @pytest.mark.asyncio
    async def test_service_creation_error_handling(self, factory):
        with (
            patch(
                "services.metrics_service.MetricsService",
                side_effect=RuntimeError("Test error"),
            ),
            pytest.raises(RuntimeError, match="Test error"),
        ):
            await factory._create_metrics_service()

    @pytest.mark.asyncio
    async def test_service_initialization_error_handling(self, factory):
        with patch("services.metrics_service.MetricsService") as MockMetricsService:
            mock_service = AsyncMock()
            mock_service.initialize = AsyncMock(
                side_effect=RuntimeError("Initialization failed")
            )
            MockMetricsService.return_value = mock_service

            with pytest.raises(RuntimeError, match="Initialization failed"):
                await factory._create_metrics_service()


class TestCreateServiceFactory:
    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock(spec=Settings)
        settings.langfuse = MagicMock()
        settings.langfuse.enabled = False  # Disable to avoid complex dependencies
        settings.vector = MagicMock()
        settings.slack = MagicMock()
        settings.slack.bot_token = MagicMock()
        settings.slack.bot_token.get_secret_value = MagicMock(
            return_value="xoxb-test-token"
        )
        return settings

    @pytest.mark.asyncio
    async def test_create_service_factory_returns_factory(self, mock_settings):
        with patch("services.container.get_container") as mock_get_container:
            mock_container = ServiceContainer()
            mock_get_container.return_value = mock_container

            factory = await create_service_factory(mock_settings)

            try:
                assert isinstance(factory, ServiceFactory)
                assert factory.container is mock_container
                assert factory.settings is mock_settings
            finally:
                await factory.close_all()

    @pytest.mark.asyncio
    async def test_create_service_factory_registers_services(self, mock_settings):
        with patch("services.container.get_container") as mock_get_container:
            mock_container = ServiceContainer()
            mock_get_container.return_value = mock_container

            factory = await create_service_factory(mock_settings)

            try:
                # Verify services were registered
                assert MetricsServiceProtocol in mock_container._factories
                assert VectorServiceProtocol in mock_container._factories
                assert RAGServiceProtocol in mock_container._factories
                assert SlackServiceProtocol in mock_container._factories
                assert LLMServiceProtocol in mock_container._factories
            finally:
                await factory.close_all()

    @pytest.mark.asyncio
    async def test_create_service_factory_with_langfuse_enabled(self, mock_settings):
        mock_settings.langfuse.enabled = True

        with patch("services.container.get_container") as mock_get_container:
            mock_container = ServiceContainer()
            mock_get_container.return_value = mock_container

            factory = await create_service_factory(mock_settings)

            try:
                assert LangfuseServiceProtocol in mock_container._factories
            finally:
                await factory.close_all()


class TestServiceFactoryIntegration:
    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock(spec=Settings)
        settings.langfuse = MagicMock()
        settings.langfuse.enabled = False
        settings.vector = MagicMock()
        settings.slack = MagicMock()
        settings.slack.bot_token = MagicMock()
        settings.slack.bot_token.get_secret_value = MagicMock(
            return_value="xoxb-test-token"
        )
        return settings

    @pytest.mark.asyncio
    async def test_full_service_lifecycle(self, mock_settings):
        container = ServiceContainer()
        factory = ServiceFactory(container, mock_settings)

        try:
            # Register services
            await factory.register_all_services()

            # Verify all expected services are registered
            assert MetricsServiceProtocol in container._factories
            assert VectorServiceProtocol in container._factories
            assert RAGServiceProtocol in container._factories
            assert SlackServiceProtocol in container._factories
            assert LLMServiceProtocol in container._factories

            # Verify services list
            services = container.list_services()
            assert "MetricsServiceProtocol" in services
            assert "VectorServiceProtocol" in services
            assert "RAGServiceProtocol" in services
            assert "SlackServiceProtocol" in services
            assert "LLMServiceProtocol" in services

        finally:
            await factory.close_all()
            assert container._closed is True

    @pytest.mark.asyncio
    async def test_service_singleton_behavior(self, mock_settings):
        container = ServiceContainer()
        factory = ServiceFactory(container, mock_settings)

        try:
            # Register a simple service
            def create_mock():
                return MockService("singleton")

            container.register_factory(MockService, create_mock)

            # Get service twice through factory
            service1 = await factory.get_service(MockService)
            service2 = await factory.get_service(MockService)

            # Should be the same instance
            assert service1 is service2

        finally:
            await factory.close_all()

    @pytest.mark.asyncio
    async def test_health_check_integration(self, mock_settings):
        container = ServiceContainer()
        factory = ServiceFactory(container, mock_settings)

        try:
            # Register and create a mock service
            container.register_factory(MockService, lambda: MockService("healthy"))
            await container.get(MockService)

            # Get health check
            health = await factory.health_check()

            assert health["container"] == "healthy"
            assert health["service_count"] == 1
            assert "MockService" in health["services"]
            assert health["services"]["MockService"]["status"] == "healthy"

        finally:
            await factory.close_all()


class TestServiceFactoryErrorHandling:
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock(spec=Settings)
        settings.langfuse = MagicMock()
        settings.langfuse.enabled = False
        settings.vector = MagicMock()
        settings.slack = MagicMock()
        settings.slack.bot_token = MagicMock()
        settings.slack.bot_token.get_secret_value = MagicMock(
            return_value="xoxb-test-token"
        )
        return settings

    @pytest.mark.asyncio
    async def test_missing_settings_attribute(self):
        settings = MagicMock(spec=Settings)
        # Missing langfuse attribute - should raise AttributeError
        del settings.langfuse

        container = ServiceContainer()
        factory = ServiceFactory(container, settings)

        with pytest.raises(AttributeError):
            await factory.register_all_services()

        await container.close_all()

    @pytest.mark.asyncio
    async def test_get_unregistered_service(self, mock_settings):
        container = ServiceContainer()
        factory = ServiceFactory(container, mock_settings)

        try:
            with pytest.raises(ValueError, match="No factory registered"):
                await factory.get_service(MockService)
        finally:
            await factory.close_all()

    @pytest.mark.asyncio
    async def test_service_creation_with_invalid_token(self):
        pytest.skip("Slack service creation requires slack_sdk package")
