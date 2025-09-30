"""Slack entity models (users, channels)"""

from typing import Any

from pydantic import BaseModel, Field


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
