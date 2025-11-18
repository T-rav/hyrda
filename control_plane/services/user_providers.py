"""User provider abstraction for pluggable identity management.

Supports multiple identity providers (Slack, Google Workspace, etc.) through
a common interface. Provider selection is configured via USER_MANAGEMENT_PROVIDER
environment variable.
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from slack_sdk import WebClient


class UserProvider(ABC):
    """Abstract base class for user identity providers."""

    @abstractmethod
    def fetch_users(self) -> List[Dict[str, Any]]:
        """Fetch all users from the provider.

        Returns:
            List of user dictionaries from the provider
        """
        pass

    @abstractmethod
    def get_user_id(self, user: Dict[str, Any]) -> str:
        """Extract unique user ID from provider user object.

        Args:
            user: User dictionary from the provider

        Returns:
            Unique user identifier
        """
        pass

    @abstractmethod
    def get_user_email(self, user: Dict[str, Any]) -> str:
        """Extract email address from provider user object.

        Args:
            user: User dictionary from the provider

        Returns:
            User's email address
        """
        pass

    @abstractmethod
    def get_user_name(self, user: Dict[str, Any]) -> str:
        """Extract full name from provider user object.

        Args:
            user: User dictionary from the provider

        Returns:
            User's full name
        """
        pass

    @abstractmethod
    def is_bot(self, user: Dict[str, Any]) -> bool:
        """Check if user is a bot/service account.

        Args:
            user: User dictionary from the provider

        Returns:
            True if user is a bot/service account
        """
        pass

    @abstractmethod
    def is_deleted(self, user: Dict[str, Any]) -> bool:
        """Check if user is deleted/deactivated.

        Args:
            user: User dictionary from the provider

        Returns:
            True if user is deleted/deactivated
        """
        pass


class SlackUserProvider(UserProvider):
    """Slack user provider implementation."""

    def __init__(self, bot_token: str) -> None:
        """Initialize Slack provider.

        Args:
            bot_token: Slack bot token for API access
        """
        self.client = WebClient(token=bot_token)

    def fetch_users(self) -> List[Dict[str, Any]]:
        """Fetch all users from Slack workspace.

        Returns:
            List of Slack user objects
        """
        response = self.client.users_list()
        return response.get("members", [])

    def get_user_id(self, user: Dict[str, Any]) -> str:
        """Get Slack user ID.

        Args:
            user: Slack user object

        Returns:
            Slack user ID
        """
        return user["id"]

    def get_user_email(self, user: Dict[str, Any]) -> str:
        """Get email from Slack user profile.

        Args:
            user: Slack user object

        Returns:
            User's email address
        """
        return user.get("profile", {}).get("email", "")

    def get_user_name(self, user: Dict[str, Any]) -> str:
        """Get full name from Slack user profile.

        Args:
            user: Slack user object

        Returns:
            User's full name
        """
        profile = user.get("profile", {})
        return profile.get("real_name", profile.get("display_name", "Unknown"))

    def is_bot(self, user: Dict[str, Any]) -> bool:
        """Check if Slack user is a bot.

        Args:
            user: Slack user object

        Returns:
            True if user is a bot
        """
        return user.get("is_bot", False)

    def is_deleted(self, user: Dict[str, Any]) -> bool:
        """Check if Slack user is deleted.

        Args:
            user: Slack user object

        Returns:
            True if user is deleted
        """
        return user.get("deleted", False)


class GoogleWorkspaceProvider(UserProvider):
    """Google Workspace user provider implementation.

    Note: This is a stub implementation. Full implementation requires:
    - Google Admin SDK setup
    - Service account credentials
    - Domain-wide delegation
    """

    def __init__(self, credentials: Any = None) -> None:
        """Initialize Google Workspace provider.

        Args:
            credentials: Google service account credentials
        """
        self.credentials = credentials
        # TODO: Initialize Google Admin SDK client
        raise NotImplementedError(
            "Google Workspace provider not yet implemented. "
            "Requires Google Admin SDK setup with service account credentials."
        )

    def fetch_users(self) -> List[Dict[str, Any]]:
        """Fetch all users from Google Workspace.

        Returns:
            List of Google user objects
        """
        # TODO: Use Google Admin SDK to list users
        raise NotImplementedError("Google Workspace provider not yet implemented")

    def get_user_id(self, user: Dict[str, Any]) -> str:
        """Get Google user ID.

        Args:
            user: Google user object

        Returns:
            Google user ID
        """
        return user["id"]

    def get_user_email(self, user: Dict[str, Any]) -> str:
        """Get email from Google user.

        Args:
            user: Google user object

        Returns:
            User's primary email address
        """
        return user["primaryEmail"]

    def get_user_name(self, user: Dict[str, Any]) -> str:
        """Get full name from Google user.

        Args:
            user: Google user object

        Returns:
            User's full name
        """
        return user["name"]["fullName"]

    def is_bot(self, user: Dict[str, Any]) -> bool:
        """Check if Google user is a service account.

        Args:
            user: Google user object

        Returns:
            True if user is a service account
        """
        # Google doesn't have bots in the same way, but service accounts exist
        return False

    def is_deleted(self, user: Dict[str, Any]) -> bool:
        """Check if Google user is suspended.

        Args:
            user: Google user object

        Returns:
            True if user is suspended
        """
        return user.get("suspended", False)


def get_user_provider(provider_type: str | None = None) -> UserProvider:
    """Factory function to create user provider instances.

    Args:
        provider_type: Type of provider ('slack', 'google'). If None, uses
            USER_MANAGEMENT_PROVIDER environment variable (defaults to 'slack')

    Returns:
        UserProvider instance

    Raises:
        ValueError: If provider type is unknown or required credentials are missing
    """
    if provider_type is None:
        provider_type = os.getenv("USER_MANAGEMENT_PROVIDER", "slack").lower()

    if provider_type == "slack":
        bot_token = os.getenv("SLACK_BOT_TOKEN")
        if not bot_token:
            raise ValueError(
                "SLACK_BOT_TOKEN environment variable required for Slack provider"
            )
        return SlackUserProvider(bot_token=bot_token)

    elif provider_type == "google":
        # TODO: Load Google credentials from environment/file
        credentials = None  # Load from GOOGLE_APPLICATION_CREDENTIALS or similar
        return GoogleWorkspaceProvider(credentials=credentials)

    else:
        raise ValueError(
            f"Unknown provider type: {provider_type}. "
            f"Supported providers: slack, google"
        )
