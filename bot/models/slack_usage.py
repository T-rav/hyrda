"""Slack usage tracking model."""

from sqlalchemy import Column, DateTime, Integer, String, func

from .base import Base


class SlackUsage(Base):
    __tablename__ = "slack_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Slack identifiers (indexed for fast aggregation queries)
    slack_user_id = Column(String(255), nullable=False, index=True)
    thread_ts = Column(String(255), nullable=False, index=True)
    channel_id = Column(String(255), nullable=True, index=True)

    # Interaction metadata
    interaction_type = Column(
        String(50),
        nullable=False,
        default="message",
        doc="Type of interaction: message, agent_invoke, file_upload, etc.",
    )

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now(), index=True)

    def __repr__(self) -> str:
        return (
            f"<SlackUsage("
            f"id={self.id}, "
            f"user={self.slack_user_id}, "
            f"thread={self.thread_ts}, "
            f"type={self.interaction_type}"
            f")>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "slack_user_id": self.slack_user_id,
            "thread_ts": self.thread_ts,
            "channel_id": self.channel_id,
            "interaction_type": self.interaction_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
