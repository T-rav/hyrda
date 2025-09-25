"""
Slack Service Protocol

Defines the interface for Slack API service implementations.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SlackServiceProtocol(Protocol):
    """Protocol for Slack service implementations."""

    async def send_message(
        self,
        channel: str,
        text: str,
        thread_ts: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
        mrkdwn: bool = True,
    ) -> str | None:
        """
        Send a message to a Slack channel.

        Args:
            channel: Channel ID to send message to
            text: Message text
            thread_ts: Optional thread timestamp for replies
            blocks: Optional Slack blocks for rich formatting
            mrkdwn: Whether to enable markdown formatting

        Returns:
            Message timestamp or None if sending fails
        """
        ...

    async def get_thread_history(
        self, channel: str, thread_ts: str
    ) -> tuple[list[dict[str, Any]], bool]:
        """
        Get thread history for context.

        Args:
            channel: Channel ID
            thread_ts: Thread timestamp

        Returns:
            Tuple of (messages list, is_in_thread boolean)
        """
        ...

    async def send_thinking_indicator(
        self, channel: str, thread_ts: str | None = None
    ) -> str | None:
        """
        Send a thinking indicator to show processing.

        Args:
            channel: Channel ID
            thread_ts: Optional thread timestamp

        Returns:
            Message timestamp or None if sending fails
        """
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...

    def health_check(self) -> dict[str, str]:
        """Check service health status."""
        ...
