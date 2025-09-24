"""Database models for the bot service."""

from .base import Base
from .slack_user import SlackUser

__all__ = ["Base", "SlackUser"]
