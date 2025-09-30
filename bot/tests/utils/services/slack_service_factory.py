"""
SlackServiceFactory for test utilities
"""

from unittest.mock import AsyncMock, MagicMock


class SlackServiceFactory:
    """Factory for creating SlackService instances"""

    @staticmethod
    def create_mock_service() -> MagicMock:
        """Create basic mock Slack service"""
        service = MagicMock()
        service.send_message = AsyncMock(return_value=True)
        service.get_thread_context = AsyncMock(return_value=None)
        from .slack_client_factory import SlackClientFactory

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
