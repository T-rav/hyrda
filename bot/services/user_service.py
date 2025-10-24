"""User Service for looking up Slack user information from the database."""

import json
import logging
from typing import Any

from sqlalchemy import Boolean, Column, Integer, String, create_engine, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


# Simple SQLAlchemy model for slack_users table (SQLAlchemy 1.4 compatible)
Base = declarative_base()


class SlackUser(Base):
    """Slack user model."""

    __tablename__ = "slack_users"

    id = Column(Integer, primary_key=True)
    slack_user_id = Column(String(255), unique=True, nullable=False)
    email_address = Column(String(255))
    display_name = Column(String(255))
    real_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    user_type = Column(String(50))


class UserService:
    """Service for retrieving user information from the slack_users table with Redis caching."""

    # Cache TTL: 1 hour (users don't change frequently)
    CACHE_TTL = 3600

    def __init__(self, redis_client=None, database_url: str | None = None):
        """
        Initialize the user service.

        Args:
            redis_client: Optional Redis client for caching
            database_url: Database connection URL
        """
        self.redis_client = redis_client
        self._session_factory = None
        if database_url:
            try:
                engine = create_engine(database_url, pool_pre_ping=True)
                self._session_factory = sessionmaker(bind=engine)
            except ImportError as e:
                # Database driver not installed (e.g., pymysql, asyncpg)
                logger.warning(
                    f"Database driver not available: {e}. "
                    "Install optional database dependencies: pip install '.[database]'"
                )
            except Exception as e:
                logger.error(f"Failed to initialize database engine: {e}")

    def _get_cache_key(self, slack_user_id: str) -> str:
        """Generate Redis cache key for user info."""
        return f"user_info:{slack_user_id}"

    def _get_from_cache(self, slack_user_id: str) -> dict[str, Any] | None:
        """
        Get user info from Redis cache.

        Args:
            slack_user_id: The Slack user ID

        Returns:
            Cached user info or None if not in cache
        """
        if not self.redis_client:
            return None

        try:
            cache_key = self._get_cache_key(slack_user_id)
            cached_data = self.redis_client.get(cache_key)

            if cached_data:
                logger.debug(f"Cache HIT for user {slack_user_id}")
                return json.loads(cached_data)

            logger.debug(f"Cache MISS for user {slack_user_id}")
            return None

        except Exception as e:
            logger.warning(f"Error reading from cache for user {slack_user_id}: {e}")
            return None

    def _set_in_cache(self, slack_user_id: str, user_info: dict[str, Any]) -> None:
        """
        Store user info in Redis cache.

        Args:
            slack_user_id: The Slack user ID
            user_info: User information to cache
        """
        if not self.redis_client:
            return

        try:
            cache_key = self._get_cache_key(slack_user_id)
            self.redis_client.setex(cache_key, self.CACHE_TTL, json.dumps(user_info))
            logger.debug(f"Cached user info for {slack_user_id}")

        except Exception as e:
            logger.warning(f"Error writing to cache for user {slack_user_id}: {e}")

    def get_user_info(self, slack_user_id: str) -> dict[str, Any] | None:
        """
        Get user information from cache or database.

        Args:
            slack_user_id: The Slack user ID (e.g., U01234567)

        Returns:
            Dictionary with user info or None if not found
        """
        # Try cache first
        cached_info = self._get_from_cache(slack_user_id)
        if cached_info:
            return cached_info

        # Cache miss - fetch from database
        user_info = self._fetch_from_database(slack_user_id)

        if user_info:
            # Store in cache for future requests
            self._set_in_cache(slack_user_id, user_info)
            return user_info

        logger.warning(f"User {slack_user_id} not found in cache or database")
        return None

    def _fetch_from_database(self, slack_user_id: str) -> dict[str, Any] | None:
        """
        Fetch user info from database.

        Args:
            slack_user_id: The Slack user ID

        Returns:
            User info dictionary or None if not found
        """
        if not self._session_factory:
            logger.warning("Database not configured, cannot fetch user info")
            return None

        try:
            with self._session_factory() as session:
                stmt = select(SlackUser).where(SlackUser.slack_user_id == slack_user_id)
                user = session.execute(stmt).scalar_one_or_none()

                if user:
                    logger.debug(f"Database HIT for user {slack_user_id}")
                    return {
                        "slack_user_id": user.slack_user_id,
                        "email_address": user.email_address,
                        "display_name": user.display_name,
                        "real_name": user.real_name,
                        "is_active": user.is_active,
                        "user_type": user.user_type,
                    }

                logger.debug(f"Database MISS for user {slack_user_id}")
                return None

        except Exception as e:
            logger.error(f"Error fetching user from database: {e}")
            return None

    def invalidate_cache(self, slack_user_id: str) -> None:
        """
        Invalidate cached user info (useful when user data is updated).

        Args:
            slack_user_id: The Slack user ID to invalidate
        """
        if not self.redis_client:
            return

        try:
            cache_key = self._get_cache_key(slack_user_id)
            self.redis_client.delete(cache_key)
            logger.info(f"Invalidated cache for user {slack_user_id}")

        except Exception as e:
            logger.warning(f"Error invalidating cache for user {slack_user_id}: {e}")


# Global instance
_user_service: UserService | None = None


def get_user_service(redis_client=None, database_url: str | None = None) -> UserService:
    """
    Get or create the global user service instance.

    Args:
        redis_client: Optional Redis client for caching (only used on first init)
        database_url: Optional database URL (only used on first init)

    Returns:
        UserService instance
    """
    global _user_service  # noqa: PLW0603
    if _user_service is None:
        # Try to get Redis client from conversation_cache if not provided
        if redis_client is None:
            try:
                from services.conversation_cache import get_redis_client

                redis_client = get_redis_client()
                if redis_client:
                    logger.info("UserService initialized with Redis caching")
                else:
                    logger.warning(
                        "UserService initialized without Redis caching (Redis unavailable)"
                    )
            except Exception as e:
                logger.warning(f"Could not get Redis client: {e}")

        # Get database URL from settings if not provided
        if database_url is None:
            try:
                from config.settings import Settings

                settings = Settings()
                if settings.database.enabled:
                    database_url = settings.database.url
                    logger.info("UserService initialized with database connection")
                else:
                    logger.warning("Database disabled in settings")
            except Exception as e:
                logger.warning(f"Could not get database URL from settings: {e}")

        _user_service = UserService(
            redis_client=redis_client, database_url=database_url
        )
    return _user_service
