"""Slack enumeration types"""

from enum import StrEnum


class SlackEventType(StrEnum):
    """Types of Slack events we handle."""

    MESSAGE = "message"
    APP_MENTION = "app_mention"
    FILE_SHARE = "file_share"
    MEMBER_JOINED = "member_joined_channel"
    MEMBER_LEFT = "member_left_channel"
    CHANNEL_CREATED = "channel_created"
    BOT_MESSAGE = "bot_message"
    THREAD_REPLY = "thread_reply"


class MessageSubtype(StrEnum):
    """Slack message subtypes."""

    BOT_MESSAGE = "bot_message"
    FILE_SHARE = "file_share"
    THREAD_BROADCAST = "thread_broadcast"
    MESSAGE_CHANGED = "message_changed"
    MESSAGE_DELETED = "message_deleted"
