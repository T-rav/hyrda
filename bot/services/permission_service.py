"""Permission service for managing agent access control with caching."""

import json
import logging
from typing import Any

from config.settings import Settings
from models.agent_metadata import AgentMetadata
from models.agent_permission import AgentPermission
from models.base import get_db_session

logger = logging.getLogger(__name__)


class PermissionService:
    """Service for managing agent permissions with Redis caching."""

    CACHE_TTL = 900  # 15 minutes in seconds

    def __init__(self, redis_client=None, database_url: str | None = None):
        """Initialize permission service.

        Args:
            redis_client: Optional Redis client for caching
            database_url: Optional database URL for DB connection
        """
        self.redis_client = redis_client
        self.database_url = database_url

    def _get_cache_key(self, user_id: str, agent_name: str) -> str:
        """Generate cache key for user-agent permission.

        Args:
            user_id: Slack user ID
            agent_name: Agent name

        Returns:
            Cache key string
        """
        return f"permission:{agent_name}:{user_id}"

    def _get_from_cache(self, user_id: str, agent_name: str) -> dict[str, Any] | None:
        """Get permission from Redis cache.

        Args:
            user_id: Slack user ID
            agent_name: Agent name

        Returns:
            Cached permission dict or None if not found
        """
        if not self.redis_client:
            return None

        try:
            cache_key = self._get_cache_key(user_id, agent_name)
            cached = self.redis_client.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for permission: {agent_name}:{user_id}")
                return json.loads(cached)
            logger.debug(f"Cache miss for permission: {agent_name}:{user_id}")
        except Exception as e:
            logger.warning(f"Error reading from cache: {e}")

        return None

    def _write_to_cache(
        self, user_id: str, agent_name: str, permission_data: dict[str, Any]
    ) -> None:
        """Write permission to Redis cache.

        Args:
            user_id: Slack user ID
            agent_name: Agent name
            permission_data: Permission result to cache
        """
        if not self.redis_client:
            return

        try:
            cache_key = self._get_cache_key(user_id, agent_name)
            self.redis_client.setex(
                cache_key, self.CACHE_TTL, json.dumps(permission_data)
            )
            logger.debug(
                f"Cached permission for {agent_name}:{user_id} (TTL={self.CACHE_TTL}s)"
            )
        except Exception as e:
            logger.warning(f"Error writing to cache: {e}")

    def invalidate_cache(
        self, user_id: str | None = None, agent_name: str | None = None
    ) -> None:
        """Invalidate cached permissions.

        Args:
            user_id: Optional user ID to invalidate (None = all users)
            agent_name: Optional agent name to invalidate (None = all agents)
        """
        if not self.redis_client:
            return

        try:
            if user_id and agent_name:
                # Invalidate specific user-agent pair
                cache_key = self._get_cache_key(user_id, agent_name)
                self.redis_client.delete(cache_key)
                logger.info(f"Invalidated cache for {agent_name}:{user_id}")
            elif agent_name:
                # Invalidate all users for this agent
                pattern = f"permission:{agent_name}:*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
                logger.info(
                    f"Invalidated cache for agent {agent_name} ({len(keys)} keys)"
                )
            elif user_id:
                # Invalidate all agents for this user
                pattern = f"permission:*:{user_id}"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
                logger.info(f"Invalidated cache for user {user_id} ({len(keys)} keys)")
        except Exception as e:
            logger.warning(f"Error invalidating cache: {e}")

    def can_use_agent(self, user_id: str, agent_name: str) -> tuple[bool, str]:
        """Check if user can use an agent (with caching).

        Args:
            user_id: Slack user ID
            agent_name: Agent name

        Returns:
            (allowed: bool, reason: str) tuple
        """
        # 1. Check cache first
        cached = self._get_from_cache(user_id, agent_name)
        if cached is not None:
            return cached["allowed"], cached["reason"]

        # 2. Cache miss - check database
        allowed, reason = self._check_permission_from_db(user_id, agent_name)

        # 3. Cache result
        self._write_to_cache(
            user_id, agent_name, {"allowed": allowed, "reason": reason}
        )

        return allowed, reason

    def _check_permission_from_db(  # noqa: PLR0911
        self, user_id: str, agent_name: str
    ) -> tuple[bool, str]:
        """Check permission from database (no cache).

        Args:
            user_id: Slack user ID
            agent_name: Agent name

        Returns:
            (allowed: bool, reason: str) tuple
        """
        try:
            with get_db_session(self.database_url) as session:
                # 1. Get agent metadata
                agent_meta = (
                    session.query(AgentMetadata)
                    .filter(AgentMetadata.agent_name == agent_name)
                    .first()
                )

                # If no metadata, default to public (backward compatible)
                if not agent_meta:
                    logger.debug(
                        f"No metadata for agent {agent_name}, defaulting to public"
                    )
                    return True, "Public agent (no metadata)"

                # 2. Check if agent is public
                if agent_meta.is_public:
                    logger.debug(f"Agent {agent_name} is public, allowing access")
                    return True, "Public agent"

                # 3. Check admin requirement
                if agent_meta.requires_admin:
                    from services.user_service import get_user_service

                    user_service = get_user_service(redis_client=self.redis_client)
                    user_info = user_service.get_user_info(user_id)

                    if not user_info or not user_info.get("is_admin", False):
                        logger.info(
                            f"User {user_id} denied access to admin-only agent {agent_name}"
                        )
                        return False, "This agent requires admin access"

                    # Admin user - allow
                    logger.info(f"Admin user {user_id} granted access to {agent_name}")
                    return True, "Admin access granted"

                # 4. Check explicit permissions in database
                permission = (
                    session.query(AgentPermission)
                    .filter(
                        AgentPermission.agent_name == agent_name,
                        AgentPermission.slack_user_id == user_id,
                    )
                    .first()
                )

                if permission:
                    if permission.permission_type == "allow":
                        logger.info(
                            f"User {user_id} explicitly allowed for {agent_name} (granted by {permission.granted_by})"
                        )
                        return (
                            True,
                            f"Access granted by {permission.granted_by or 'admin'}",
                        )

                    logger.info(
                        f"User {user_id} explicitly denied for {agent_name} (denied by {permission.granted_by})"
                    )
                    return False, f"Access denied by {permission.granted_by or 'admin'}"

                # 5. Private agent with no explicit permission - deny
                logger.info(
                    f"User {user_id} denied access to private agent {agent_name} (no explicit permission)"
                )
                return False, "You don't have permission to use this agent"

        except Exception as e:
            logger.error(f"Error checking permission: {e}", exc_info=True)
            # On error, fail open for public agents, fail closed for unknown
            return True, "Permission check error (defaulting to allow)"

    def grant_permission(
        self,
        user_id: str,
        agent_name: str,
        granted_by: str,
        expires_at: str | None = None,
    ) -> bool:
        """Grant user permission to use an agent.

        Args:
            user_id: Slack user ID to grant permission
            agent_name: Agent name
            granted_by: Slack user ID who granted permission
            expires_at: Optional expiration timestamp

        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_session(self.database_url) as session:
                # Check if permission already exists
                existing = (
                    session.query(AgentPermission)
                    .filter(
                        AgentPermission.agent_name == agent_name,
                        AgentPermission.slack_user_id == user_id,
                    )
                    .first()
                )

                if existing:
                    # Update existing permission
                    existing.permission_type = "allow"
                    existing.granted_by = granted_by
                    existing.expires_at = expires_at
                else:
                    # Create new permission
                    permission = AgentPermission(
                        agent_name=agent_name,
                        slack_user_id=user_id,
                        permission_type="allow",
                        granted_by=granted_by,
                        expires_at=expires_at,
                    )
                    session.add(permission)

                session.commit()

                # Invalidate cache
                self.invalidate_cache(user_id, agent_name)

                logger.info(
                    f"Granted {user_id} access to {agent_name} (by {granted_by})"
                )
                return True

        except Exception as e:
            logger.error(f"Error granting permission: {e}", exc_info=True)
            return False

    def revoke_permission(self, user_id: str, agent_name: str) -> bool:
        """Revoke user permission for an agent.

        Args:
            user_id: Slack user ID
            agent_name: Agent name

        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_session(self.database_url) as session:
                permission = (
                    session.query(AgentPermission)
                    .filter(
                        AgentPermission.agent_name == agent_name,
                        AgentPermission.slack_user_id == user_id,
                    )
                    .first()
                )

                if permission:
                    session.delete(permission)
                    session.commit()

                    # Invalidate cache
                    self.invalidate_cache(user_id, agent_name)

                    logger.info(f"Revoked {user_id} access to {agent_name}")
                    return True

                logger.warning(
                    f"No permission found to revoke for {user_id}:{agent_name}"
                )
                return False

        except Exception as e:
            logger.error(f"Error revoking permission: {e}", exc_info=True)
            return False


# Global instance
_permission_service: PermissionService | None = None


def get_permission_service(
    redis_client=None, database_url: str | None = None
) -> PermissionService:
    """Get or create the global permission service instance.

    Args:
        redis_client: Optional Redis client for caching (only used on first init)
        database_url: Optional database URL (only used on first init)

    Returns:
        PermissionService instance
    """
    global _permission_service  # noqa: PLW0603

    if _permission_service is None:
        # Try to get Redis client from conversation_cache if not provided
        if redis_client is None:
            try:
                from services.conversation_cache import get_conversation_cache

                cache = get_conversation_cache()
                if cache and hasattr(cache, "redis_client"):
                    redis_client = cache.redis_client
                    logger.info("Using Redis client from conversation_cache")
            except Exception as e:
                logger.warning(f"Could not get Redis client: {e}")

        # Get database URL from settings if not provided
        if database_url is None:
            try:
                settings = Settings()
                database_url = settings.database_url
            except Exception as e:
                logger.warning(f"Could not get database URL: {e}")

        _permission_service = PermissionService(
            redis_client=redis_client, database_url=database_url
        )
        logger.info("PermissionService initialized with Redis caching (TTL=15min)")

    return _permission_service
