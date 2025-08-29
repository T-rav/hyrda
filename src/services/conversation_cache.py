import json
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
import redis.asyncio as redis
from services.slack_service import SlackService

logger = logging.getLogger(__name__)

class ConversationCache:
    """Redis-based conversation history cache with Slack API fallback"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", ttl: int = 1800):
        self.redis_url = redis_url
        self.ttl = ttl  # 30 minutes default
        self.redis_client = None
        self._redis_available = None
        
    async def _get_redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client with connection health check"""
        if self.redis_client is None:
            try:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                # Test connection
                await self.redis_client.ping()
                self._redis_available = True
                logger.info(f"Connected to Redis at {self.redis_url}")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Will use Slack API only.")
                self._redis_available = False
                self.redis_client = None
                
        return self.redis_client if self._redis_available else None
        
    def _get_cache_key(self, thread_ts: str) -> str:
        """Generate cache key for thread"""
        return f"conversation:{thread_ts}"
        
    def _get_metadata_key(self, thread_ts: str) -> str:
        """Generate metadata cache key for thread"""
        return f"conversation_meta:{thread_ts}"
        
    async def get_conversation(
        self, 
        channel: str, 
        thread_ts: str,
        slack_service: SlackService
    ) -> Tuple[List[Dict[str, str]], bool, str]:
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
                    
                    logger.info("Retrieved conversation from cache", extra={
                        "thread_ts": thread_ts,
                        "channel_id": channel,
                        "message_count": len(messages),
                        "cache_age_seconds": self._get_cache_age(metadata),
                        "event_type": "cache_hit"
                    })
                    
                    return messages, True, "cache"
                    
            except Exception as e:
                logger.warning(f"Cache retrieval failed: {e}. Falling back to Slack API.")
        
        # Fallback to Slack API
        logger.info("Cache miss, fetching from Slack API", extra={
            "thread_ts": thread_ts,
            "channel_id": channel,
            "event_type": "cache_miss"
        })
        
        messages, success = await slack_service.get_thread_history(channel, thread_ts)
        
        # Cache the result if successful and Redis is available
        if success and redis_client and messages:
            try:
                await self._cache_conversation(redis_client, thread_ts, messages)
            except Exception as e:
                logger.warning(f"Failed to cache conversation: {e}")
                
        source = "slack_api" if success else "failed"
        return messages, success, source
        
    async def update_conversation(
        self,
        thread_ts: str,
        new_message: Dict[str, str],
        is_bot_message: bool = False
    ) -> bool:
        """
        Update cached conversation with new message
        Returns: True if cache was updated, False if cache unavailable
        """
        cache_key = self._get_cache_key(thread_ts)
        meta_key = self._get_metadata_key(thread_ts)
        
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
            
            logger.debug("Updated conversation cache", extra={
                "thread_ts": thread_ts,
                "message_count": len(messages),
                "is_bot_message": is_bot_message,
                "event_type": "cache_update"
            })
            
            return True
            
        except Exception as e:
            logger.warning(f"Failed to update conversation cache: {e}")
            return False
            
    async def _cache_conversation(
        self,
        redis_client: redis.Redis,
        thread_ts: str,
        messages: List[Dict[str, str]]
    ):
        """Store conversation and metadata in cache"""
        cache_key = self._get_cache_key(thread_ts)
        meta_key = self._get_metadata_key(thread_ts)
        
        # Store conversation data
        conversation_data = json.dumps(messages)
        await redis_client.setex(cache_key, self.ttl, conversation_data)
        
        # Store metadata
        metadata = {
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "message_count": len(messages),
            "ttl": self.ttl
        }
        meta_data = json.dumps(metadata)
        await redis_client.setex(meta_key, self.ttl, meta_data)
        
    def _get_cache_age(self, metadata: dict) -> int:
        """Calculate cache age in seconds"""
        try:
            cached_at = datetime.fromisoformat(metadata["cached_at"].replace('Z', '+00:00'))
            age = (datetime.now(timezone.utc) - cached_at).total_seconds()
            return int(age)
        except Exception:
            return 0
            
    async def clear_conversation(self, thread_ts: str) -> bool:
        """Clear specific conversation from cache"""
        redis_client = await self._get_redis_client()
        if not redis_client:
            return False
            
        try:
            cache_key = self._get_cache_key(thread_ts)
            meta_key = self._get_metadata_key(thread_ts)
            
            deleted = await redis_client.delete(cache_key, meta_key)
            logger.info(f"Cleared conversation cache for {thread_ts}, deleted {deleted} keys")
            return deleted > 0
            
        except Exception as e:
            logger.warning(f"Failed to clear conversation cache: {e}")
            return False
            
    async def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        redis_client = await self._get_redis_client()
        if not redis_client:
            return {"status": "unavailable"}
            
        try:
            info = await redis_client.info('memory')
            keys = await redis_client.keys("conversation:*")
            
            return {
                "status": "available",
                "memory_used": info.get('used_memory_human', 'unknown'),
                "cached_conversations": len(keys),
                "redis_url": self.redis_url,
                "ttl": self.ttl
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
            
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.aclose()
            self.redis_client = None