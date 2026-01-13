"""Typed models for Slack events and interactions.

DEPRECATED: This module is maintained for backward compatibility.
Please import from models.slack instead:
    from models.slack import SlackEvent, SlackMessage, etc.
"""

# Backward compatibility imports
from models.slack import (
    MessageSubtype,
    SlackChannel,
    SlackEvent,
    SlackEventType,
    SlackMessage,
    SlackResponse,
    SlackUser,
    ThreadContext,
)

__all__ = [
    "SlackEventType",
    "MessageSubtype",
    "SlackUser",
    "SlackChannel",
    "SlackMessage",
    "SlackEvent",
    "SlackResponse",
    "ThreadContext",
]
