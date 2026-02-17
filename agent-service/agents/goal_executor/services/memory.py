"""Goal executor memory service using MinIO.

Provides persistent memory for goal bots at two scopes:

1. **Session-scoped** (run_id): What happened THIS run
   - Searches performed, companies looked at, actions taken
   - Cleared/archived when run completes

2. **Goal-wide** (bot_id): Persistent across ALL runs
   - All companies ever searched
   - Learned patterns, successful signals
   - Aggregate statistics

Usage:
    memory = get_goal_memory(bot_id="prospect_bot", run_id="run_123")

    # Session: track this run's activity
    memory.log_activity("search", {"query": "AI startups", "results": 5})
    memory.get_session_activity()  # ["search: AI startups"]

    # Goal-wide: persist across runs
    memory.add_to_set("companies_searched", "Acme Corp")
    memory.get_set("companies_searched")  # All companies ever searched
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
    "sessions": "goal-executor-sessions",
}


class GoalMemory:
    """Persistent memory for goal executors using MinIO S3.

    Two scopes:
    - Session (run_id): Activity log for current run
    - Goal-wide (bot_id): Persistent across all runs

    Stores:
    - prospects: Saved qualified prospects
    - runs: Run history and results
    - memory: Learned information, context (goal-wide)
    - research: Research artifacts (search results, company profiles)
    - sessions: Activity logs per run (session-scoped)
    """

    def __init__(
        self,
        bot_id: str | None = None,
        thread_id: str | None = None,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
    ):
        """Initialize MinIO memory.

        Args:
            bot_id: Goal bot identifier for namespacing (goal-wide)
            thread_id: LangGraph thread_id for session scoping
                       (from config["configurable"]["thread_id"])
            endpoint_url: MinIO endpoint
            access_key: MinIO access key
            secret_key: MinIO secret key
        """
        self.bot_id = bot_id or "default"
        self.thread_id = thread_id
        self.endpoint_url = endpoint_url or os.getenv("MINIO_ENDPOINT")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY")

        self._client: boto3.client | None = None
        self._initialized = False

        # In-memory session activity (also persisted to MinIO)
        self._session_activity: list[dict[str, Any]] = []

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

    def _key(self, _category: str, name: str) -> str:
        """Generate namespaced key.

        Args:
            _category: Category hint (unused, buckets provide separation)
            name: Key name
        """
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

    # =========================================================================
    # Session-Scoped Memory (thread_id)
    # =========================================================================

    def log_activity(
        self, activity_type: str, data: dict[str, Any], persist: bool = True
    ) -> None:
        """Log an activity for this session/thread.

        Session-scoped: tracks what happened THIS run.

        Args:
            activity_type: Type of activity (search, analyze, save, etc.)
            data: Activity data
            persist: Whether to persist to MinIO (default True)
        """
        activity = {
            "type": activity_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "thread_id": self.thread_id,
        }
        self._session_activity.append(activity)

        if persist and self.thread_id:
            self._persist_session_activity()

    def get_session_activity(
        self, activity_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Get activity log for this session.

        Args:
            activity_type: Optional filter by type

        Returns:
            List of activities (most recent first)
        """
        # Load from MinIO if we have a thread_id and empty local cache
        if self.thread_id and not self._session_activity:
            self._load_session_activity()

        activities = self._session_activity
        if activity_type:
            activities = [a for a in activities if a.get("type") == activity_type]

        return list(reversed(activities))

    def get_session_summary(self) -> dict[str, Any]:
        """Get summary of this session's activity.

        Returns:
            Summary with counts by type, recent items
        """
        activities = self.get_session_activity()
        by_type: dict[str, int] = {}
        for a in activities:
            t = a.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "thread_id": self.thread_id,
            "total_activities": len(activities),
            "by_type": by_type,
            "recent": activities[:5],
        }

    def _persist_session_activity(self) -> None:
        """Persist session activity to MinIO."""
        if not self._ensure_client() or not self.thread_id:
            return

        key = f"{self.bot_id}/threads/{self.thread_id}.json"
        session_data = {
            "thread_id": self.thread_id,
            "bot_id": self.bot_id,
            "activities": self._session_activity,
            "updated_at": datetime.now().isoformat(),
        }

        try:
            self._client.put_object(
                Bucket=BUCKETS["sessions"],
                Key=key,
                Body=json.dumps(session_data, indent=2).encode("utf-8"),
                ContentType="application/json",
            )
        except Exception as e:
            logger.warning(f"Failed to persist session activity: {e}")

    def _load_session_activity(self) -> None:
        """Load session activity from MinIO."""
        if not self._ensure_client() or not self.thread_id:
            return

        key = f"{self.bot_id}/threads/{self.thread_id}.json"

        try:
            data = self._client.get_object(
                Bucket=BUCKETS["sessions"],
                Key=key,
            )
            session_data = json.loads(data["Body"].read().decode("utf-8"))
            self._session_activity = session_data.get("activities", [])
        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchKey":
                logger.warning(f"Failed to load session activity: {e}")
        except Exception as e:
            logger.warning(f"Failed to load session activity: {e}")

    # =========================================================================
    # Goal-Wide Sets (for tracking across all runs)
    # =========================================================================

    def add_to_set(self, set_name: str, value: str) -> bool:
        """Add a value to a goal-wide set.

        Goal-wide: persists across ALL runs for this bot.
        Use for tracking things like "all companies ever searched".

        Args:
            set_name: Name of the set (e.g., "companies_searched")
            value: Value to add

        Returns:
            True if added (False if already existed)
        """
        current = self.get_set(set_name)
        if value in current:
            return False

        current.add(value)
        self.remember(f"set:{set_name}", list(current))
        return True

    def get_set(self, set_name: str) -> set[str]:
        """Get all values in a goal-wide set.

        Args:
            set_name: Name of the set

        Returns:
            Set of values
        """
        values = self.recall(f"set:{set_name}")
        if values is None:
            return set()
        return set(values)

    def is_in_set(self, set_name: str, value: str) -> bool:
        """Check if a value is in a goal-wide set.

        Args:
            set_name: Name of the set
            value: Value to check

        Returns:
            True if value is in the set
        """
        return value in self.get_set(set_name)

    def remove_from_set(self, set_name: str, value: str) -> bool:
        """Remove a value from a goal-wide set.

        Args:
            set_name: Name of the set
            value: Value to remove

        Returns:
            True if removed (False if didn't exist)
        """
        current = self.get_set(set_name)
        if value not in current:
            return False

        current.discard(value)
        self.remember(f"set:{set_name}", list(current))
        return True

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def log_search(self, query: str, results_count: int, source: str = "web") -> None:
        """Log a search activity (session) and track query (goal-wide).

        Args:
            query: Search query
            results_count: Number of results found
            source: Search source
        """
        # Session-scoped: what we searched this run
        self.log_activity(
            "search",
            {"query": query, "results_count": results_count, "source": source},
        )
        # Goal-wide: track all queries ever
        self.add_to_set("queries_searched", query)

    def log_company_researched(
        self, company_name: str, data: dict | None = None
    ) -> None:
        """Log company research (session) and track company (goal-wide).

        Args:
            company_name: Company name
            data: Additional data about the research
        """
        # Session-scoped
        self.log_activity(
            "company_research",
            {"company": company_name, **(data or {})},
        )
        # Goal-wide
        self.add_to_set("companies_researched", company_name)

    def was_company_researched(self, company_name: str) -> bool:
        """Check if a company was ever researched (goal-wide).

        Args:
            company_name: Company name

        Returns:
            True if company was researched in any run
        """
        return self.is_in_set("companies_researched", company_name)

    def get_all_companies_researched(self) -> set[str]:
        """Get all companies ever researched (goal-wide).

        Returns:
            Set of company names
        """
        return self.get_set("companies_researched")

    # =========================================================================
    # Session Compaction (bridges to VectorMemory)
    # =========================================================================

    async def compact_and_archive(
        self,
        outcome: str,
        goal: str | None = None,
    ) -> dict[str, Any]:
        """Compact and archive the current session.

        Call this when a run completes. This:
        1. Gets all session activities
        2. Creates an LLM summary → embeds in Qdrant for semantic search
        3. Saves full session markdown to MinIO for detailed retrieval

        Args:
            outcome: Final outcome/summary of the run
            goal: The goal that was executed

        Returns:
            Dict with archive details (memory_id, activity_count, etc.)
        """
        if not self.thread_id:
            return {"error": "No thread_id - cannot compact session"}

        # Get session activities
        activities = self.get_session_activity()

        # Archive to vector memory
        from .vector_memory import get_vector_memory

        vector_memory = get_vector_memory(self.bot_id)
        memory_id = await vector_memory.compact_session(
            thread_id=self.thread_id,
            activities=activities,
            outcome=outcome,
            goal=goal,
        )

        # Also save full session to MinIO
        self._persist_session_activity()

        # Save run record
        self.save_run(
            run_id=self.thread_id,
            run_data={
                "goal": goal,
                "outcome": outcome,
                "activity_count": len(activities),
                "memory_id": memory_id,
            },
        )

        return {
            "thread_id": self.thread_id,
            "memory_id": memory_id,
            "activity_count": len(activities),
            "archived": True,
        }

    async def search_past_runs(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Semantic search across past session summaries.

        Args:
            query: Natural language query (e.g., "companies with funding")
            limit: Maximum results

        Returns:
            List of matching past sessions
        """
        from .vector_memory import get_vector_memory

        vector_memory = get_vector_memory(self.bot_id)
        return await vector_memory.search(query, limit=limit)


# Singleton instances by bot_id (goal-wide instances without thread_id)
_memory_instances: dict[str, GoalMemory] = {}


def get_goal_memory(
    bot_id: str = "default", thread_id: str | None = None
) -> GoalMemory:
    """Get or create GoalMemory instance.

    For goal-wide operations (no session tracking), omit thread_id.
    For session-scoped operations, pass thread_id from LangGraph config.

    Args:
        bot_id: Bot identifier (goal-wide scope)
        thread_id: LangGraph thread_id for session scope
                   (from config["configurable"]["thread_id"])

    Returns:
        GoalMemory instance

    Example:
        # In a LangGraph node:
        def my_node(state, config):
            thread_id = config["configurable"].get("thread_id")
            memory = get_goal_memory(bot_id="prospect_bot", thread_id=thread_id)

            # Session-scoped
            memory.log_search("AI startups", results_count=5)

            # Goal-wide
            if memory.was_company_researched("Acme Corp"):
                # Skip, already researched in a previous run
                pass
    """
    # If thread_id provided, create a new instance (session-scoped)
    if thread_id:
        return GoalMemory(bot_id=bot_id, thread_id=thread_id)

    # Otherwise use singleton (goal-wide only)
    if bot_id not in _memory_instances:
        _memory_instances[bot_id] = GoalMemory(bot_id=bot_id)
    return _memory_instances[bot_id]
