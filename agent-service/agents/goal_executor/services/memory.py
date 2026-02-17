"""Goal executor memory service using MinIO.

Provides persistent memory for goal bots:
- Run history and results
- Saved prospects
- Learned information across runs
- Research artifacts
"""

import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# MinIO buckets for goal executor
BUCKETS = {
    "prospects": "goal-executor-prospects",
    "runs": "goal-executor-runs",
    "memory": "goal-executor-memory",
    "research": "goal-executor-research",
}


class GoalMemory:
    """Persistent memory for goal executors using MinIO S3.

    Stores:
    - prospects: Saved qualified prospects
    - runs: Run history and results
    - memory: Learned information, context
    - research: Research artifacts (search results, company profiles)
    """

    def __init__(
        self,
        bot_id: str | None = None,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
    ):
        """Initialize MinIO memory.

        Args:
            bot_id: Goal bot identifier for namespacing
            endpoint_url: MinIO endpoint
            access_key: MinIO access key
            secret_key: MinIO secret key
        """
        self.bot_id = bot_id or "default"
        self.endpoint_url = endpoint_url or os.getenv("MINIO_ENDPOINT")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY")

        self._client: boto3.client | None = None
        self._initialized = False

    def _ensure_client(self) -> bool:
        """Ensure S3 client is initialized."""
        if self._initialized:
            return self._client is not None

        self._initialized = True

        if not self.endpoint_url or not self.access_key or not self.secret_key:
            logger.warning("MinIO not configured, memory will not persist")
            return False

        try:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name="us-east-1",
            )
            self._client.list_buckets()
            self._ensure_buckets()
            logger.info(f"GoalMemory connected to MinIO: {self.endpoint_url}")
            return True
        except Exception as e:
            logger.warning(f"MinIO connection failed: {e}")
            self._client = None
            return False

    def _ensure_buckets(self) -> None:
        """Create required buckets."""
        if not self._client:
            return

        for bucket in BUCKETS.values():
            try:
                self._client.head_bucket(Bucket=bucket)
            except ClientError:
                try:
                    self._client.create_bucket(Bucket=bucket)
                    logger.info(f"Created bucket: {bucket}")
                except Exception as e:
                    logger.error(f"Failed to create bucket {bucket}: {e}")

    def _key(self, category: str, name: str) -> str:
        """Generate namespaced key."""
        return f"{self.bot_id}/{name}"

    # =========================================================================
    # Prospect Storage
    # =========================================================================

    def save_prospect(self, prospect: dict[str, Any]) -> str | None:
        """Save a qualified prospect to MinIO.

        Args:
            prospect: Prospect data dict

        Returns:
            Prospect ID or None if save failed
        """
        if not self._ensure_client():
            logger.info(f"PROSPECT (not persisted): {json.dumps(prospect, indent=2)}")
            return None

        company = prospect.get("company_name", "unknown")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prospect_id = hashlib.md5(f"{company}_{timestamp}".encode()).hexdigest()[:12]

        prospect["prospect_id"] = prospect_id
        prospect["saved_at"] = datetime.now().isoformat()
        prospect["bot_id"] = self.bot_id

        key = self._key(
            "prospects", f"{prospect_id}_{company.lower().replace(' ', '_')}.json"
        )

        try:
            self._client.put_object(
                Bucket=BUCKETS["prospects"],
                Key=key,
                Body=json.dumps(prospect, indent=2).encode("utf-8"),
                ContentType="application/json",
            )
            logger.info(f"Saved prospect to MinIO: {key}")
            return prospect_id
        except Exception as e:
            logger.error(f"Failed to save prospect: {e}")
            return None

    def list_prospects(self, limit: int = 50) -> list[dict[str, Any]]:
        """List saved prospects.

        Args:
            limit: Max prospects to return

        Returns:
            List of prospect dicts
        """
        if not self._ensure_client():
            return []

        prospects = []
        prefix = f"{self.bot_id}/"

        try:
            response = self._client.list_objects_v2(
                Bucket=BUCKETS["prospects"],
                Prefix=prefix,
                MaxKeys=limit,
            )

            for obj in response.get("Contents", []):
                try:
                    data = self._client.get_object(
                        Bucket=BUCKETS["prospects"],
                        Key=obj["Key"],
                    )
                    prospect = json.loads(data["Body"].read().decode("utf-8"))
                    prospects.append(prospect)
                except Exception as e:
                    logger.warning(f"Error loading prospect {obj['Key']}: {e}")

            return prospects
        except Exception as e:
            logger.error(f"Failed to list prospects: {e}")
            return []

    # =========================================================================
    # Run History
    # =========================================================================

    def save_run(self, run_id: str, run_data: dict[str, Any]) -> bool:
        """Save run history to MinIO.

        Args:
            run_id: Run identifier
            run_data: Run data (status, results, etc.)

        Returns:
            True if saved successfully
        """
        if not self._ensure_client():
            return False

        run_data["run_id"] = run_id
        run_data["bot_id"] = self.bot_id
        run_data["saved_at"] = datetime.now().isoformat()

        key = self._key("runs", f"{run_id}.json")

        try:
            self._client.put_object(
                Bucket=BUCKETS["runs"],
                Key=key,
                Body=json.dumps(run_data, indent=2).encode("utf-8"),
                ContentType="application/json",
            )
            logger.info(f"Saved run to MinIO: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to save run: {e}")
            return False

    def get_recent_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent run history.

        Args:
            limit: Max runs to return

        Returns:
            List of run dicts (most recent first)
        """
        if not self._ensure_client():
            return []

        runs = []
        prefix = f"{self.bot_id}/"

        try:
            response = self._client.list_objects_v2(
                Bucket=BUCKETS["runs"],
                Prefix=prefix,
                MaxKeys=limit,
            )

            for obj in sorted(
                response.get("Contents", []),
                key=lambda x: x["LastModified"],
                reverse=True,
            ):
                try:
                    data = self._client.get_object(
                        Bucket=BUCKETS["runs"],
                        Key=obj["Key"],
                    )
                    run = json.loads(data["Body"].read().decode("utf-8"))
                    runs.append(run)
                except Exception as e:
                    logger.warning(f"Error loading run {obj['Key']}: {e}")

            return runs[:limit]
        except Exception as e:
            logger.error(f"Failed to list runs: {e}")
            return []

    # =========================================================================
    # Long-term Memory
    # =========================================================================

    def remember(self, key: str, value: Any) -> bool:
        """Store a piece of information in long-term memory.

        Args:
            key: Memory key (e.g., "learned_icp", "successful_signals")
            value: Value to store

        Returns:
            True if stored successfully
        """
        if not self._ensure_client():
            return False

        memory_key = self._key("memory", f"{key}.json")

        memory_data = {
            "key": key,
            "value": value,
            "updated_at": datetime.now().isoformat(),
            "bot_id": self.bot_id,
        }

        try:
            self._client.put_object(
                Bucket=BUCKETS["memory"],
                Key=memory_key,
                Body=json.dumps(memory_data, indent=2).encode("utf-8"),
                ContentType="application/json",
            )
            logger.info(f"Remembered: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to remember {key}: {e}")
            return False

    def recall(self, key: str) -> Any | None:
        """Recall information from long-term memory.

        Args:
            key: Memory key

        Returns:
            Stored value or None
        """
        if not self._ensure_client():
            return None

        memory_key = self._key("memory", f"{key}.json")

        try:
            data = self._client.get_object(
                Bucket=BUCKETS["memory"],
                Key=memory_key,
            )
            memory_data = json.loads(data["Body"].read().decode("utf-8"))
            return memory_data.get("value")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            logger.error(f"Failed to recall {key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to recall {key}: {e}")
            return None

    def recall_all(self) -> dict[str, Any]:
        """Recall all memories for this bot.

        Returns:
            Dict of all memories
        """
        if not self._ensure_client():
            return {}

        memories = {}
        prefix = f"{self.bot_id}/"

        try:
            response = self._client.list_objects_v2(
                Bucket=BUCKETS["memory"],
                Prefix=prefix,
            )

            for obj in response.get("Contents", []):
                try:
                    data = self._client.get_object(
                        Bucket=BUCKETS["memory"],
                        Key=obj["Key"],
                    )
                    memory_data = json.loads(data["Body"].read().decode("utf-8"))
                    memories[memory_data["key"]] = memory_data["value"]
                except Exception as e:
                    logger.warning(f"Error loading memory {obj['Key']}: {e}")

            return memories
        except Exception as e:
            logger.error(f"Failed to recall all: {e}")
            return {}

    # =========================================================================
    # Research Cache
    # =========================================================================

    def cache_research(self, query: str, results: str, source: str = "web") -> bool:
        """Cache research results.

        Args:
            query: Search query
            results: Search results
            source: Source of results (web, perplexity, hubspot)

        Returns:
            True if cached successfully
        """
        if not self._ensure_client():
            return False

        query_hash = hashlib.md5(query.encode()).hexdigest()[:12]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        key = self._key("research", f"{source}_{query_hash}_{timestamp}.json")

        cache_data = {
            "query": query,
            "results": results,
            "source": source,
            "cached_at": datetime.now().isoformat(),
            "bot_id": self.bot_id,
        }

        try:
            self._client.put_object(
                Bucket=BUCKETS["research"],
                Key=key,
                Body=json.dumps(cache_data, indent=2).encode("utf-8"),
                ContentType="application/json",
            )
            return True
        except Exception as e:
            logger.error(f"Failed to cache research: {e}")
            return False

    def search_research_cache(
        self, query: str, source: str | None = None
    ) -> list[dict]:
        """Search cached research.

        Args:
            query: Search term
            source: Optional source filter

        Returns:
            List of matching cached results
        """
        if not self._ensure_client():
            return []

        results = []
        prefix = f"{self.bot_id}/"
        query_lower = query.lower()

        try:
            response = self._client.list_objects_v2(
                Bucket=BUCKETS["research"],
                Prefix=prefix,
            )

            for obj in response.get("Contents", []):
                try:
                    data = self._client.get_object(
                        Bucket=BUCKETS["research"],
                        Key=obj["Key"],
                    )
                    cache_data = json.loads(data["Body"].read().decode("utf-8"))

                    # Filter by source if specified
                    if source and cache_data.get("source") != source:
                        continue

                    # Match by query content
                    if query_lower in cache_data.get("query", "").lower():
                        results.append(cache_data)

                except Exception as e:
                    logger.warning(f"Error loading cache {obj['Key']}: {e}")

            return results
        except Exception as e:
            logger.error(f"Failed to search research cache: {e}")
            return []


# Singleton instance
_memory_instances: dict[str, GoalMemory] = {}


def get_goal_memory(bot_id: str = "default") -> GoalMemory:
    """Get or create GoalMemory instance for bot.

    Args:
        bot_id: Bot identifier

    Returns:
        GoalMemory instance
    """
    if bot_id not in _memory_instances:
        _memory_instances[bot_id] = GoalMemory(bot_id=bot_id)
    return _memory_instances[bot_id]
