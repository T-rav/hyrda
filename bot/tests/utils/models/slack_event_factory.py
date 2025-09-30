"""
SlackEventFactory for test utilities
"""

from typing import Any


class SlackEventFactory:
    """Factory for creating Slack event objects"""

    @staticmethod
    def create_message_event(
        text: str = "Test message",
        user: str = "U12345",
        channel: str = "C12345",
        ts: str = "1234567890.123456",
    ) -> dict[str, Any]:
        """Create Slack message event"""
        return {
            "type": "message",
            "text": text,
            "user": user,
            "channel": channel,
            "ts": ts,
        }

    @staticmethod
    def create_app_mention_event(
        text: str = "Test mention",
        user: str = "U12345",
        channel: str = "C12345",
    ) -> dict[str, Any]:
        """Create Slack app mention event"""
        return {
            "type": "app_mention",
            "text": text,
            "user": user,
            "channel": channel,
        }

    @staticmethod
    def create_thread_reply_event(
        text: str = "Reply",
        user: str = "U12345",
        channel: str = "C12345",
        thread_ts: str = "1234567890.123456",
    ) -> dict[str, Any]:
        """Create Slack thread reply event"""
        return {
            "type": "message",
            "text": text,
            "user": user,
            "channel": channel,
            "thread_ts": thread_ts,
        }
