"""
Service Container for Dependency Injection

Provides centralized service registry with lifecycle management,
proper dependency injection, and graceful resource cleanup.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceContainer:
    """
    Centralized service registry with dependency injection and lifecycle management.

    Features:
    - Singleton pattern for services
    - Lazy initialization
    - Automatic dependency resolution
    - Graceful resource cleanup
    - Thread-safe service creation
    """

    def __init__(self):
        self._services: dict[type, Any] = {}
        self._factories: dict[type, Callable] = {}
        self._initializing: dict[type, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._closed = False

    def register_factory(self, service_type: type[T], factory: Callable[[], T]):
        """
        Register a factory function for service creation.

        Args:
            service_type: The service type/interface to register
            factory: Async callable that creates the service instance

        Example:
            container.register_factory(
                LLMService,
                lambda: LLMService(settings, rag_service, metrics_service)
            )

        """
        if self._closed:
            raise RuntimeError("Cannot register factories on closed container")

        self._factories[service_type] = factory
        logger.debug(f"Registered factory for {service_type.__name__}")

    def register_singleton(self, service_type: type[T], instance: T):
        """
        Register a pre-created service instance.

        Args:
            service_type: The service type/interface
            instance: The service instance

        """
        if self._closed:
            raise RuntimeError("Cannot register services on closed container")

        self._services[service_type] = instance
        logger.debug(f"Registered singleton for {service_type.__name__}")

    async def get(self, service_type: type[T]) -> T:
        """
        Get or create a service instance with thread-safe lazy initialization.

        Args:
            service_type: The service type to retrieve

        Returns:
            The service instance

        Raises:
            ValueError: If no factory is registered for the service type
            RuntimeError: If the container is closed

        """
        if self._closed:
            raise RuntimeError("Cannot get services from closed container")

        # Check if already created
        if service_type in self._services:
            return self._services[service_type]

        # Check if currently being initialized
        async with self._lock:
            if service_type in self._services:
                return self._services[service_type]

            if service_type in self._initializing:
                # Wait for ongoing initialization
                await self._initializing[service_type]
                return self._services[service_type]

            # Start initialization
            if service_type not in self._factories:
                raise ValueError(f"No factory registered for {service_type.__name__}")

            # Create initialization task
            task = asyncio.create_task(self._create_service(service_type))
            self._initializing[service_type] = task

        try:
            service = await task
            self._services[service_type] = service
            logger.info(f"Created service instance: {service_type.__name__}")
            return service
        finally:
            # Clean up initialization tracking
            async with self._lock:
                self._initializing.pop(service_type, None)

    async def _create_service(self, service_type: type[T]) -> T:
        """Internal service creation with proper error handling."""
        try:
            factory = self._factories[service_type]
            service = (
                await factory() if asyncio.iscoroutinefunction(factory) else factory()
            )

            # Initialize service if it has an initialize method
            if hasattr(service, "initialize"):
                if asyncio.iscoroutinefunction(service.initialize):
                    await service.initialize()
                else:
                    service.initialize()

            return service
        except Exception as e:
            logger.error(f"Failed to create service {service_type.__name__}: {e}")
            raise

    async def close_all(self):
        """
        Gracefully close all services in reverse creation order.

        This ensures proper cleanup of dependencies and resources.
        """
        if self._closed:
            return

        self._closed = True
        logger.info("Closing service container...")

        # Cancel any ongoing initializations
        for task in self._initializing.values():
            if not task.done():
                task.cancel()

        # Close services in reverse order
        services_to_close = list(self._services.values())[::-1]

        for service in services_to_close:
            try:
                if hasattr(service, "close"):
                    if asyncio.iscoroutinefunction(service.close):
                        await service.close()
                    else:
                        service.close()
                    logger.debug(f"Closed service: {service.__class__.__name__}")
            except Exception as e:
                logger.error(f"Error closing service {service.__class__.__name__}: {e}")

        self._services.clear()
        self._factories.clear()
        logger.info("Service container closed")

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health checks on all registered services.

        Returns:
            Dict containing health status of all services

        """
        health_status = {
            "container": "healthy",
            "services": {},
            "service_count": len(self._services),
        }

        for service_type, service in self._services.items():
            service_name = service_type.__name__

            try:
                if hasattr(service, "health_check"):
                    if asyncio.iscoroutinefunction(service.health_check):
                        status = await service.health_check()
                    else:
                        status = service.health_check()
                    health_status["services"][service_name] = status
                else:
                    health_status["services"][service_name] = {"status": "unknown"}
            except Exception as e:
                health_status["services"][service_name] = {
                    "status": "error",
                    "error": str(e),
                }

        return health_status

    def list_services(self) -> dict[str, str]:
        """
        List all registered services and their status.

        Returns:
            Dict mapping service names to their status

        """
        result = {}

        for service_type in self._factories:
            name = service_type.__name__
            if service_type in self._services:
                result[name] = "initialized"
            elif service_type in self._initializing:
                result[name] = "initializing"
            else:
                result[name] = "registered"

        return result


# Global container instance
_container: ServiceContainer | None = None


def get_container() -> ServiceContainer:
    """
    Get the global service container instance.

    Returns:
        The global ServiceContainer instance

    """
    global _container  # noqa: PLW0603
    if _container is None:
        _container = ServiceContainer()
    return _container


async def close_container():
    """Close the global service container."""
    global _container  # noqa: PLW0603
    if _container is not None:
        await _container.close_all()
        _container = None
