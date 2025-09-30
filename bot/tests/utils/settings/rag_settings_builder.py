"""
RAGSettingsBuilder for test utilities
"""

from unittest.mock import MagicMock


class RAGSettingsBuilder:
    """Builder for creating RAG-specific settings configurations"""

    @staticmethod
    def create_rag_settings(
        max_chunks: int = 5,
        similarity_threshold: float = 0.7,
        rerank_enabled: bool = False,
    ) -> MagicMock:
        """Create RAG settings mock"""
        settings = MagicMock()
        settings.max_chunks = max_chunks
        settings.similarity_threshold = similarity_threshold
        settings.rerank_enabled = rerank_enabled
        settings.include_metadata = True
        return settings
