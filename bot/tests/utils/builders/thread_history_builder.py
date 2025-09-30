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
        """Add bot message to thread"""
        if ts is None:
            ts = f"{self._next_ts:.6f}"
            self._next_ts += 1.0

        message = {
            "text": text,
            "bot_id": bot_id,
            "ts": ts,
            "subtype": "bot_message",
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

    def build(self) -> list[dict[str, Any]]:
        """Build the thread history"""
        return self._messages.copy()
