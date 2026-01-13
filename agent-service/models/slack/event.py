"""Slack event and response models"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from models.slack.entities import SlackChannel, SlackUser
from models.slack.enums import SlackEventType
from models.slack.message import SlackMessage


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
