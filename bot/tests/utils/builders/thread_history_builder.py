"""
ThreadHistoryBuilder for test utilities
"""

from typing import Any


class ThreadHistoryBuilder:
    """Builder for creating Slack thread histories"""

    def __init__(self):
        self._messages = []
        self._next_ts = 1234567890.0

    def add_message(
        self,
        text: str,
        user: str = "U12345",
        ts: str | None = None,
        thread_ts: str | None = None,
    ):
        """Add message to thread"""
        if ts is None:
            ts = f"{self._next_ts:.6f}"
            self._next_ts += 1.0

        message = {
            "text": text,
            "user": user,
            "ts": ts,
        }

        if thread_ts:
            message["thread_ts"] = thread_ts

        self._messages.append(message)
        return self

    def add_bot_message(
        self,
        text: str,
        bot_id: str = "B12345678",
        ts: str | None = None,
    ):
        """Add bot message to thread

        Note: Uses 'user' field with bot_id for compatibility with SlackService
        which checks msg.get('user') == bot_id to identify bot messages.
        """
        if ts is None:
            ts = f"{self._next_ts:.6f}"
            self._next_ts += 1.0

        message = {
            "text": text,
            "user": bot_id,  # Use 'user' field for SlackService compatibility
            "ts": ts,
        }
        self._messages.append(message)
        return self

    def add_thread_reply(
        self,
        text: str,
        user: str = "U12345",
        thread_ts: str = "1234567890.000000",
    ):
        """Add reply to thread"""
        return self.add_message(text=text, user=user, thread_ts=thread_ts)

    def add_user_message(
        self,
        text: str = "Hello",
        user_id: str = "U12345",
        ts: str | None = None,
    ):
        """Add user message to thread history (compatibility method)"""
        return self.add_message(text=text, user=user_id, ts=ts)

    def add_empty_message(
        self,
        user_id: str = "U12345",
        ts: str | None = None,
    ):
        """Add empty message to thread history"""
        return self.add_message(text="", user=user_id, ts=ts)

    def add_message_with_mention(
        self,
        text: str = "<@B12345678> hello",
        user_id: str = "U12345",
        ts: str | None = None,
    ):
        """Add message with bot mention"""
        return self.add_message(text=text, user=user_id, ts=ts)

    def build(self) -> list[dict[str, Any]]:
        """Build the thread history"""
        return self._messages.copy()

    @staticmethod
    def basic_conversation() -> "ThreadHistoryBuilder":
        """Create basic conversation thread"""
        return (
            ThreadHistoryBuilder()
            .add_user_message("Hello")
            .add_bot_message("Hi there!")
            .add_user_message("How are you?", ts="1234567890.345678")
        )

    @staticmethod
    def conversation_with_mentions() -> "ThreadHistoryBuilder":
        """Create conversation with bot mentions"""
        return (
            ThreadHistoryBuilder()
            .add_message_with_mention("<@B12345678> hello")
            .add_bot_message("Hi there!")
        )

    @staticmethod
    def conversation_with_empty_messages() -> "ThreadHistoryBuilder":
        """Create conversation with empty messages"""
        return (
            ThreadHistoryBuilder()
            .add_empty_message()
            .add_empty_message(user_id="U12345", ts="1234567890.234567")
            .add_user_message("Hello", ts="1234567890.345678")
        )
