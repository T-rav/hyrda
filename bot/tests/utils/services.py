"""
Service factory patterns for test services

Provides factories for creating various service objects and mocks used across tests.
Consolidates duplicate factory patterns from multiple test files.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import WebClient


class SlackClientFactory:
    """Factory for creating mock Slack clients"""

    @staticmethod
    def create_basic_client() -> AsyncMock:
        """Create basic mock Slack client"""
        return AsyncMock(spec=WebClient)

    @staticmethod
    def create_client_with_success_response(
        response: dict[str, Any] | None = None,
    ) -> AsyncMock:
        """Create mock client that returns successful responses"""
        client = SlackClientFactory.create_basic_client()
        default_response = {"ts": "1234567890.654321"}
        client.chat_postMessage = AsyncMock(return_value=response or default_response)
        return client

    @staticmethod
    def create_client_with_error(
        error: Exception | None = None,
    ) -> AsyncMock:
        """Create mock client that raises errors"""
        client = SlackClientFactory.create_basic_client()
        default_error = SlackApiError(
            message="Error", response={"error": "channel_not_found"}
        )
        client.chat_postMessage.side_effect = error or default_error
        return client

    @staticmethod
    def create_client_with_thread_history(
        messages: list[dict[str, Any]] | None = None,
    ) -> AsyncMock:
        """Create mock client with thread history responses"""
        client = SlackClientFactory.create_basic_client()
        default_messages = [
            {"text": "Hello", "user": "U12345", "ts": "1234567890.123456"},
            {"text": "Hi there!", "user": "B12345678", "ts": "1234567890.234567"},
        ]
        client.conversations_replies = AsyncMock(
            return_value={"messages": messages or default_messages}
        )
        return client

    @staticmethod
    def create_client_with_auth_test(
        user_id: str = "B12345678",
        bot_id: str = "B08RGGA6QKS",
    ) -> AsyncMock:
        """Create mock client with auth test response"""
        client = SlackClientFactory.create_basic_client()
        client.auth_test = AsyncMock(
            return_value={"user_id": user_id, "bot_id": bot_id}
        )
        return client


class SlackServiceFactory:
    """Factory for creating SlackService instances"""

    @staticmethod
    def create_mock_service() -> MagicMock:
        """Create basic mock Slack service"""
        service = MagicMock()
        service.send_message = AsyncMock(return_value=True)
        service.get_thread_context = AsyncMock(return_value=None)
        service.client = SlackClientFactory.create_basic_client()
        return service

    @staticmethod
    def create_service_with_thread_support() -> MagicMock:
        """Create Slack service mock with thread support"""
        service = SlackServiceFactory.create_mock_service()
        service.get_thread_context = AsyncMock(
            return_value={"messages": [], "participant_count": 0}
        )
        return service


class LLMServiceFactory:
    """Factory for creating LLM service mocks"""

    @staticmethod
    def create_mock_service(response: str = "Test response") -> MagicMock:
        """Create basic mock LLM service"""
        service = MagicMock()
        service.get_response = AsyncMock(return_value=response)
        service.initialize = AsyncMock()
        service.close = AsyncMock()
        return service

    @staticmethod
    def create_service_with_rag(response: str = "RAG response") -> MagicMock:
        """Create LLM service mock with RAG enabled"""
        service = LLMServiceFactory.create_mock_service(response)
        service.rag_service = MagicMock()
        service.rag_service.generate_response = AsyncMock(return_value=response)
        return service


class RAGServiceFactory:
    """Factory for creating RAG service mocks"""

    @staticmethod
    def create_service_with_response(response: str) -> MagicMock:
        """Create RAG service that returns specified response"""
        service = MagicMock()
        service.generate_response = AsyncMock(return_value=response)
        return service

    @staticmethod
    def create_service_with_error(error: Exception) -> MagicMock:
        """Create RAG service that raises errors"""
        service = MagicMock()
        service.generate_response = AsyncMock(side_effect=error)
        return service


class ConversationCacheFactory:
    """Factory for creating conversation cache mocks"""

    @staticmethod
    def create_enabled_cache() -> MagicMock:
        """Create enabled conversation cache mock"""
        cache = MagicMock()
        cache.is_enabled = True
        cache.get_conversation = AsyncMock(return_value=[])
        cache.add_message = AsyncMock()
        cache.clear_conversation = AsyncMock()
        return cache

    @staticmethod
    def create_disabled_cache() -> MagicMock:
        """Create disabled conversation cache mock"""
        cache = MagicMock()
        cache.is_enabled = False
        cache.get_conversation = AsyncMock(return_value=[])
        return cache

    @staticmethod
    def create_cache_with_history(messages: list[dict[str, str]]) -> MagicMock:
        """Create cache with pre-populated conversation history"""
        cache = ConversationCacheFactory.create_enabled_cache()
        cache.get_conversation = AsyncMock(return_value=messages)
        return cache


class RetrievalServiceFactory:
    """Factory for creating retrieval service mocks"""

    @staticmethod
    def create_mock_service() -> MagicMock:
        """Create basic mock retrieval service"""
        service = MagicMock()
        service.search = AsyncMock(return_value=[])
        service.initialize = AsyncMock()
        service.close = AsyncMock()
        return service

    @staticmethod
    def create_service_with_results(results: list) -> MagicMock:
        """Create retrieval service that returns specific results"""
        service = RetrievalServiceFactory.create_mock_service()
        service.search = AsyncMock(return_value=results)
        return service


class EmbeddingServiceFactory:
    """Factory for creating embedding service mocks"""

    @staticmethod
    def create_mock_service(embeddings: list[list[float]] | None = None) -> MagicMock:
        """Create basic mock embedding service"""
        service = MagicMock()
        default_embeddings = [[0.1] * 1536]
        service.get_embeddings = AsyncMock(
            return_value=embeddings or default_embeddings
        )
        service.get_embedding = AsyncMock(
            return_value=(embeddings or default_embeddings)[0]
        )
        service.close = AsyncMock()
        return service

    @staticmethod
    def create_service_with_dimension(dimensions: int = 1536) -> MagicMock:
        """Create embedding service with specific dimension size"""
        return EmbeddingServiceFactory.create_mock_service([[0.1] * dimensions])


class VectorServiceFactory:
    """Factory for creating vector service mocks"""

    @staticmethod
    def create_mock_service() -> MagicMock:
        """Create basic mock vector service"""
        service = MagicMock()
        service.search = AsyncMock(return_value=[])
        service.add_documents = AsyncMock(return_value=True)
        service.delete_documents = AsyncMock(return_value=True)
        service.initialize = AsyncMock()
        service.close = AsyncMock()
        return service

    @staticmethod
    def create_service_with_results(results: list) -> MagicMock:
        """Create vector service that returns specific search results"""
        service = VectorServiceFactory.create_mock_service()
        service.search = AsyncMock(return_value=results)
        return service


class LangfuseServiceFactory:
    """Factory for creating Langfuse service mocks"""

    @staticmethod
    def create_mock_service() -> MagicMock:
        """Create basic mock Langfuse service"""
        service = MagicMock()
        service.trace_conversation = MagicMock()
        service.trace_llm_call = MagicMock()
        service.get_prompt = MagicMock(return_value=None)
        return service

    @staticmethod
    def create_service_with_prompt(prompt: str) -> MagicMock:
        """Create Langfuse service that returns a specific prompt"""
        service = LangfuseServiceFactory.create_mock_service()
        prompt_obj = MagicMock()
        prompt_obj.compile.return_value = prompt
        service.get_prompt = MagicMock(return_value=prompt_obj)
        return service
