"""
Title Injection Service for Enhanced RAG

DEPRECATED: This module is maintained for backward compatibility.
Please import from services.chunking instead:
    from services.chunking import TitleInjectionService, EnhancedChunkProcessor
"""

# Backward compatibility imports
from services.chunking import EnhancedChunkProcessor, TitleInjectionService

__all__ = [
    "TitleInjectionService",
    "EnhancedChunkProcessor",
]
