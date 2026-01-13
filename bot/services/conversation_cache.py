import json
import logging
from datetime import UTC, datetime

import redis.asyncio as redis

from services.slack_service import SlackService

logger = logging.getLogger(__name__)


class ConversationCache:
    """Redis-based conversation history cache with Slack API fallback"""

    def __init__(self, redis_url: str = "redis://localhost:6379", ttl: int = 1800):
        self.redis_url = redis_url
        self.ttl = ttl  # 30 minutes default
        self.cache_key_prefix = "slack_conversation:"
        self.redis_client = None
        self._redis_available = None

    async def _get_redis_client(self) -> redis.Redis | None:
        """Get Redis client with connection health check"""
        if self.redis_client is None:
            try:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                    retry_on_timeout=True,
                    health_check_interval=30,
                )
                # Test connection
                await self.redis_client.ping()
                self._redis_available = True
                logger.info(f"Connected to Redis at {self.redis_url}")
            except Exception as e:
                logger.warning(
                    f"Redis connection failed: {e}. Will use Slack API only."
                )
                self._redis_available = False
                self.redis_client = None

        return self.redis_client if self._redis_available else None

    def _get_cache_key(self, thread_ts: str) -> str:
        """Generate cache key for thread"""
        return f"conversation:{thread_ts}"

    def _get_metadata_key(self, thread_ts: str) -> str:
        """Generate metadata cache key for thread"""
        return f"conversation_meta:{thread_ts}"

    def _get_document_key(self, thread_ts: str) -> str:
        """Generate document cache key for thread"""
        return f"conversation_documents:{thread_ts}"

    def _get_summary_key(self, thread_ts: str, version: int | None = None) -> str:
        """Generate summary cache key for thread (with optional version)"""
        if version is not None:
            return f"conversation_summary:{thread_ts}:v{version}"
        return f"conversation_summary:{thread_ts}:current"

    def _get_summary_history_key(self, thread_ts: str) -> str:
        """Generate summary history metadata key"""
        return f"conversation_summary:{thread_ts}:history"

    async def get_conversation(
        self, channel: str, thread_ts: str, slack_service: SlackService
    ) -> tuple[list[dict[str, str]], bool, str]:
        """
        Get conversation history with cache-first approach
        Returns: (messages, success, source)
        """
        cache_key = self._get_cache_key(thread_ts)
        meta_key = self._get_metadata_key(thread_ts)

        # Try cache first
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                # Get cached conversation and metadata
                cached_data = await redis_client.get(cache_key)
                cached_meta = await redis_client.get(meta_key)

                if cached_data and cached_meta:
                    messages = json.loads(cached_data)
                    metadata = json.loads(cached_meta)

                    logger.info(
                        "Retrieved conversation from cache",
                        extra={
                            "thread_ts": thread_ts,
                            "channel_id": channel,
                            "message_count": len(messages),
                            "cache_age_seconds": self._get_cache_age(metadata),
                            "event_type": "cache_hit",
                        },
                    )

                    return messages, True, "cache"

            except Exception as e:
                logger.warning(
                    f"Cache retrieval failed: {e}. Falling back to Slack API."
                )

        # Fallback to Slack API
        logger.info(
            "Cache miss, fetching from Slack API",
            extra={
                "thread_ts": thread_ts,
                "channel_id": channel,
                "event_type": "cache_miss",
            },
        )

        messages, success = await slack_service.get_thread_history(channel, thread_ts)

        # Cache the result if successful and Redis is available
        if success and redis_client and messages:
            try:
                await self._cache_conversation(redis_client, thread_ts, messages)
            except Exception as e:
                logger.warning(f"Failed to cache conversation: {e}")

        source = "slack_api" if success else "failed"
        return messages, success, source

    async def store_document_content(
        self, thread_ts: str, document_content: str, document_filename: str
    ) -> bool:
        """Store document content for later retrieval in conversation"""
        document_key = self._get_document_key(thread_ts)

        redis_client = await self._get_redis_client()
        if not redis_client:
            return False

        try:
            document_data = {
                "content": document_content,
                "filename": document_filename,
                "stored_at": datetime.now(UTC).isoformat(),
            }

            await redis_client.setex(document_key, self.ttl, json.dumps(document_data))

            logger.info(
                f"Stored document content for thread {thread_ts}: {document_filename}"
            )
            return True

        except Exception as e:
            logger.warning(f"Failed to store document content: {e}")
            return False

    async def get_document_content(
        self, thread_ts: str
    ) -> tuple[str | None, str | None]:
        """Retrieve stored document content for thread

        Returns:
            tuple: (document_content, document_filename) or (None, None) if not found

        """
        document_key = self._get_document_key(thread_ts)

        redis_client = await self._get_redis_client()
        if not redis_client:
            return None, None

        try:
            document_data = await redis_client.get(document_key)
            if not document_data:
                return None, None

            data = json.loads(document_data)
            logger.info(
                f"Retrieved document content for thread {thread_ts}: {data.get('filename')}"
            )
            return data.get("content"), data.get("filename")

        except Exception as e:
            logger.warning(f"Failed to retrieve document content: {e}")
            return None, None

    async def store_summary(
        self,
        thread_ts: str,
        summary: str,
        message_count: int = 0,
        compressed_from: int = 0,
        max_versions: int = 5,
    ) -> bool:
        """
        Store conversation summary in cache with structured metadata and versioning.

        Args:
            thread_ts: Thread timestamp
            summary: Summary text
            message_count: Number of messages in current context
            compressed_from: Number of messages that were compressed into this summary
            max_versions: Maximum number of summary versions to keep (default: 5)

        Returns:
            True if summary was stored successfully

        """
        redis_client = await self._get_redis_client()
        if not redis_client:
            return False

        try:
            # Estimate token count for summary (chars / 4)
            token_count = len(summary) // 4

            # Get current version number from history
            history_key = self._get_summary_history_key(thread_ts)
            history_data = await redis_client.get(history_key)

            if history_data:
                history = json.loads(history_data)
                current_version = history.get("current_version", 0)
                versions = history.get("versions", [])
            else:
                current_version = 0
                versions = []

            # Increment version
            new_version = current_version + 1

            # Create structured summary data with metadata
            summary_data = {
                "summary": summary,
                "version": new_version,
                "token_count": token_count,
                "message_count": message_count,
                "compressed_from_messages": compressed_from,
                "created_at": datetime.now(UTC).isoformat(),
            }

            # Store current summary (for quick access)
            current_key = self._get_summary_key(thread_ts)
            await redis_client.setex(current_key, self.ttl, json.dumps(summary_data))

            # Store versioned summary
            version_key = self._get_summary_key(thread_ts, new_version)
            await redis_client.setex(version_key, self.ttl, json.dumps(summary_data))

            # Update version history
            versions.append(
                {
                    "version": new_version,
                    "token_count": token_count,
                    "created_at": summary_data["created_at"],
                }
            )

            # Keep only last N versions
            if len(versions) > max_versions:
                # Remove oldest version from history
                old_version = versions.pop(0)
                # Delete old versioned summary from Redis
                old_key = self._get_summary_key(thread_ts, old_version["version"])
                await redis_client.delete(old_key)

            # Store updated history
            history_data = {
                "current_version": new_version,
                "versions": versions,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            await redis_client.setex(history_key, self.ttl, json.dumps(history_data))

            logger.info(
                f"Stored conversation summary v{new_version} for thread {thread_ts}: "
                f"{len(summary)} chars (~{token_count} tokens), "
                f"compressed from {compressed_from} messages"
            )
            return True

        except Exception as e:
            logger.warning(f"Failed to store summary: {e}")
            return False

    async def get_summary(
        self, thread_ts: str, version: int | None = None
    ) -> str | None:
        """
        Retrieve conversation summary from cache.

        Args:
            thread_ts: Thread timestamp
            version: Optional specific version to retrieve (default: current)

        Returns:
            Summary text or None if not found

        """
        summary_key = (
            self._get_summary_key(thread_ts, version)
            if version
            else self._get_summary_key(thread_ts)
        )

        redis_client = await self._get_redis_client()
        if not redis_client:
            return None

        try:
            summary_data = await redis_client.get(summary_key)
            if not summary_data:
                return None

            data = json.loads(summary_data)
            version_str = (
                f"v{data.get('version', '?')}" if data.get("version") else "current"
            )
            logger.info(
                f"Retrieved summary {version_str} for thread {thread_ts}: "
                f"{len(data.get('summary', ''))} chars (~{data.get('token_count', '?')} tokens)"
            )
            return data.get("summary")

        except Exception as e:
            logger.warning(f"Failed to retrieve summary: {e}")
            return None

    async def get_summary_metadata(
        self, thread_ts: str, version: int | None = None
    ) -> dict | None:
        """
        Retrieve summary metadata without the full summary text.

        Args:
            thread_ts: Thread timestamp
            version: Optional specific version (default: current)

        Returns:
            Dictionary with metadata (version, token_count, message_count, etc.) or None

        """
        summary_key = (
            self._get_summary_key(thread_ts, version)
            if version
            else self._get_summary_key(thread_ts)
        )

        redis_client = await self._get_redis_client()
        if not redis_client:
            return None

        try:
            summary_data = await redis_client.get(summary_key)
            if not summary_data:
                return None

            data = json.loads(summary_data)
            # Return metadata without the full summary text
            return {
                "version": data.get("version"),
                "token_count": data.get("token_count"),
                "message_count": data.get("message_count"),
                "compressed_from_messages": data.get("compressed_from_messages"),
                "created_at": data.get("created_at"),
                "summary_length": len(data.get("summary", "")),
            }

        except Exception as e:
            logger.warning(f"Failed to retrieve summary metadata: {e}")
            return None

    async def get_summary_history(self, thread_ts: str) -> dict | None:
        """
        Retrieve summary version history.

        Args:
            thread_ts: Thread timestamp

        Returns:
            Dictionary with version history or None

        """
        history_key = self._get_summary_history_key(thread_ts)

        redis_client = await self._get_redis_client()
        if not redis_client:
            return None

        try:
            history_data = await redis_client.get(history_key)
            if not history_data:
                return None

            history = json.loads(history_data)
            logger.info(
                f"Retrieved summary history for thread {thread_ts}: "
                f"{len(history.get('versions', []))} versions"
            )
            return history

        except Exception as e:
            logger.warning(f"Failed to retrieve summary history: {e}")
            return None

    async def update_conversation(
        self, thread_ts: str, new_message: dict[str, str], is_bot_message: bool = False
    ) -> bool:
        """
        Update cached conversation with new message
        Returns: True if cache was updated, False if cache unavailable
        """
        cache_key = self._get_cache_key(thread_ts)
        self._get_metadata_key(thread_ts)

        redis_client = await self._get_redis_client()
        if not redis_client:
            return False

        try:
            # Get existing conversation
            cached_data = await redis_client.get(cache_key)
            if not cached_data:
                # No existing cache, start new conversation
                messages = [new_message]
            else:
                messages = json.loads(cached_data)
                messages.append(new_message)

            # Update cache
            await self._cache_conversation(redis_client, thread_ts, messages)

            logger.debug(
                "Updated conversation cache",
                extra={
                    "thread_ts": thread_ts,
                    "message_count": len(messages),
                    "is_bot_message": is_bot_message,
                    "event_type": "cache_update",
                },
            )

            return True

        except Exception as e:
            logger.warning(f"Failed to update conversation cache: {e}")
            return False

    async def _cache_conversation(
        self, redis_client: redis.Redis, thread_ts: str, messages: list[dict[str, str]]
    ):
        """Store conversation and metadata in cache"""
        cache_key = self._get_cache_key(thread_ts)
        meta_key = self._get_metadata_key(thread_ts)

        # Store conversation data
        conversation_data = json.dumps(messages)
        await redis_client.setex(cache_key, self.ttl, conversation_data)

        # Store metadata - PRESERVE existing fields like thread_type!
        existing_meta = await redis_client.get(meta_key)
        if existing_meta:
            try:
                metadata = json.loads(existing_meta)
                # Ensure it's a dict, not a list
                if not isinstance(metadata, dict):
                    metadata = {}
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        else:
            metadata = {}

        # Update with new cache info (preserves thread_type if it exists)
        metadata.update(
            {
                "cached_at": datetime.now(UTC).isoformat(),
                "message_count": len(messages),
                "ttl": self.ttl,
            }
        )

        meta_data = json.dumps(metadata)
        await redis_client.setex(meta_key, self.ttl, meta_data)

    def _get_cache_age(self, metadata: dict) -> int:
        """Calculate cache age in seconds"""
        try:
            cached_at = datetime.fromisoformat(
                metadata["cached_at"].replace("Z", "+00:00")
            )
            age = (datetime.now(UTC) - cached_at).total_seconds()
            return int(age)
        except Exception:
            return 0

    async def clear_conversation(self, thread_ts: str) -> bool:
        """Clear specific conversation from cache, including all summary versions"""
        redis_client = await self._get_redis_client()
        if not redis_client:
            return False

        try:
            cache_key = self._get_cache_key(thread_ts)
            meta_key = self._get_metadata_key(thread_ts)
            document_key = self._get_document_key(thread_ts)
            summary_key = self._get_summary_key(thread_ts)
            history_key = self._get_summary_history_key(thread_ts)

            keys_to_delete = [
                cache_key,
                meta_key,
                document_key,
                summary_key,
                history_key,
            ]

            # Get version history to delete all versioned summaries
            history_data = await redis_client.get(history_key)
            if history_data:
                history = json.loads(history_data)
                versions = history.get("versions", [])
                for version_info in versions:
                    version_key = self._get_summary_key(
                        thread_ts, version_info["version"]
                    )
                    keys_to_delete.append(version_key)

            deleted = await redis_client.delete(*keys_to_delete)
            logger.info(
                f"Cleared conversation cache for {thread_ts}, deleted {deleted} keys "
                f"(including {len(keys_to_delete) - 5} versioned summaries)"
            )
            return deleted > 0

        except Exception as e:
            logger.warning(f"Failed to clear conversation cache: {e}")
            return False

    async def set_thread_type(self, thread_ts: str, thread_type: str) -> bool:
        """
        Store thread type metadata (e.g., 'profile', 'meddic', 'general').

        Args:
            thread_ts: Thread timestamp
            thread_type: Type of thread ('profile', 'meddic', 'general', etc.)

        Returns:
            True if stored successfully, False otherwise

        """
        redis_client = await self._get_redis_client()
        if not redis_client:
            return False

        try:
            meta_key = self._get_metadata_key(thread_ts)
            logger.info(
                f"🔍 Storing thread_type='{thread_type}' for {thread_ts}, key={meta_key}"
            )

            # Get existing metadata or create new
            existing_meta = await redis_client.get(meta_key)
            if existing_meta:
                metadata = json.loads(existing_meta)
            else:
                metadata = {"cached_at": datetime.now(UTC).isoformat()}

            # Add thread type
            metadata["thread_type"] = thread_type

            await redis_client.setex(meta_key, self.ttl, json.dumps(metadata))
            logger.info(
                f"✅ Stored thread_type='{thread_type}' for thread {thread_ts} at key {meta_key}"
            )
            return True

        except Exception as e:
            logger.warning(f"Failed to store thread type: {e}")
            return False

    async def get_thread_type(self, thread_ts: str) -> str | None:
        """
        Retrieve thread type metadata.

        Args:
            thread_ts: Thread timestamp

        Returns:
            Thread type string ('profile', 'meddic', 'general') or None if not set

        """
        redis_client = await self._get_redis_client()
        if not redis_client:
            logger.warning(
                f"get_thread_type: No Redis client available for thread {thread_ts}"
            )
            return None

        try:
            meta_key = self._get_metadata_key(thread_ts)
            logger.info(f"🔍 Getting thread_type for {thread_ts}, key={meta_key}")
            metadata_json = await redis_client.get(meta_key)

            if not metadata_json:
                logger.warning(
                    f"❌ No metadata found for thread {thread_ts} at key {meta_key}"
                )
                return None

            metadata = json.loads(metadata_json)
            thread_type = metadata.get("thread_type")
            logger.info(
                f"✅ Retrieved thread_type='{thread_type}' for thread {thread_ts}"
            )
            return thread_type

        except Exception as e:
            logger.error(
                f"Failed to retrieve thread type for {thread_ts}: {e}", exc_info=True
            )
            return None

    async def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        redis_client = await self._get_redis_client()
        if not redis_client:
            return {"status": "unavailable"}

        try:
            info = await redis_client.info("memory")
            keys = await redis_client.keys("conversation:*")

            return {
                "status": "available",
                "memory_used": info.get("used_memory_human", "unknown"),
                "cached_conversations": len(keys),
                "redis_url": self.redis_url,
                "ttl": self.ttl,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.aclose()
            self.redis_client = None
