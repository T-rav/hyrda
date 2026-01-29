"""LibreChat usage tracking model for aggregating UI interactions.

Tracks conversations and interactions from LibreChat UI to enable usage analytics.
"""

from sqlalchemy import Column, DateTime, Integer, String, func

from .base import Base


class LibreChatUsage(Base):
    """Model for tracking LibreChat UI usage by user and conversation.

    This enables aggregation of:
    - Total interactions per user
    - Conversation counts
    - Usage patterns over time
    """

    __tablename__ = "librechat_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # User identifiers (indexed for fast aggregation queries)
    user_id = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)

    # Conversation metadata
    conversation_id = Column(String(255), nullable=False, index=True)
    agent_used = Column(String(100), nullable=True, doc="Agent name if agent was used")
    deep_search = Column(
        String(10), nullable=True, doc="Deep search enabled: true/false"
    )

    # Interaction metadata
    interaction_type = Column(
        String(50),
        nullable=False,
        default="message",
        doc="Type of interaction: message, agent_invoke, deep_search, etc.",
    )

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now(), index=True)

    def __repr__(self) -> str:
        return (
            f"<LibreChatUsage("
            f"id={self.id}, "
            f"user={self.user_id}, "
            f"conversation={self.conversation_id}, "
            f"type={self.interaction_type}"
            f")>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email": self.email,
            "conversation_id": self.conversation_id,
            "agent_used": self.agent_used,
            "deep_search": self.deep_search,
            "interaction_type": self.interaction_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
