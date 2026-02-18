"""Vector memory service for goal executors using Qdrant.

Provides semantic search over goal bot memories following the OpenClaw pattern:

1. **Session compaction**: When a run completes, LLM summarizes key findings
   and embeds them for future semantic search.

2. **Hybrid search**: Combines vector similarity + BM25 keyword matching
   for both semantic understanding and exact token matches.

3. **Temporal decay**: Recent findings rank higher (30-day half-life).

4. **MMR re-ranking**: Maximal Marginal Relevance reduces duplicate results.

Architecture:
    Session ends → LLM summarizes → Embed summary → Store in Qdrant
                                                  → Full markdown in MinIO

    Search query → Vector search (semantic)
                → BM25 search (keywords)
                → Weighted merge
                → Temporal decay
                → MMR diversity
                → Top-K results

Usage:
    memory = VectorMemory(bot_id="prospect_bot")

    # Compact session when done
    await memory.compact_session(
        thread_id="abc123",
        activities=[...],  # From GoalMemory.get_session_activity()
        outcome="Found 3 qualified prospects in AI infrastructure"
    )

    # Hybrid search across all past runs
    results = await memory.search(
        "companies with recent funding rounds",
        use_hybrid=True,   # BM25 + vector
        use_mmr=True,      # Diversity re-ranking
    )
"""

import asyncio
import hashlib
import logging
import math
import os
import uuid
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Collection name for goal bot memories
GOAL_MEMORY_COLLECTION = "goal-bot-memories"


class VectorMemory:
    """Semantic memory for goal executors using Qdrant.

    Stores session summaries as embeddings for semantic retrieval.
    Full session details remain in MinIO for detailed access.
    """

    def __init__(
        self,
        bot_id: str = "default",
        qdrant_host: str | None = None,
        qdrant_port: int | None = None,
        openai_api_key: str | None = None,
    ):
        """Initialize vector memory.

        Args:
            bot_id: Goal bot identifier for filtering
            qdrant_host: Qdrant host (default from env)
            qdrant_port: Qdrant port (default from env)
            openai_api_key: OpenAI API key for embeddings/summarization
        """
        self.bot_id = bot_id
        self.qdrant_host = qdrant_host or os.getenv("QDRANT_HOST", "localhost")
        self.qdrant_port = qdrant_port or int(os.getenv("QDRANT_PORT", "6333"))
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

        self._client = None
        self._embedding_provider = None
        self._initialized = False

        # Temporal decay settings (30-day half-life like OpenClaw)
        self.decay_half_life_days = 30

        # Hybrid search weights (OpenClaw defaults)
        self.vector_weight = 0.7  # Semantic similarity
        self.text_weight = 0.3  # BM25 keyword relevance

        # MMR settings (lambda=0.7 balances relevance vs diversity)
        self.mmr_lambda = 0.7  # 1.0 = pure relevance, 0.0 = max diversity

    async def _ensure_initialized(self) -> bool:
        """Ensure Qdrant client and embedding provider are ready."""
        if self._initialized:
            return self._client is not None

        self._initialized = True

        try:
            # Import Qdrant
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            # Initialize Qdrant client
            self._client = QdrantClient(
                host=self.qdrant_host,
                port=self.qdrant_port,
                timeout=60,
            )

            # Create collection if needed
            collections = self._client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if GOAL_MEMORY_COLLECTION not in collection_names:
                self._client.create_collection(
                    collection_name=GOAL_MEMORY_COLLECTION,
                    vectors_config=VectorParams(
                        size=1536,  # text-embedding-3-small dimensions
                        distance=Distance.COSINE,
                    ),
                )
                logger.info(f"Created Qdrant collection: {GOAL_MEMORY_COLLECTION}")

            # Initialize embedding provider
            from config.settings import EmbeddingSettings
            from services.embedding import create_embedding_provider

            embedding_settings = EmbeddingSettings()
            self._embedding_provider = create_embedding_provider(embedding_settings)

            logger.info(
                f"VectorMemory initialized for {self.bot_id} "
                f"(Qdrant: {self.qdrant_host}:{self.qdrant_port})"
            )
            return True

        except ImportError as e:
            logger.warning(f"Qdrant not available: {e}")
            return False
        except Exception as e:
            logger.warning(f"VectorMemory initialization failed: {e}")
            self._client = None
            return False

    # =========================================================================
    # Session Compaction
    # =========================================================================

    async def compact_session(
        self,
        thread_id: str,
        activities: list[dict[str, Any]],
        outcome: str,
        goal: str | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Compact a session into a searchable summary.

        Called when a run completes. Uses LLM to summarize key findings,
        then embeds and stores for future semantic search.

        Args:
            thread_id: LangGraph thread_id for this session
            activities: Session activities from GoalMemory.get_session_activity()
            outcome: Final outcome/summary of the run
            goal: The goal that was executed
            extra_metadata: Additional metadata to store

        Returns:
            Memory ID if stored successfully, None otherwise
        """
        if not await self._ensure_initialized():
            logger.info(f"COMPACT (not persisted): {outcome[:100]}...")
            return None

        # Generate summary using LLM
        summary = await self._generate_summary(activities, outcome, goal)
        if not summary:
            logger.warning("Failed to generate session summary")
            return None

        # Generate embedding
        embedding = await self._embed_text(summary)
        if not embedding:
            logger.warning("Failed to embed session summary")
            return None

        # Store in Qdrant
        memory_id = self._generate_memory_id(thread_id, outcome)

        try:
            from qdrant_client.models import PointStruct

            # Build metadata
            metadata = {
                "bot_id": self.bot_id,
                "thread_id": thread_id,
                "summary": summary,
                "outcome": outcome,
                "goal": goal or "",
                "activity_count": len(activities),
                "created_at": datetime.now().isoformat(),
                "type": "session_summary",
                **(extra_metadata or {}),
            }

            # Extract searchable entities from activities
            companies = set()
            queries = set()
            for activity in activities:
                data = activity.get("data", {})
                if "company" in data:
                    companies.add(data["company"])
                if "query" in data:
                    queries.add(data["query"])

            metadata["companies"] = list(companies)
            metadata["queries"] = list(queries)

            point = PointStruct(
                id=memory_id,
                vector=embedding,
                payload=metadata,
            )

            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.upsert(
                    collection_name=GOAL_MEMORY_COLLECTION,
                    points=[point],
                ),
            )

            logger.info(
                f"Compacted session {thread_id} → memory {memory_id} "
                f"({len(activities)} activities, {len(companies)} companies)"
            )
            return memory_id

        except Exception as e:
            logger.error(f"Failed to store session summary: {e}")
            return None

    async def _generate_summary(
        self,
        activities: list[dict[str, Any]],
        outcome: str,
        goal: str | None,
    ) -> str | None:
        """Generate a concise summary of the session using LLM.

        Args:
            activities: Session activities
            outcome: Final outcome
            goal: The goal

        Returns:
            Summary text or None if failed
        """
        if not self.openai_api_key:
            # Fallback: create a simple summary without LLM
            return self._simple_summary(activities, outcome, goal)

        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self.openai_api_key)

            # Build activity summary
            activity_lines = []
            for a in activities[:20]:  # Limit to recent activities
                activity_type = a.get("type", "unknown")
                data = a.get("data", {})
                if activity_type == "search":
                    activity_lines.append(f"- Searched: {data.get('query', '?')}")
                elif activity_type == "company_research":
                    activity_lines.append(f"- Researched: {data.get('company', '?')}")
                elif activity_type == "save":
                    activity_lines.append(f"- Saved: {data.get('type', 'item')}")
                else:
                    activity_lines.append(f"- {activity_type}: {str(data)[:50]}")

            activities_text = (
                "\n".join(activity_lines) if activity_lines else "No activities logged"
            )

            prompt = f"""Summarize this goal bot session in 2-3 sentences for future semantic search.
Focus on: key findings, companies researched, patterns discovered, outcome achieved.

Goal: {goal or "Not specified"}

Activities:
{activities_text}

Outcome: {outcome}

Write a concise summary that would help find this session when searching for related topics."""

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.warning(f"LLM summarization failed: {e}")
            return self._simple_summary(activities, outcome, goal)

    def _simple_summary(
        self,
        activities: list[dict[str, Any]],
        outcome: str,
        goal: str | None,
    ) -> str:
        """Generate a simple summary without LLM."""
        parts = []

        if goal:
            parts.append(f"Goal: {goal}")

        # Extract key entities
        companies = set()
        searches = set()
        for a in activities:
            data = a.get("data", {})
            if "company" in data:
                companies.add(data["company"])
            if "query" in data:
                searches.add(data["query"])

        if companies:
            parts.append(f"Companies: {', '.join(list(companies)[:5])}")
        if searches:
            parts.append(f"Searches: {', '.join(list(searches)[:5])}")

        parts.append(f"Outcome: {outcome}")

        return " | ".join(parts)

    async def _embed_text(self, text: str) -> list[float] | None:
        """Generate embedding for text."""
        if not self._embedding_provider:
            return None

        try:
            embedding = await self._embedding_provider.get_embedding(text)
            return embedding
        except Exception as e:
            logger.warning(f"Embedding failed: {e}")
            return None

    def _generate_memory_id(self, thread_id: str, content: str) -> str:
        """Generate a deterministic UUID for a memory."""
        hash_input = f"{self.bot_id}:{thread_id}:{content}"
        hash_hex = hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest()
        return str(uuid.UUID(hash_hex))

    # =========================================================================
    # Hybrid Search (Vector + BM25 + MMR)
    # =========================================================================

    async def search(
        self,
        query: str,
        limit: int = 10,
        include_other_bots: bool = False,
        apply_temporal_decay: bool = True,
        use_hybrid: bool = True,
        use_mmr: bool = True,
        min_score: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Hybrid search across past session summaries.

        Combines vector similarity with BM25 keyword matching,
        applies temporal decay, and uses MMR for diversity.

        Pipeline:
            Vector search → BM25 scoring → Weighted merge
            → Temporal decay → MMR re-ranking → Top-K

        Args:
            query: Natural language query
            limit: Maximum results
            include_other_bots: Search across all bots (default: only this bot)
            apply_temporal_decay: Apply recency boost (default: True)
            use_hybrid: Combine vector + BM25 (default: True)
            use_mmr: Apply MMR diversity re-ranking (default: True)
            min_score: Minimum combined score

        Returns:
            List of matching memories with metadata
        """
        if not await self._ensure_initialized():
            return []

        # Embed query for vector search
        query_embedding = await self._embed_text(query)
        if not query_embedding:
            return []

        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            # Build filter
            query_filter = None
            if not include_other_bots:
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="bot_id",
                            match=MatchValue(value=self.bot_id),
                        )
                    ]
                )

            # Get more candidates for hybrid/MMR processing
            candidate_limit = limit * 4 if (use_hybrid or use_mmr) else limit * 2

            # Vector search
            results = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: (
                    self._client.query_points(
                        collection_name=GOAL_MEMORY_COLLECTION,
                        query=query_embedding,
                        limit=candidate_limit,
                        query_filter=query_filter,
                        with_payload=True,
                        with_vectors=False,
                    ).points
                ),
            )

            # Build candidate list with scores
            candidates = []
            query_tokens = self._tokenize(query)

            for point in results:
                payload = point.payload or {}
                vector_score = point.score

                # Calculate BM25 text score if hybrid
                text_score = 0.0
                if use_hybrid:
                    searchable_text = " ".join(
                        [
                            payload.get("summary", ""),
                            payload.get("outcome", ""),
                            payload.get("goal", ""),
                            " ".join(payload.get("companies", [])),
                            " ".join(payload.get("queries", [])),
                        ]
                    )
                    text_score = self._bm25_score(query_tokens, searchable_text)

                # Combine scores
                if use_hybrid and text_score > 0:
                    combined_score = (
                        self.vector_weight * vector_score
                        + self.text_weight * text_score
                    )
                else:
                    combined_score = vector_score

                # Apply temporal decay
                if apply_temporal_decay:
                    created_at = payload.get("created_at")
                    if created_at:
                        combined_score = self._apply_decay(combined_score, created_at)

                if combined_score < min_score:
                    continue

                candidates.append(
                    {
                        "id": point.id,
                        "score": combined_score,
                        "vector_score": vector_score,
                        "text_score": text_score,
                        "summary": payload.get("summary", ""),
                        "outcome": payload.get("outcome", ""),
                        "goal": payload.get("goal", ""),
                        "thread_id": payload.get("thread_id", ""),
                        "bot_id": payload.get("bot_id", ""),
                        "companies": payload.get("companies", []),
                        "queries": payload.get("queries", []),
                        "created_at": payload.get("created_at", ""),
                        "activity_count": payload.get("activity_count", 0),
                    }
                )

            # Sort by combined score
            candidates.sort(key=lambda x: x["score"], reverse=True)

            # Apply MMR re-ranking for diversity
            if use_mmr and len(candidates) > limit:
                candidates = self._mmr_rerank(candidates, limit)
            else:
                candidates = candidates[:limit]

            return candidates

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def _apply_decay(self, score: float, created_at: str) -> float:
        """Apply temporal decay to score based on age.

        Uses exponential decay with configurable half-life:
        decayed_score = score * e^(-λ * age_days)
        where λ = ln(2) / half_life_days

        Args:
            score: Original similarity score
            created_at: ISO timestamp

        Returns:
            Decayed score
        """
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            now = datetime.now(created.tzinfo) if created.tzinfo else datetime.now()
            age_days = (now - created).days

            # Calculate decay factor
            lambda_decay = math.log(2) / self.decay_half_life_days
            decay_factor = math.exp(-lambda_decay * age_days)

            return score * decay_factor
        except Exception:
            return score

    def _tokenize(self, text: str) -> set[str]:
        """Tokenize text for BM25 scoring.

        Simple whitespace tokenization with lowercasing and filtering.

        Args:
            text: Text to tokenize

        Returns:
            Set of tokens
        """
        import re

        # Lowercase and split on non-alphanumeric
        tokens = re.findall(r"\b[a-z0-9]+\b", text.lower())
        # Filter short tokens and stopwords
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
        }
        return {t for t in tokens if len(t) > 2 and t not in stopwords}

    def _bm25_score(
        self,
        query_tokens: set[str],
        document: str,
        k1: float = 1.5,
        b: float = 0.75,
        avg_doc_len: float = 100.0,
    ) -> float:
        """Calculate BM25 relevance score.

        Simplified BM25 without IDF (single document context).
        Uses term frequency with length normalization.

        Args:
            query_tokens: Tokenized query terms
            document: Document text to score
            k1: Term frequency saturation parameter
            b: Length normalization parameter
            avg_doc_len: Average document length estimate

        Returns:
            BM25 score (0.0 to ~1.0 normalized)
        """
        if not query_tokens or not document:
            return 0.0

        doc_tokens = self._tokenize(document)
        doc_len = len(doc_tokens)

        if doc_len == 0:
            return 0.0

        # Count term frequencies
        term_freq: dict[str, int] = {}
        for token in doc_tokens:
            term_freq[token] = term_freq.get(token, 0) + 1

        # Calculate BM25 score
        score = 0.0
        for term in query_tokens:
            if term in term_freq:
                tf = term_freq[term]
                # BM25 term score (simplified without IDF)
                numerator = tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * (doc_len / avg_doc_len))
                score += numerator / denominator

        # Normalize to 0-1 range (divide by query length)
        normalized = score / len(query_tokens) if query_tokens else 0.0

        # Cap at 1.0
        return min(normalized, 1.0)

    def _mmr_rerank(
        self,
        candidates: list[dict[str, Any]],
        limit: int,
    ) -> list[dict[str, Any]]:
        """Apply Maximal Marginal Relevance re-ranking for diversity.

        Iteratively selects items that balance relevance with diversity
        from already-selected items.

        Score: λ * relevance - (1-λ) * max_similarity_to_selected

        Args:
            candidates: List of candidate results with scores
            limit: Number of results to return

        Returns:
            Re-ranked list with diversity
        """
        if len(candidates) <= limit:
            return candidates

        selected: list[dict[str, Any]] = []
        remaining = candidates.copy()

        # Select first item (highest relevance)
        if remaining:
            selected.append(remaining.pop(0))

        while len(selected) < limit and remaining:
            best_idx = 0
            best_mmr_score = float("-inf")

            for i, candidate in enumerate(remaining):
                relevance = candidate["score"]

                # Calculate max similarity to selected items
                max_sim = 0.0
                candidate_text = candidate.get("summary", "")
                for sel in selected:
                    sel_text = sel.get("summary", "")
                    sim = self._jaccard_similarity(candidate_text, sel_text)
                    max_sim = max(max_sim, sim)

                # MMR score
                mmr_score = (
                    self.mmr_lambda * relevance - (1 - self.mmr_lambda) * max_sim
                )

                if mmr_score > best_mmr_score:
                    best_mmr_score = mmr_score
                    best_idx = i

            selected.append(remaining.pop(best_idx))

        return selected

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """Calculate Jaccard similarity between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Jaccard similarity (0.0 to 1.0)
        """
        tokens1 = self._tokenize(text1)
        tokens2 = self._tokenize(text2)

        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return intersection / union if union > 0 else 0.0

    # =========================================================================
    # Memory Management
    # =========================================================================

    async def get_recent_memories(
        self,
        limit: int = 10,
        days: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent memories for this bot.

        Args:
            limit: Maximum results
            days: Only include memories from last N days

        Returns:
            List of recent memories
        """
        if not await self._ensure_initialized():
            return []

        try:
            from qdrant_client.models import (
                FieldCondition,
                Filter,
                MatchValue,
            )

            conditions = [
                FieldCondition(
                    key="bot_id",
                    match=MatchValue(value=self.bot_id),
                )
            ]

            # Note: Date filtering happens in Python after retrieval
            # since Qdrant doesn't support date ranges on string fields

            query_filter = Filter(must=conditions)

            # Scroll through points (no vector query needed)
            results = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.scroll(
                    collection_name=GOAL_MEMORY_COLLECTION,
                    scroll_filter=query_filter,
                    limit=limit * 2,  # Get extra for date filtering
                    with_payload=True,
                    with_vectors=False,
                )[0],  # scroll returns (points, next_offset)
            )

            memories = []
            for point in results:
                payload = point.payload or {}

                # Date filter in Python
                if days:
                    created_at = payload.get("created_at")
                    if created_at:
                        created = datetime.fromisoformat(
                            created_at.replace("Z", "+00:00")
                        )
                        now = (
                            datetime.now(created.tzinfo)
                            if created.tzinfo
                            else datetime.now()
                        )
                        if (now - created).days > days:
                            continue

                memories.append(
                    {
                        "id": point.id,
                        "summary": payload.get("summary", ""),
                        "outcome": payload.get("outcome", ""),
                        "goal": payload.get("goal", ""),
                        "thread_id": payload.get("thread_id", ""),
                        "companies": payload.get("companies", []),
                        "created_at": payload.get("created_at", ""),
                    }
                )

            # Sort by created_at descending
            memories.sort(
                key=lambda x: x.get("created_at", ""),
                reverse=True,
            )

            return memories[:limit]

        except Exception as e:
            logger.error(f"Failed to get recent memories: {e}")
            return []

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a specific memory.

        Args:
            memory_id: Memory ID to delete

        Returns:
            True if deleted
        """
        if not await self._ensure_initialized():
            return False

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.delete(
                    collection_name=GOAL_MEMORY_COLLECTION,
                    points_selector=[memory_id],
                ),
            )
            logger.info(f"Deleted memory: {memory_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return False

    async def get_stats(self) -> dict[str, Any]:
        """Get memory statistics for this bot."""
        if not await self._ensure_initialized():
            return {"error": "Not initialized"}

        try:
            # Count memories for this bot
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="bot_id",
                        match=MatchValue(value=self.bot_id),
                    )
                ]
            )

            count = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: (
                    self._client.count(
                        collection_name=GOAL_MEMORY_COLLECTION,
                        count_filter=query_filter,
                    ).count
                ),
            )

            return {
                "bot_id": self.bot_id,
                "memory_count": count,
                "collection": GOAL_MEMORY_COLLECTION,
            }
        except Exception as e:
            return {"error": str(e)}


# Factory function
_vector_memory_instances: dict[str, VectorMemory] = {}


def get_vector_memory(bot_id: str = "default") -> VectorMemory:
    """Get or create VectorMemory instance for a bot.

    Args:
        bot_id: Bot identifier

    Returns:
        VectorMemory instance
    """
    if bot_id not in _vector_memory_instances:
        _vector_memory_instances[bot_id] = VectorMemory(bot_id=bot_id)
    return _vector_memory_instances[bot_id]
