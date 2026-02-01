"""Usage tracking service for Slack bot interactions.

Provides tracing, logging, and database persistence for usage analytics.
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager

from opentelemetry import trace
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models.slack_usage import SlackUsage

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class UsageTrackingService:
    """Service for tracking Slack bot usage with tracing and logging.

    Records user interactions to enable:
    - Usage aggregation by user/thread
    - Analytics and monitoring
    - Usage-based billing (future)
    """

    def __init__(self, database_url: str | None = None):
        """Initialize the usage tracking service.

        Args:
            database_url: Database connection URL (optional)
        """
        self._session_factory = None
        self.logger = logging.getLogger(self.__class__.__name__)

        if database_url:
            try:
                engine = create_engine(database_url, pool_pre_ping=True)
                self._session_factory = sessionmaker(bind=engine)
                self.logger.debug("UsageTrackingService initialized with database")
            except Exception as e:
                self.logger.warning(
                    f"Failed to initialize database for usage tracking: {e}. "
                    "Usage tracking will be disabled."
                )

    def _get_session(self) -> Session | None:
        """Get database session if available."""
        if self._session_factory:
            return self._session_factory()
        return None

    def record_interaction(
        self,
        slack_user_id: str,
        thread_ts: str,
        channel_id: str | None = None,
        interaction_type: str = "message",
    ) -> SlackUsage | None:
        """Record a user interaction with full tracing.

        Args:
            slack_user_id: Slack user ID
            thread_ts: Thread timestamp (unique conversation ID)
            channel_id: Optional channel ID
            interaction_type: Type of interaction (message, agent_invoke, etc.)

        Returns:
            Created SlackUsage record or None if failed
        """
        with tracer.start_as_current_span(
            "usage_tracking.record_interaction",
            attributes={
                "slack.user_id": slack_user_id,
                "slack.thread_ts": thread_ts,
                "slack.channel_id": channel_id or "",
                "slack.interaction_type": interaction_type,
            },
        ) as span:
            session = self._get_session()
            if not session:
                span.set_attribute("usage.skipped", True)
                span.set_attribute("usage.skip_reason", "no_database")
                self.logger.debug("Usage tracking skipped: no database configured")
                return None

            try:
                self.logger.debug(
                    f"Recording interaction: user={slack_user_id}, "
                    f"thread={thread_ts}, type={interaction_type}"
                )

                usage = SlackUsage(
                    slack_user_id=slack_user_id,
                    thread_ts=thread_ts,
                    channel_id=channel_id,
                    interaction_type=interaction_type,
                )

                session.add(usage)
                session.commit()

                # Refresh to get the ID
                session.refresh(usage)

                # Set span attributes for observability
                span.set_attribute("usage.recorded", True)
                span.set_attribute("usage.id", usage.id)

                self.logger.info(
                    f"Recorded usage: id={usage.id}, user={slack_user_id}, "
                    f"thread={thread_ts}"
                )

                return usage

            except Exception as e:
                session.rollback()
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                self.logger.error(
                    f"Failed to record usage: user={slack_user_id}, "
                    f"thread={thread_ts}, error={e}"
                )
                return None
            finally:
                session.close()

    def get_user_usage_count(self, slack_user_id: str, since_days: int = 30) -> int:
        """Get total usage count for a user.

        Args:
            slack_user_id: Slack user ID
            since_days: Number of days to look back
        Returns:
            Total interaction count
        """
        with tracer.start_as_current_span(
            "usage_tracking.get_user_usage_count",
            attributes={
                "slack.user_id": slack_user_id,
                "since_days": since_days,
            },
        ):
            session = self._get_session()
            if not session:
                return 0

            try:
                from datetime import datetime, timedelta

                from sqlalchemy import func

                since = datetime.now() - timedelta(days=since_days)

                count = (
                    session.query(func.count(SlackUsage.id))
                    .filter(SlackUsage.slack_user_id == slack_user_id)
                    .filter(SlackUsage.created_at >= since)
                    .scalar()
                    or 0
                )

                return count
            finally:
                session.close()

    def get_thread_participant_count(self, thread_ts: str) -> int:
        """Get unique participant count for a thread.

        Args:
            thread_ts: Thread timestamp
        Returns:
            Number of unique users in thread
        """
        with tracer.start_as_current_span(
            "usage_tracking.get_thread_participant_count",
            attributes={"slack.thread_ts": thread_ts},
        ):
            session = self._get_session()
            if not session:
                return 0

            try:
                from sqlalchemy import func

                count = (
                    session.query(func.count(func.distinct(SlackUsage.slack_user_id)))
                    .filter(SlackUsage.thread_ts == thread_ts)
                    .scalar()
                    or 0
                )

                return count
            finally:
                session.close()


# Global instance
_usage_tracking_service: UsageTrackingService | None = None


def get_usage_tracking_service(
    database_url: str | None = None,
) -> UsageTrackingService:
    """Get or create the global usage tracking service.

    Args:
        database_url: Database connection URL (optional)

    Returns:
        UsageTrackingService instance
    """
    global _usage_tracking_service  # noqa: PLW0603
    if _usage_tracking_service is None:
        _usage_tracking_service = UsageTrackingService(database_url=database_url)

    return _usage_tracking_service


def reset_usage_tracking_service() -> None:
    """Reset the global usage tracking service (for testing)."""
    globals()["_usage_tracking_service"] = None


@contextmanager
def usage_tracking_context(
    database_url: str | None = None,
) -> Generator[UsageTrackingService, None, None]:
    """Context manager for usage tracking service.

    Args:
        database_url: Database connection URL (optional)

    Yields:
        UsageTrackingService instance

    Example:
        with usage_tracking_context() as usage_service:
            usage_service.record_interaction(user_id, thread_ts)
    """
    service = get_usage_tracking_service(database_url)
    try:
        yield service
    finally:
        logger.debug("Usage tracking context exited")
