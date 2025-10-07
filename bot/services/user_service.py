"""User Service for looking up Slack user information from the database."""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class UserService:
    """Service for retrieving user information from the slack_users table with Redis caching."""

    # Cache TTL: 1 hour (users don't change frequently)
    CACHE_TTL = 3600

    def __init__(self, redis_client=None):
        """
        Initialize the user service.

        Args:
            redis_client: Optional Redis client for caching
        """
        self.redis_client = redis_client

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
        try:
            from models.base import get_db_session
            from models.slack_user import SlackUser

            with get_db_session() as session:
                user = (
                    session.query(SlackUser)
                    .filter(SlackUser.slack_user_id == slack_user_id)
                    .first()
                )

                if user:
                    user_info = {
                        "slack_user_id": user.slack_user_id,
                        "real_name": user.real_name,
                        "display_name": user.display_name,
                        "email_address": user.email_address,
                        "is_admin": user.is_admin,
                        "is_bot": user.is_bot,
                    }

                    # Cache for next time
                    self._set_in_cache(slack_user_id, user_info)

                    return user_info
                else:
                    logger.warning(f"User {slack_user_id} not found in database")
                    return None

        except Exception as e:
            logger.error(f"Error fetching user info for {slack_user_id}: {e}")
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


def get_user_service(redis_client=None) -> UserService:
    """
    Get or create the global user service instance.

    Args:
        redis_client: Optional Redis client for caching (only used on first init)

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

        _user_service = UserService(redis_client=redis_client)
    return _user_service
