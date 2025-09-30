"""
SlackClientFactory for test utilities
"""

from typing import Any
from unittest.mock import AsyncMock

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient


class SlackClientFactory:
    """Factory for creating mock Slack clients"""

    @staticmethod
    def create_basic_client() -> AsyncMock:
        """Create basic mock Slack client"""
        return AsyncMock(spec=AsyncWebClient)

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
