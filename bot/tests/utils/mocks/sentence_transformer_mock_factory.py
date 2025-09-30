"""
SentenceTransformerMockFactory for test utilities
"""

from unittest.mock import MagicMock


class SentenceTransformerMockFactory:
    """Factory for creating mock Sentence Transformer models"""

    @staticmethod
    def create_mock_model(dimensions: int = 384) -> MagicMock:
        """Create mock Sentence Transformer model"""
        import numpy as np

        model = MagicMock()

        # Mock encode method
        def mock_encode(texts, *args, **kwargs):
            if isinstance(texts, str):
                texts = [texts]
            return np.array([[0.1] * dimensions for _ in texts])

        model.encode.side_effect = mock_encode
        return model

    @staticmethod
    def create_mock_model_with_error(error: Exception) -> MagicMock:
        """Create Sentence Transformer model that raises errors"""
        model = MagicMock()
        model.encode.side_effect = error
        return model
