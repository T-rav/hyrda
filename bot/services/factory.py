"""
Service Factory with Dependency Injection

Centralized factory for creating services with proper dependency injection
and lifecycle management using the service container.
"""

import logging
from typing import TypeVar

from config.settings import Settings
from services.container import ServiceContainer
from services.protocols import (
    LangfuseServiceProtocol,
    LLMServiceProtocol,
    MetricsServiceProtocol,
    RAGServiceProtocol,
    SlackServiceProtocol,
    VectorServiceProtocol,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceFactory:
    """
    Factory for creating services with proper dependency injection.

    This factory uses the service container to manage dependencies
    and ensure proper service lifecycle.
    """

    def __init__(self, container: ServiceContainer, settings: Settings):
        self.container = container
        self.settings = settings

    async def register_all_services(self) -> None:
        """
        Register all service factories with the container.

        This sets up the dependency graph for the entire application.
        """
        logger.info("Registering service factories...")

        # Register core services first (no dependencies)
        self.container.register_factory(
            MetricsServiceProtocol, self._create_metrics_service
        )

        # Register services with simple dependencies
        if self.settings.langfuse.enabled:
            self.container.register_factory(
                LangfuseServiceProtocol, self._create_langfuse_service
            )

        # Register vector services
        self.container.register_factory(
            VectorServiceProtocol, self._create_vector_service
        )

        # Register RAG service (depends on vector service)
        self.container.register_factory(RAGServiceProtocol, self._create_rag_service)

        # Register Slack service
        self.container.register_factory(
            SlackServiceProtocol, self._create_slack_service
        )

        # Register LLM service (depends on RAG, Langfuse, Metrics)
        self.container.register_factory(LLMServiceProtocol, self._create_llm_service)

        logger.info("Service factories registered successfully")

    async def _create_metrics_service(self):  # type: ignore[no-untyped-def]
        """Create metrics service."""
        from services.metrics_service import MetricsService

        service = MetricsService(self.settings)
        await service.initialize()
        return service

    async def _create_langfuse_service(self):  # type: ignore[no-untyped-def]
        """Create Langfuse service."""
        from services.langfuse_service import LangfuseService

        service = LangfuseService(self.settings.langfuse)
        await service.initialize()
        return service

    async def _create_vector_service(self):  # type: ignore[no-untyped-def]
        """Create Qdrant vector service."""
        from services.vector_stores.qdrant_store import QdrantVectorStore

        service = QdrantVectorStore(self.settings.vector)
        await service.initialize()
        return service

    async def _create_rag_service(self):  # type: ignore[no-untyped-def]
        """Create RAG service HTTP client."""
        from services.rag_client import RAGClient

        # Use standalone rag-service via HTTP (no initialization needed)
        service = RAGClient(base_url=self.settings.rag_service_url)
        return service

    async def _create_slack_service(self):  # type: ignore[no-untyped-def]
        """Create Slack service."""
        from slack_sdk import WebClient

        from services.slack_service import SlackService

        # Create Slack client
        client = WebClient(token=self.settings.slack.bot_token.get_secret_value())

        service = SlackService(settings=self.settings.slack, client=client)
        await service.initialize()
        return service

    async def _create_llm_service(self):  # type: ignore[no-untyped-def]
        """Create LLM service with all dependencies."""
        # Import and create service
        from services.llm_service import LLMService

        service = LLMService(settings=self.settings)
        await service.initialize()
        return service

    async def get_service(self, service_type: type[T]) -> T:
        """
        Get a service instance from the container.

        Args:
            service_type: Service protocol/interface type

        Returns:
            Service instance

        """
        return await self.container.get(service_type)

    async def close_all(self) -> None:
        """Close all services and the container."""
        await self.container.close_all()

    async def health_check(self) -> dict:
        """Get health status of all services."""
        return await self.container.health_check()


async def create_service_factory(settings: Settings) -> ServiceFactory:
    """
    Create and initialize a service factory.

    Args:
        settings: Application settings

    Returns:
        Initialized service factory

    """
    from services.container import get_container

    container = get_container()
    factory = ServiceFactory(container, settings)
    await factory.register_all_services()

    return factory
