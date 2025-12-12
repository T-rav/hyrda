"""
Langfuse service for LLM observability and tracing.

This module re-exports from the shared library for backward compatibility.
The actual implementation is in shared/services/langfuse_service.py.
"""

# Re-export everything from shared library
from shared.services.langfuse_service import (  # noqa: F401
    LangfuseService,
    _langfuse_available,
    get_langfuse_service,
    initialize_langfuse_service,
    logger,
    observe,
)

# Conditionally re-export Langfuse client class if available
if _langfuse_available:
    from shared.services.langfuse_service import (
        Langfuse,  # noqa: F401  # type: ignore[reportUnusedImport]
    )

    __all__ = [
        "LangfuseService",
        "get_langfuse_service",
        "initialize_langfuse_service",
        "observe",
        "_langfuse_available",
        "logger",
        "Langfuse",
    ]
else:
    __all__ = [
        "LangfuseService",
        "get_langfuse_service",
        "initialize_langfuse_service",
        "observe",
        "_langfuse_available",
        "logger",
    ]
