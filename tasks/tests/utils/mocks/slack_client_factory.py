"""Factory for creating Slack client mocks."""

from unittest.mock import Mock


class SlackClientMockFactory:
    """Factory for creating Slack client mocks."""

    @staticmethod
    def create_basic_client() -> Mock:
        """Create basic Slack client mock with successful empty response.

        Returns:
            Mock: Slack client mock with users_list method configured
        """
        mock_client = Mock()
        mock_client.users_list.return_value = {
            "ok": True,
            "members": [],
            "response_metadata": {},
        }
        return mock_client

    @staticmethod
    def create_client_with_users(users: list) -> Mock:
        """Create Slack client mock with specific users.

        Args:
            users: List of user dictionaries to return

        Returns:
            Mock: Slack client mock configured with specified users
        """
        mock_client = SlackClientMockFactory.create_basic_client()
        mock_client.users_list.return_value["members"] = users
        return mock_client

    @staticmethod
    def create_failing_client(error: str = "API Error") -> Mock:
        """Create Slack client mock that raises an exception.

        Args:
            error: Error message to raise

        Returns:
            Mock: Slack client mock that raises exception on users_list call
        """
        mock_client = Mock()
        mock_client.users_list.side_effect = Exception(error)
        return mock_client
