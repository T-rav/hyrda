"""
Base Service Class

Provides common functionality for all services including logging,
initialization patterns, health checks, and resource management.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any


class BaseService(ABC):
    """
    Abstract base class for all services with common functionality.

    Features:
    - Consistent logging setup
    - Initialization lifecycle management
    - Health check interface
    - Resource cleanup patterns
    - Error handling helpers
    """

    def __init__(self, service_name: str | None = None):
        """
        Initialize base service.

        Args:
            service_name: Optional service name override for logging
        """
        self._service_name = service_name or self.__class__.__name__
        self.logger = logging.getLogger(self.__class__.__module__)
        self._initialized = False
        self._closed = False
        self._initialization_lock = asyncio.Lock()

    @property
    def service_name(self) -> str:
        """Get the service name."""
        return self._service_name

    @property
    def is_initialized(self) -> bool:
        """Check if the service is initialized."""
        return self._initialized

    @property
    def is_closed(self) -> bool:
        """Check if the service is closed."""
        return self._closed

    async def initialize(self) -> None:
        """
        Initialize the service with thread-safe lazy initialization.

        This method can be called multiple times safely.
        """
        if self._initialized or self._closed:
            return

        async with self._initialization_lock:
            if self._initialized or self._closed:
                return

            try:
                self.logger.info(f"Initializing {self._service_name}...")
                await self._initialize()
                self._initialized = True
                self.logger.info(f"{self._service_name} initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize {self._service_name}: {e}")
                raise

    @abstractmethod
    async def _initialize(self) -> None:
        """
        Service-specific initialization logic.

        Override this method in subclasses to implement initialization.
        """
        pass

    async def close(self) -> None:
        """
        Close the service and clean up resources.

        This method can be called multiple times safely.
        """
        if self._closed:
            return

        self.logger.info(f"Closing {self._service_name}...")
        try:
            await self._close()
            self.logger.info(f"{self._service_name} closed successfully")
        except Exception as e:
            self.logger.error(f"Error closing {self._service_name}: {e}")
            raise
        finally:
            # Always mark as closed, even if cleanup failed
            self._closed = True

    async def _close(self) -> None:  # noqa: B027
        """
        Service-specific cleanup logic.

        Override this method in subclasses to implement cleanup.
        Default implementation does nothing.
        """
        # Default implementation - subclasses can override

    def health_check(self) -> dict[str, Any]:
        """
        Perform a health check on the service.

        Returns:
            Dict containing health status information

        Override this method in subclasses for service-specific health checks.
        """
        status = "healthy" if self._initialized and not self._closed else "unhealthy"

        return {
            "status": status,
            "service": self._service_name,
            "initialized": self._initialized,
            "closed": self._closed,
        }

    async def ensure_initialized(self) -> None:
        """
        Ensure the service is initialized, initializing if necessary.

        Raises:
            RuntimeError: If the service is closed
        """
        if self._closed:
            raise RuntimeError(f"Service {self._service_name} is closed")

        if not self._initialized:
            await self.initialize()

    def _log_operation(self, operation: str, **metadata) -> None:
        """
        Log an operation with consistent formatting.

        Args:
            operation: Operation name
            **metadata: Additional metadata to log
        """
        self.logger.info(
            f"{self._service_name} - {operation}",
            extra={"service": self._service_name, "operation": operation, **metadata},
        )

    def _log_error(self, operation: str, error: Exception, **metadata) -> None:
        """
        Log an error with consistent formatting.

        Args:
            operation: Operation that failed
            error: Exception that occurred
            **metadata: Additional metadata to log
        """
        self.logger.error(
            f"{self._service_name} - {operation} failed: {error}",
            extra={
                "service": self._service_name,
                "operation": operation,
                "error_type": type(error).__name__,
                "error_message": str(error),
                **metadata,
            },
        )

    async def __aenter__(self):
        """Async context manager entry."""
        await self.ensure_initialized()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def __repr__(self) -> str:
        """String representation of the service."""
        return (
            f"{self.__class__.__name__}("
            f"name={self._service_name}, "
            f"initialized={self._initialized}, "
            f"closed={self._closed})"
        )


class ManagedService(BaseService):
    """
    Base class for services that need automatic lifecycle management.

    This class provides additional functionality for services that need
    to be managed by the service container.
    """

    def __init__(self, service_name: str | None = None):
        super().__init__(service_name)
        self._dependencies: dict[str, Any] = {}

    def add_dependency(self, name: str, service: Any) -> None:
        """
        Add a dependency to this service.

        Args:
            name: Dependency name
            service: Service instance
        """
        self._dependencies[name] = service

    def get_dependency(self, name: str) -> Any:
        """
        Get a dependency by name.

        Args:
            name: Dependency name

        Returns:
            Service instance

        Raises:
            KeyError: If dependency is not found
        """
        if name not in self._dependencies:
            raise KeyError(f"Dependency '{name}' not found in {self._service_name}")
        return self._dependencies[name]

    async def _close(self) -> None:
        """Close managed service and dependencies."""
        # Close dependencies in reverse order
        for name, service in reversed(list(self._dependencies.items())):
            try:
                if hasattr(service, "close") and callable(service.close):
                    if asyncio.iscoroutinefunction(service.close):
                        await service.close()
                    else:
                        service.close()
                    self.logger.debug(f"Closed dependency: {name}")
            except Exception as e:
                self.logger.error(f"Error closing dependency {name}: {e}")

        await super()._close()

    def health_check(self) -> dict[str, Any]:
        """Health check including dependencies."""
        health = super().health_check()
        health["dependencies"] = {}

        for name, service in self._dependencies.items():
            try:
                if hasattr(service, "health_check") and callable(service.health_check):
                    dep_health = service.health_check()
                    health["dependencies"][name] = dep_health
                else:
                    health["dependencies"][name] = {"status": "unknown"}
            except Exception as e:
                health["dependencies"][name] = {"status": "error", "error": str(e)}

        return health
