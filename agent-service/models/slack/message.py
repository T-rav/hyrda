"""Slack message models"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from models.slack.entities import SlackChannel, SlackUser
from models.slack.enums import MessageSubtype


@dataclass(frozen=True)
class SlackMessage:
    """Slack message with rich metadata."""

    text: str
    user: SlackUser | None
    channel: SlackChannel
    timestamp: str
    thread_ts: str | None = None
    subtype: MessageSubtype | None = None
    files: list[dict[str, Any]] | None = None
    attachments: list[dict[str, Any]] | None = None
    reactions: list[dict[str, Any]] | None = None
    reply_count: int = 0
    is_thread_parent: bool = False
    is_thread_reply: bool = False
    bot_id: str | None = None
    app_id: str | None = None


@dataclass(frozen=True)
class ThreadContext:
    """Slack thread conversation context."""

    channel: str
    thread_ts: str
    messages: list[SlackMessage]
    participant_count: int
    reply_count: int
    created_at: datetime
    last_reply_at: datetime | None = None
    is_active: bool = True
    summary: str | None = None
