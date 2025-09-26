"""Typed models for Slack events and interactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SlackEventType(str, Enum):
    """Types of Slack events we handle."""

    MESSAGE = "message"
    APP_MENTION = "app_mention"
    FILE_SHARE = "file_share"
    MEMBER_JOINED = "member_joined_channel"
    MEMBER_LEFT = "member_left_channel"
    CHANNEL_CREATED = "channel_created"
    BOT_MESSAGE = "bot_message"
    THREAD_REPLY = "thread_reply"


class MessageSubtype(str, Enum):
    """Slack message subtypes."""

    BOT_MESSAGE = "bot_message"
    FILE_SHARE = "file_share"
    THREAD_BROADCAST = "thread_broadcast"
    MESSAGE_CHANGED = "message_changed"
    MESSAGE_DELETED = "message_deleted"


class SlackUser(BaseModel):
    """Slack user information."""

    id: str
    name: str | None = None
    real_name: str | None = None
    display_name: str | None = None
    email: str | None = None
    is_bot: bool = False
    is_admin: bool = False
    is_owner: bool = False
    profile: dict[str, Any] = Field(default_factory=dict)

    class Config:
        frozen = True


class SlackChannel(BaseModel):
    """Slack channel information."""

    id: str
    name: str | None = None
    is_private: bool = False
    is_archived: bool = False
    is_general: bool = False
    member_count: int | None = None
    topic: str | None = None
    purpose: str | None = None

    class Config:
        frozen = True


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
class SlackEvent:
    """Complete Slack event structure."""

    type: SlackEventType
    event_id: str
    event_time: datetime
    team_id: str
    api_app_id: str | None = None
    message: SlackMessage | None = None
    user: SlackUser | None = None
    channel: SlackChannel | None = None
    raw_data: dict[str, Any] | None = None


@dataclass(frozen=True)
class SlackResponse:
    """Response to send back to Slack."""

    text: str
    channel: str
    thread_ts: str | None = None
    as_user: bool = True
    parse: str = "full"
    link_names: bool = True
    unfurl_links: bool = False
    unfurl_media: bool = False
    username: str | None = None
    icon_emoji: str | None = None
    blocks: list[dict[str, Any]] | None = None
    attachments: list[dict[str, Any]] | None = None


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
