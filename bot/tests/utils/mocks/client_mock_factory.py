"""
ClientMockFactory for test utilities
"""

from unittest.mock import AsyncMock, MagicMock


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
