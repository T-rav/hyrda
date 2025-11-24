"""
Prometheus Metrics Service

Provides application-level metrics collection for monitoring and observability.
Integrates with the existing Prometheus monitoring stack.
"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Optional Prometheus client import
try:
    from prometheus_client import (  # type: ignore[reportMissingImports]
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    _prometheus_available = True
    logger.info("Prometheus client available")
except ImportError:
    logger.warning("Prometheus client not available - metrics will be disabled")
    _prometheus_available = False


class MetricsService:
    """
    Service for collecting and exposing Prometheus metrics
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled and _prometheus_available

        # Track active conversations with timestamps
        self._active_conversations = {}  # conversation_id -> last_activity_time
        self._conversation_timeout = timedelta(days=7)

        # Track RAG stats for dashboard (in-memory counters)
        self._rag_stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "total_documents_used": 0,
            "avg_chunks_per_query": 0.0,
            "last_reset": datetime.now(),
        }

        # Track agent invocation stats (in-memory counters)
        self._agent_stats = {
            "total_invocations": 0,
            "successful_invocations": 0,
            "failed_invocations": 0,
            "by_agent": {},  # agent_name -> count
            "last_reset": datetime.now(),
        }

        if not self.enabled:
            return

        # Business metrics
        self.messages_processed = Counter(
            "slack_messages_total",
            "Total number of Slack messages processed",
            ["user_id", "channel_type"],
        )

        self.rag_retrievals = Counter(
            "rag_retrievals_total",
            "Total number of RAG retrievals performed",
            ["provider", "entity_filter"],
        )

        self.llm_requests = Counter(
            "llm_requests_total",
            "Total number of LLM API requests",
            ["provider", "model", "status"],
        )

        self.agent_invocations = Counter(
            "agent_invocations_total",
            "Total number of agent invocations",
            ["agent_name", "status"],  # status: success, error
        )

        # Performance metrics
        self.request_duration = Histogram(
            "request_duration_seconds",
            "Request processing duration",
            ["endpoint", "method"],
            buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 100.0),
        )

        self.rag_duration = Histogram(
            "rag_operation_duration_seconds",
            "RAG operation duration",
            ["operation_type", "provider"],
            buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
        )

        self.llm_duration = Histogram(
            "llm_request_duration_seconds",
            "LLM API request duration",
            ["provider", "model"],
            buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0),
        )

        self.agent_duration = Histogram(
            "agent_invocation_duration_seconds",
            "Agent invocation duration",
            ["agent_name"],
            buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 100.0, 200.0),
        )

        # System metrics
        self.active_conversations = Gauge(
            "active_conversations", "Number of active conversation threads"
        )

        self.cache_operations = Counter(
            "cache_operations_total", "Total cache operations", ["operation", "status"]
        )

        self.cache_hit_rate = Gauge("cache_hit_rate", "Cache hit rate percentage")

        # Quality metrics
        self.retrieval_quality = Histogram(
            "retrieval_similarity_score",
            "Average similarity scores from retrievals",
            buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
        )

        self.response_tokens = Histogram(
            "response_token_count",
            "Token count in LLM responses",
            ["provider", "model"],
            buckets=(50, 100, 250, 500, 1000, 2000, 4000, 8000),
        )

        # RAG-specific metrics
        self.rag_hits_vs_misses = Counter(
            "rag_query_results_total",
            "RAG queries with results found vs no results",
            ["result_type", "provider"],  # result_type: hit, miss, error
        )

        self.rag_document_usage = Counter(
            "rag_documents_retrieved_total",
            "Documents retrieved and used in responses",
            ["document_type", "source"],
        )

        self.rag_query_types = Counter(
            "rag_query_types_total",
            "Types of queries processed",
            [
                "query_category",
                "has_context",
            ],  # query_category: question, command, conversation
        )

        self.user_satisfaction = Counter(
            "user_interactions_total",
            "User interaction patterns",
            [
                "interaction_type",
                "user_type",
            ],  # interaction_type: follow_up, new_topic, error_report
        )

        # Advanced RAG metrics
        self.retrieval_chunk_count = Histogram(
            "rag_chunks_retrieved_count",
            "Number of chunks retrieved per query",
            buckets=(0, 1, 2, 3, 5, 10, 15, 20, 30),
        )

        self.document_diversity = Histogram(
            "rag_unique_documents_per_query",
            "Number of unique documents used per query",
            buckets=(0, 1, 2, 3, 4, 5, 7, 10),
        )

        self.context_utilization = Histogram(
            "rag_context_length_chars",
            "Length of context provided to LLM",
            buckets=(0, 500, 1000, 2000, 4000, 8000, 16000, 32000),
        )

        logger.info("Metrics service initialized with Prometheus client")

    def record_message_processed(self, user_id: str, channel_type: str = "dm"):
        """Record a processed Slack message"""
        if not self.enabled:
            return

        try:
            self.messages_processed.labels(
                user_id=user_id, channel_type=channel_type
            ).inc()
        except Exception as e:
            logger.error(f"Error recording message metric: {e}")

    def record_rag_retrieval(
        self,
        provider: str,
        entity_filter: str = "none",
        chunks_found: int = 0,
        avg_similarity: float = 0.0,
    ):
        """Record a RAG retrieval operation"""
        if not self.enabled:
            return

        try:
            self.rag_retrievals.labels(
                provider=provider, entity_filter=entity_filter
            ).inc()

            if avg_similarity > 0:
                self.retrieval_quality.observe(avg_similarity)

            # Track number of chunks found (could be useful for monitoring)
            _ = chunks_found  # Acknowledged but not currently tracked in metrics

        except Exception as e:
            logger.error(f"Error recording RAG retrieval metric: {e}")

    def record_llm_request(
        self,
        provider: str,
        model: str,
        status: str = "success",
        duration: float = 0.0,
        tokens: int = 0,
    ):
        """Record an LLM API request"""
        if not self.enabled:
            return

        try:
            self.llm_requests.labels(
                provider=provider, model=model, status=status
            ).inc()

            if duration > 0:
                self.llm_duration.labels(provider=provider, model=model).observe(
                    duration
                )

            if tokens > 0:
                self.response_tokens.labels(provider=provider, model=model).observe(
                    tokens
                )

        except Exception as e:
            logger.error(f"Error recording LLM request metric: {e}")

    def record_cache_operation(self, operation: str, status: str = "success"):
        """Record a cache operation (hit, miss, set, etc.)"""
        if not self.enabled:
            return

        try:
            self.cache_operations.labels(operation=operation, status=status).inc()
        except Exception as e:
            logger.error(f"Error recording cache metric: {e}")

    def update_cache_hit_rate(self, hit_rate: float):
        """Update current cache hit rate percentage"""
        if not self.enabled:
            return

        try:
            self.cache_hit_rate.set(hit_rate)
        except Exception as e:
            logger.error(f"Error updating cache hit rate: {e}")

    def record_rag_query_result(
        self,
        result_type: str,  # "hit", "miss", "error"
        provider: str,
        chunks_found: int = 0,
        unique_documents: int = 0,
        context_length: int = 0,
        avg_similarity: float = 0.0,
    ):
        """Record RAG query results and quality metrics"""
        try:
            # Update dashboard stats (always track, even if Prometheus disabled)
            self._rag_stats["total_queries"] += 1
            if result_type == "hit":
                self._rag_stats["successful_queries"] += 1
                self._rag_stats["total_documents_used"] += unique_documents
                # Update rolling average of chunks per query
                total_queries = self._rag_stats["total_queries"]
                current_avg = self._rag_stats["avg_chunks_per_query"]
                self._rag_stats["avg_chunks_per_query"] = (
                    current_avg * (total_queries - 1) + chunks_found
                ) / total_queries
            elif result_type in ["miss", "error"]:
                self._rag_stats["failed_queries"] += 1

            if not self.enabled:
                return

            # Record hit/miss/error to Prometheus
            self.rag_hits_vs_misses.labels(
                result_type=result_type, provider=provider
            ).inc()

            # Record chunk and document metrics for successful queries
            if result_type == "hit" and chunks_found > 0:
                self.retrieval_chunk_count.observe(chunks_found)
                self.document_diversity.observe(unique_documents)

                if context_length > 0:
                    self.context_utilization.observe(context_length)

                if avg_similarity > 0:
                    self.retrieval_quality.observe(avg_similarity)

        except Exception as e:
            logger.error(f"Error recording RAG query result: {e}")

    def record_document_usage(self, document_type: str, source: str):
        """Record when a document is retrieved and used"""
        if not self.enabled:
            return

        try:
            self.rag_document_usage.labels(
                document_type=document_type, source=source
            ).inc()
        except Exception as e:
            logger.error(f"Error recording document usage: {e}")

    def record_query_type(self, query_category: str, has_context: bool):
        """Record the type of query being processed"""
        if not self.enabled:
            return

        try:
            self.rag_query_types.labels(
                query_category=query_category,
                has_context="yes" if has_context else "no",
            ).inc()
        except Exception as e:
            logger.error(f"Error recording query type: {e}")

    def record_user_interaction(
        self, interaction_type: str, user_type: str = "regular"
    ):
        """Record user interaction patterns for satisfaction tracking"""
        if not self.enabled:
            return

        try:
            self.user_satisfaction.labels(
                interaction_type=interaction_type, user_type=user_type
            ).inc()
        except Exception as e:
            logger.error(f"Error recording user interaction: {e}")

    def record_conversation_activity(self, conversation_id: str):
        """Record activity in a conversation"""
        if not self.enabled:
            return

        try:
            # Update conversation activity timestamp
            self._active_conversations[conversation_id] = datetime.now()

            # Log conversation activity for debugging
            logger.debug(
                f"Recorded activity for conversation: {conversation_id[:20]}... (total active: {len(self._active_conversations)})"
            )

            # Clean up old conversations and update metric
            self._cleanup_inactive_conversations()

        except Exception as e:
            logger.error(f"Error recording conversation activity: {e}")

    def _cleanup_inactive_conversations(self):
        """Remove inactive conversations and update the metric"""
        if not self.enabled:
            return

        try:
            now = datetime.now()
            cutoff_time = now - self._conversation_timeout

            # Remove conversations older than timeout
            inactive_conversations = [
                conv_id
                for conv_id, last_activity in self._active_conversations.items()
                if last_activity < cutoff_time
            ]

            for conv_id in inactive_conversations:
                del self._active_conversations[conv_id]

            # Update Prometheus metric with current active count
            active_count = len(self._active_conversations)
            self.active_conversations.set(active_count)

            if inactive_conversations:
                logger.info(
                    f"Cleaned up {len(inactive_conversations)} inactive conversations. Active: {active_count}"
                )
            elif active_count > 0:
                logger.debug(f"Active conversations: {active_count}")

        except Exception as e:
            logger.error(f"Error cleaning up conversations: {e}")

    def update_active_conversations(self, count: int):
        """Update the number of active conversations (legacy method)"""
        if not self.enabled:
            return

        try:
            self.active_conversations.set(count)
        except Exception as e:
            logger.error(f"Error updating active conversations: {e}")

    def get_active_conversation_count(self) -> int:
        """Get current active conversation count"""
        if not self.enabled:
            return 0

        self._cleanup_inactive_conversations()
        return len(self._active_conversations)

    def get_rag_stats(self) -> dict:
        """Get RAG statistics for dashboard display"""
        stats = self._rag_stats.copy()

        # Calculate success rate
        total = stats["total_queries"]
        if total > 0:
            stats["success_rate"] = round(
                (stats["successful_queries"] / total) * 100, 1
            )
            stats["miss_rate"] = round((stats["failed_queries"] / total) * 100, 1)
        else:
            stats["success_rate"] = 0.0
            stats["miss_rate"] = 0.0

        # Round average chunks
        stats["avg_chunks_per_query"] = round(stats["avg_chunks_per_query"], 1)

        return stats

    def reset_rag_stats(self):
        """Reset RAG statistics (useful for daily/weekly resets)"""
        self._rag_stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "total_documents_used": 0,
            "avg_chunks_per_query": 0.0,
            "last_reset": datetime.now(),
        }

    def record_agent_invocation(
        self, agent_name: str, status: str = "success", duration: float = 0.0
    ):
        """Record an agent invocation"""
        if not self.enabled:
            # Still track in-memory stats even if Prometheus is disabled
            self._agent_stats["total_invocations"] += 1
            if status == "success":
                self._agent_stats["successful_invocations"] += 1
            else:
                self._agent_stats["failed_invocations"] += 1

            # Track by agent
            if agent_name not in self._agent_stats["by_agent"]:
                self._agent_stats["by_agent"][agent_name] = 0
            self._agent_stats["by_agent"][agent_name] += 1
            return

        try:
            # Prometheus metrics
            self.agent_invocations.labels(agent_name=agent_name, status=status).inc()
            if duration > 0:
                self.agent_duration.labels(agent_name=agent_name).observe(duration)

            # In-memory stats for dashboard
            self._agent_stats["total_invocations"] += 1
            if status == "success":
                self._agent_stats["successful_invocations"] += 1
            else:
                self._agent_stats["failed_invocations"] += 1

            # Track by agent
            if agent_name not in self._agent_stats["by_agent"]:
                self._agent_stats["by_agent"][agent_name] = 0
            self._agent_stats["by_agent"][agent_name] += 1

        except Exception as e:
            logger.error(f"Error recording agent invocation metric: {e}")

    def get_agent_stats(self) -> dict:
        """Get agent invocation statistics for dashboard display"""
        stats = self._agent_stats.copy()

        # Calculate success rate
        total = stats["total_invocations"]
        if total > 0:
            stats["success_rate"] = round(
                (stats["successful_invocations"] / total) * 100, 1
            )
            stats["error_rate"] = round((stats["failed_invocations"] / total) * 100, 1)
        else:
            stats["success_rate"] = 0.0
            stats["error_rate"] = 0.0

        return stats

    def reset_agent_stats(self):
        """Reset agent statistics (useful for daily/weekly resets)"""
        self._agent_stats = {
            "total_invocations": 0,
            "successful_invocations": 0,
            "failed_invocations": 0,
            "by_agent": {},
            "last_reset": datetime.now(),
        }

    @asynccontextmanager
    async def time_request(self, endpoint: str, method: str = "POST"):
        """Context manager to time request duration"""
        if not self.enabled:
            yield
            return

        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            try:
                self.request_duration.labels(endpoint=endpoint, method=method).observe(
                    duration
                )
            except Exception as e:
                logger.error(f"Error recording request duration: {e}")

    @asynccontextmanager
    async def time_rag_operation(self, operation_type: str, provider: str):
        """Context manager to time RAG operations"""
        if not self.enabled:
            yield
            return

        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            try:
                self.rag_duration.labels(
                    operation_type=operation_type, provider=provider
                ).observe(duration)
            except Exception as e:
                logger.error(f"Error recording RAG duration: {e}")

    def get_metrics(self) -> str:
        """Get current metrics in Prometheus format"""
        if not self.enabled:
            return "# Metrics disabled\n"

        try:
            return generate_latest().decode("utf-8")
        except Exception as e:
            logger.error(f"Error generating metrics: {e}")
            return f"# Error generating metrics: {e}\n"

    def get_content_type(self) -> str:
        """Get the content type for metrics endpoint"""
        if not self.enabled:
            return "text/plain"
        return CONTENT_TYPE_LATEST


# Global metrics service instance
metrics_service: MetricsService | None = None


def get_metrics_service() -> MetricsService | None:
    """Get the global metrics service instance"""
    return metrics_service


def initialize_metrics_service(enabled: bool = True) -> MetricsService:
    """Initialize the global metrics service"""
    global metrics_service  # noqa: PLW0603
    metrics_service = MetricsService(enabled=enabled)
    return metrics_service
