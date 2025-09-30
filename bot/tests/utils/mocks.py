"""
Mock factory patterns for test doubles

Provides factories for creating mock objects, stubs, and test doubles.
Used for isolating units under test.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock


class MockVectorStoreFactory:
    """Factory for creating mock vector store objects"""

    @staticmethod
    def create_basic_store() -> MagicMock:
        """Create basic mock vector store"""
        store = MagicMock()
        store.search = AsyncMock(return_value=[])
        store.add_documents = AsyncMock(return_value=True)
        store.delete_documents = AsyncMock(return_value=True)
        store.initialize = AsyncMock()
        store.close = AsyncMock()
        return store

    @staticmethod
    def create_store_with_results(results: list[dict[str, Any]]) -> MagicMock:
        """Create vector store that returns specific results"""
        store = MockVectorStoreFactory.create_basic_store()
        store.search = AsyncMock(return_value=results)
        return store

    @staticmethod
    def create_store_with_error(error: Exception) -> MagicMock:
        """Create vector store that raises errors"""
        store = MockVectorStoreFactory.create_basic_store()
        store.search = AsyncMock(side_effect=error)
        return store


class ClientMockFactory:
    """Factory for creating mock API clients"""

    @staticmethod
    def create_openai_client() -> MagicMock:
        """Create mock OpenAI client"""
        client = MagicMock()

        # Mock embeddings
        embeddings_response = MagicMock()
        embeddings_response.data = [MagicMock(embedding=[0.1] * 1536)]
        client.embeddings.create = AsyncMock(return_value=embeddings_response)

        # Mock chat completions
        completion_response = MagicMock()
        completion_response.choices = [
            MagicMock(message=MagicMock(content="Test response"))
        ]
        completion_response.usage = MagicMock(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )
        client.chat.completions.create = AsyncMock(return_value=completion_response)

        # Mock close
        client.close = AsyncMock()

        return client

    @staticmethod
    def create_openai_client_with_error(error: Exception) -> MagicMock:
        """Create OpenAI client that raises errors"""
        client = ClientMockFactory.create_openai_client()
        client.chat.completions.create = AsyncMock(side_effect=error)
        client.embeddings.create = AsyncMock(side_effect=error)
        return client

    @staticmethod
    def create_anthropic_client() -> MagicMock:
        """Create mock Anthropic client"""
        client = MagicMock()

        # Mock messages
        message_response = MagicMock()
        message_response.content = [MagicMock(text="Test response")]
        message_response.usage = MagicMock(
            input_tokens=10,
            output_tokens=20,
        )
        client.messages.create = AsyncMock(return_value=message_response)

        return client


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


class HTTPResponseFactory:
    """Factory for creating mock HTTP responses"""

    @staticmethod
    def create_success_response(
        status_code: int = 200,
        content: bytes = b"Success",
        headers: dict[str, str] | None = None,
    ) -> MagicMock:
        """Create successful HTTP response"""
        response = MagicMock()
        response.status_code = status_code
        response.content = content
        response.headers = headers or {}
        response.text = content.decode("utf-8")
        response.json = MagicMock(return_value={})
        response.raise_for_status = MagicMock()
        return response

    @staticmethod
    def create_error_response(
        status_code: int = 404,
        content: bytes = b"Not Found",
    ) -> MagicMock:
        """Create error HTTP response"""
        response = HTTPResponseFactory.create_success_response(status_code, content)
        response.raise_for_status = MagicMock(
            side_effect=Exception(f"HTTP {status_code}")
        )
        return response

    @staticmethod
    def create_json_response(data: dict[str, Any], status_code: int = 200) -> MagicMock:
        """Create HTTP response with JSON data"""
        import json

        content = json.dumps(data).encode("utf-8")
        response = HTTPResponseFactory.create_success_response(status_code, content)
        response.json = MagicMock(return_value=data)
        return response


class LLMProviderMockFactory:
    """Factory for creating mock LLM provider objects"""

    @staticmethod
    def create_mock_provider(response: str = "Test response") -> MagicMock:
        """Create basic mock LLM provider"""
        provider = MagicMock()
        provider.get_response = AsyncMock(return_value=response)
        provider.close = AsyncMock()
        provider.model = "test-model"
        provider.temperature = 0.7
        provider.max_tokens = 2000
        return provider

    @staticmethod
    def create_provider_with_error(error: Exception) -> MagicMock:
        """Create LLM provider that raises errors"""
        provider = LLMProviderMockFactory.create_mock_provider()
        provider.get_response = AsyncMock(side_effect=error)
        return provider


class EmbeddingProviderMockFactory:
    """Factory for creating mock embedding provider objects"""

    @staticmethod
    def create_mock_provider(
        embeddings: list[list[float]] | None = None,
        dimensions: int = 1536,
    ) -> MagicMock:
        """Create basic mock embedding provider"""
        provider = MagicMock()

        if embeddings is None:
            embeddings = [[0.1] * dimensions]

        provider.get_embeddings = AsyncMock(return_value=embeddings)
        provider.get_embedding = AsyncMock(return_value=embeddings[0])
        provider.close = AsyncMock()
        provider.model = "test-embedding-model"

        return provider

    @staticmethod
    def create_provider_with_error(error: Exception) -> MagicMock:
        """Create embedding provider that raises errors"""
        provider = EmbeddingProviderMockFactory.create_mock_provider()
        provider.get_embeddings = AsyncMock(side_effect=error)
        provider.get_embedding = AsyncMock(side_effect=error)
        return provider


class PrometheusDataFactory:
    """Factory for creating Prometheus metric data"""

    @staticmethod
    def create_counter_data(
        name: str = "test_counter", value: float = 10.0
    ) -> dict[str, Any]:
        """Create Prometheus counter data"""
        return {
            "name": name,
            "type": "counter",
            "help": f"Test counter {name}",
            "samples": [{"value": value, "labels": {}}],
        }

    @staticmethod
    def create_gauge_data(
        name: str = "test_gauge", value: float = 5.0
    ) -> dict[str, Any]:
        """Create Prometheus gauge data"""
        return {
            "name": name,
            "type": "gauge",
            "help": f"Test gauge {name}",
            "samples": [{"value": value, "labels": {}}],
        }

    @staticmethod
    def create_histogram_data(
        name: str = "test_histogram",
        buckets: list[tuple[float, int]] | None = None,
    ) -> dict[str, Any]:
        """Create Prometheus histogram data"""
        if buckets is None:
            buckets = [(0.1, 5), (0.5, 10), (1.0, 15)]

        samples = [
            {"value": count, "labels": {"le": str(bucket)}} for bucket, count in buckets
        ]
        samples.append({"value": sum(c for _, c in buckets), "labels": {"le": "+Inf"}})

        return {
            "name": name,
            "type": "histogram",
            "help": f"Test histogram {name}",
            "samples": samples,
        }
