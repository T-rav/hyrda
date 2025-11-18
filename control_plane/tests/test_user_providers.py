"""Unit tests for user provider implementations."""

import pytest
from unittest.mock import MagicMock, patch

from services.user_providers import (
    SlackUserProvider,
    GoogleWorkspaceProvider,
    get_user_provider,
)


class TestSlackUserProvider:
    """Test Slack user provider implementation."""

    @pytest.fixture
    def mock_slack_client(self):
        """Mock Slack WebClient."""
        with patch("services.user_providers.WebClient") as mock:
            yield mock

    @pytest.fixture
    def provider(self, mock_slack_client):
        """Create SlackUserProvider with mocked client."""
        return SlackUserProvider(bot_token="xoxb-test-token")

    @pytest.fixture
    def sample_slack_users(self):
        """Sample Slack user data."""
        return [
            {
                "id": "U123",
                "profile": {
                    "email": "alice@example.com",
                    "real_name": "Alice Smith",
                    "display_name": "alice",
                },
                "is_bot": False,
                "deleted": False,
            },
            {
                "id": "U456",
                "profile": {
                    "email": "bob@example.com",
                    "real_name": "Bob Jones",
                    "display_name": "bob",
                },
                "is_bot": False,
                "deleted": False,
            },
            {
                "id": "B789",
                "profile": {
                    "email": "",
                    "real_name": "Test Bot",
                    "display_name": "testbot",
                },
                "is_bot": True,
                "deleted": False,
            },
            {
                "id": "U999",
                "profile": {
                    "email": "deleted@example.com",
                    "real_name": "Deleted User",
                    "display_name": "deleted",
                },
                "is_bot": False,
                "deleted": True,
            },
        ]

    def test_fetch_users(self, provider, sample_slack_users):
        """Test fetching users from Slack API."""
        provider.client.users_list = MagicMock(
            return_value={"members": sample_slack_users}
        )

        users = provider.fetch_users()

        assert len(users) == 4
        assert users == sample_slack_users
        provider.client.users_list.assert_called_once()

    def test_fetch_users_empty(self, provider):
        """Test fetching users returns empty list when no users."""
        provider.client.users_list = MagicMock(return_value={"members": []})

        users = provider.fetch_users()

        assert users == []

    def test_get_user_id(self, provider, sample_slack_users):
        """Test extracting user ID."""
        user = sample_slack_users[0]
        assert provider.get_user_id(user) == "U123"

    def test_get_user_email(self, provider, sample_slack_users):
        """Test extracting user email."""
        user = sample_slack_users[0]
        assert provider.get_user_email(user) == "alice@example.com"

    def test_get_user_email_missing(self, provider):
        """Test extracting email when missing."""
        user = {"id": "U123", "profile": {}}
        assert provider.get_user_email(user) == ""

    def test_get_user_name(self, provider, sample_slack_users):
        """Test extracting user name."""
        user = sample_slack_users[0]
        assert provider.get_user_name(user) == "Alice Smith"

    def test_get_user_name_fallback_to_display(self, provider):
        """Test falling back to display_name when real_name missing."""
        user = {
            "id": "U123",
            "profile": {"display_name": "alice", "real_name": ""},
        }
        assert provider.get_user_name(user) == "alice"

    def test_get_user_name_fallback_to_unknown(self, provider):
        """Test falling back to Unknown when both names missing."""
        user = {"id": "U123", "profile": {}}
        assert provider.get_user_name(user) == "Unknown"

    def test_is_bot_true(self, provider, sample_slack_users):
        """Test identifying bot users."""
        bot_user = sample_slack_users[2]
        assert provider.is_bot(bot_user) is True

    def test_is_bot_false(self, provider, sample_slack_users):
        """Test identifying non-bot users."""
        user = sample_slack_users[0]
        assert provider.is_bot(user) is False

    def test_is_bot_missing_field(self, provider):
        """Test is_bot when field is missing."""
        user = {"id": "U123", "profile": {}}
        assert provider.is_bot(user) is False

    def test_is_deleted_true(self, provider, sample_slack_users):
        """Test identifying deleted users."""
        deleted_user = sample_slack_users[3]
        assert provider.is_deleted(deleted_user) is True

    def test_is_deleted_false(self, provider, sample_slack_users):
        """Test identifying active users."""
        user = sample_slack_users[0]
        assert provider.is_deleted(user) is False

    def test_is_deleted_missing_field(self, provider):
        """Test is_deleted when field is missing."""
        user = {"id": "U123", "profile": {}}
        assert provider.is_deleted(user) is False


class TestGoogleWorkspaceProvider:
    """Test Google Workspace provider implementation."""

    def test_not_implemented(self):
        """Test that GoogleWorkspaceProvider raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Google Workspace provider not yet implemented"):
            GoogleWorkspaceProvider(credentials=None)


class TestProviderFactory:
    """Test provider factory function."""

    @patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-test-token"})
    @patch("services.user_providers.WebClient")
    def test_get_slack_provider_default(self, mock_client):
        """Test getting Slack provider as default."""
        provider = get_user_provider()

        assert isinstance(provider, SlackUserProvider)
        mock_client.assert_called_once_with(token="xoxb-test-token")

    @patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-test-token"})
    @patch("services.user_providers.WebClient")
    def test_get_slack_provider_explicit(self, mock_client):
        """Test explicitly requesting Slack provider."""
        provider = get_user_provider("slack")

        assert isinstance(provider, SlackUserProvider)

    @patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-test-token", "USER_MANAGEMENT_PROVIDER": "slack"})
    @patch("services.user_providers.WebClient")
    def test_get_slack_provider_from_env(self, mock_client):
        """Test getting Slack provider from environment variable."""
        provider = get_user_provider()

        assert isinstance(provider, SlackUserProvider)

    @patch.dict("os.environ", {}, clear=True)
    def test_get_slack_provider_missing_token(self):
        """Test error when SLACK_BOT_TOKEN is missing."""
        with pytest.raises(ValueError, match="SLACK_BOT_TOKEN environment variable required"):
            get_user_provider("slack")

    def test_get_google_provider_not_implemented(self):
        """Test that requesting Google provider raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            get_user_provider("google")

    def test_get_unknown_provider(self):
        """Test error when requesting unknown provider."""
        with pytest.raises(ValueError, match="Unknown provider type: unknown"):
            get_user_provider("unknown")


class TestProviderInterface:
    """Test that all providers implement the required interface."""

    @patch("services.user_providers.WebClient")
    def test_slack_provider_implements_interface(self, mock_client):
        """Test that SlackUserProvider implements all required methods."""
        provider = SlackUserProvider(bot_token="xoxb-test")

        # Check all required methods exist
        assert hasattr(provider, "fetch_users")
        assert hasattr(provider, "get_user_id")
        assert hasattr(provider, "get_user_email")
        assert hasattr(provider, "get_user_name")
        assert hasattr(provider, "is_bot")
        assert hasattr(provider, "is_deleted")

        # Check methods are callable
        assert callable(provider.fetch_users)
        assert callable(provider.get_user_id)
        assert callable(provider.get_user_email)
        assert callable(provider.get_user_name)
        assert callable(provider.is_bot)
        assert callable(provider.is_deleted)
