"""
Bot-specific Langfuse service - imports from centralized shared service.

This module provides a thin wrapper around the shared LangfuseService
for backward compatibility with bot code.
"""

import sys
from pathlib import Path

# Add shared to path for importing centralized service
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import everything from shared langfuse service
from shared.services.langfuse_service import (  # noqa: E402, F401
    LangfuseService,
    LangfuseSettings,
    _langfuse_available,
    get_langfuse_service,
    initialize_langfuse_service,
    langfuse_service,
    observe,
)

# Try to import Langfuse class for tests
try:
    from langfuse import Langfuse  # noqa: F401
except ImportError:
    Langfuse = None  # type: ignore[assignment,misc]

# Re-export for backward compatibility
__all__ = [
    "Langfuse",
    "LangfuseService",
    "LangfuseSettings",
    "_langfuse_available",
    "get_langfuse_service",
    "initialize_langfuse_service",
    "langfuse_service",
    "observe",
]
