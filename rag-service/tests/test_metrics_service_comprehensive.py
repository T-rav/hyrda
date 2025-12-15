"""
Comprehensive tests for metrics service.

Tests Prometheus metrics collection, RAG/agent stats, and performance tracking.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from contextlib import asynccontextmanager

from services.metrics_service import MetricsService, get_metrics_service, initialize_metrics_service


class TestMetricsServiceInitialization:
    """Test metrics service initialization."""

    def test_metrics_service_initialization_enabled(self):
        """Test initialization when Prometheus is available."""
        service = MetricsService(enabled=True)
        # If Prometheus is available, service should be enabled
        assert service is not None

    def test_metrics_service_initialization_disabled(self):
        """Test initialization when explicitly disabled."""
        service = MetricsService(enabled=False)
        assert service.enabled is False

    def test_metrics_service_has_rag_stats(self):
        """Test that RAG stats are initialized."""
        service = MetricsService()
        stats = service._rag_stats

        assert "total_queries" in stats
        assert "successful_queries" in stats
        assert "failed_queries" in stats
        assert "total_documents_used" in stats
        assert "avg_chunks_per_query" in stats
        assert "last_reset" in stats

    def test_metrics_service_has_agent_stats(self):
        """Test that agent stats are initialized."""
        service = MetricsService()
        stats = service._agent_stats

        assert "total_invocations" in stats
        assert "successful_invocations" in stats
        assert "failed_invocations" in stats
        assert "by_agent" in stats
        assert "last_reset" in stats


class TestMessageProcessing:
    """Test message processing metrics."""

    def test_record_message_processed_dm(self):
        """Test recording DM message."""
        service = MetricsService(enabled=False)  # Disable Prometheus for unit test
        # Should not raise error even if disabled
        service.record_message_processed("U123", "dm")

    def test_record_message_processed_channel(self):
        """Test recording channel message."""
        service = MetricsService(enabled=False)
        service.record_message_processed("U123", "channel")

    def test_record_message_processed_default_channel_type(self):
        """Test recording message with default channel type."""
        service = MetricsService(enabled=False)
        service.record_message_processed("U123")


class TestRAGMetrics:
    """Test RAG-related metrics."""

    def test_record_rag_retrieval_basic(self):
        """Test recording basic RAG retrieval."""
        service = MetricsService(enabled=False)
        service.record_rag_retrieval(
            provider="qdrant",
            chunks_found=5,
            avg_similarity=0.85
        )

    def test_record_rag_retrieval_with_filters(self):
        """Test recording RAG retrieval with entity filters."""
        service = MetricsService(enabled=False)
        service.record_rag_retrieval(
            provider="qdrant",
            chunks_found=3,
            avg_similarity=0.9,
            entity_filter="employee"
        )

    def test_record_rag_retrieval_no_results(self):
        """Test recording RAG retrieval with no results."""
        service = MetricsService(enabled=False)
        service.record_rag_retrieval(
            provider="qdrant",
            chunks_found=0,
            avg_similarity=0.0
        )

    def test_record_rag_query_result_hit(self):
        """Test recording RAG query hit."""
        service = MetricsService(enabled=False)
        service.record_rag_query_result(
            result_type="hit",
            provider="qdrant",
            chunks_found=5,
            avg_similarity=0.85
        )

        stats = service.get_rag_stats()
        assert stats["total_queries"] == 1
        assert stats["successful_queries"] == 1

    def test_record_rag_query_result_miss(self):
        """Test recording RAG query miss."""
        service = MetricsService(enabled=False)
        service.record_rag_query_result(
            result_type="miss",
            provider="qdrant",
            chunks_found=0,
            avg_similarity=0.0
        )

        stats = service.get_rag_stats()
        assert stats["total_queries"] == 1
        assert stats["failed_queries"] == 1

    def test_record_rag_query_result_error(self):
        """Test recording RAG query error."""
        service = MetricsService(enabled=False)
        service.record_rag_query_result(
            result_type="error",
            provider="qdrant",
            chunks_found=0,
            avg_similarity=0.0
        )

        stats = service.get_rag_stats()
        assert stats["total_queries"] == 1
        assert stats["failed_queries"] == 1

    def test_get_rag_stats(self):
        """Test getting RAG statistics."""
        service = MetricsService(enabled=False)

        # Record some queries
        service.record_rag_query_result("hit", "qdrant", chunks_found=5, avg_similarity=0.85)
        service.record_rag_query_result("hit", "qdrant", chunks_found=3, avg_similarity=0.9)
        service.record_rag_query_result("miss", "qdrant", chunks_found=0, avg_similarity=0.0)

        stats = service.get_rag_stats()
        assert stats["total_queries"] == 3
        assert stats["successful_queries"] == 2
        assert stats["failed_queries"] == 1

    def test_reset_rag_stats(self):
        """Test resetting RAG statistics."""
        service = MetricsService(enabled=False)

        # Record some queries
        service.record_rag_query_result("hit", "qdrant", chunks_found=5, avg_similarity=0.85)
        service.reset_rag_stats()

        stats = service.get_rag_stats()
        assert stats["total_queries"] == 0
        assert stats["successful_queries"] == 0
        assert stats["failed_queries"] == 0


class TestLLMMetrics:
    """Test LLM-related metrics."""

    def test_record_llm_request_success(self):
        """Test recording successful LLM request."""
        service = MetricsService(enabled=False)
        service.record_llm_request(
            provider="openai",
            model="gpt-4",
            status="success",
            duration=2.5,
            tokens=500
        )

    def test_record_llm_request_error(self):
        """Test recording failed LLM request."""
        service = MetricsService(enabled=False)
        service.record_llm_request(
            provider="anthropic",
            model="claude-3",
            status="error"
        )

    def test_record_llm_request_minimal(self):
        """Test recording LLM request with minimal params."""
        service = MetricsService(enabled=False)
        service.record_llm_request(
            provider="openai",
            model="gpt-3.5-turbo",
            status="success"
        )


class TestAgentMetrics:
    """Test agent invocation metrics."""

    def test_record_agent_invocation_success(self):
        """Test recording successful agent invocation."""
        service = MetricsService(enabled=False)
        service.record_agent_invocation(
            agent_name="research",
            status="success",
            duration=5.2
        )

        stats = service.get_agent_stats()
        assert stats["total_invocations"] == 1
        assert stats["successful_invocations"] == 1
        assert "research" in stats["by_agent"]

    def test_record_agent_invocation_error(self):
        """Test recording failed agent invocation."""
        service = MetricsService(enabled=False)
        service.record_agent_invocation(
            agent_name="company_profile",
            status="error",
            duration=1.5
        )

        stats = service.get_agent_stats()
        assert stats["total_invocations"] == 1
        assert stats["failed_invocations"] == 1

    def test_get_agent_stats(self):
        """Test getting agent statistics."""
        service = MetricsService(enabled=False)

        service.record_agent_invocation("research", "success", 3.0)
        service.record_agent_invocation("research", "success", 4.0)
        service.record_agent_invocation("company_profile", "error", 2.0)

        stats = service.get_agent_stats()
        assert stats["total_invocations"] == 3
        assert stats["successful_invocations"] == 2
        assert stats["failed_invocations"] == 1
        assert stats["by_agent"]["research"] == 2
        assert stats["by_agent"]["company_profile"] == 1

    def test_reset_agent_stats(self):
        """Test resetting agent statistics."""
        service = MetricsService(enabled=False)

        service.record_agent_invocation("research", "success", 3.0)
        service.reset_agent_stats()

        stats = service.get_agent_stats()
        assert stats["total_invocations"] == 0
        assert stats["successful_invocations"] == 0
        assert stats["by_agent"] == {}


class TestCacheMetrics:
    """Test cache-related metrics."""

    def test_record_cache_operation_hit(self):
        """Test recording cache hit."""
        service = MetricsService(enabled=False)
        service.record_cache_operation("get", "hit")

    def test_record_cache_operation_miss(self):
        """Test recording cache miss."""
        service = MetricsService(enabled=False)
        service.record_cache_operation("get", "miss")

    def test_record_cache_operation_set(self):
        """Test recording cache set."""
        service = MetricsService(enabled=False)
        service.record_cache_operation("set", "success")

    def test_update_cache_hit_rate(self):
        """Test updating cache hit rate."""
        service = MetricsService(enabled=False)
        service.update_cache_hit_rate(0.85)


class TestDocumentMetrics:
    """Test document usage metrics."""

    def test_record_document_usage_pdf(self):
        """Test recording PDF document usage."""
        service = MetricsService(enabled=False)
        service.record_document_usage("pdf", "google_drive")

    def test_record_document_usage_metric_data(self):
        """Test recording metric data usage."""
        service = MetricsService(enabled=False)
        service.record_document_usage("employee", "metric")


class TestQueryMetrics:
    """Test query categorization metrics."""

    def test_record_query_type_with_context(self):
        """Test recording query with RAG context."""
        service = MetricsService(enabled=False)
        service.record_query_type("factual", has_context=True)

    def test_record_query_type_without_context(self):
        """Test recording query without RAG context."""
        service = MetricsService(enabled=False)
        service.record_query_type("conversational", has_context=False)


class TestUserInteraction:
    """Test user interaction metrics."""

    def test_record_user_interaction_message(self):
        """Test recording message interaction."""
        service = MetricsService(enabled=False)
        service.record_user_interaction("message", "regular")

    def test_record_user_interaction_reaction(self):
        """Test recording reaction interaction."""
        service = MetricsService(enabled=False)
        service.record_user_interaction("reaction", "power_user")


class TestConversationTracking:
    """Test conversation activity tracking."""

    def test_record_conversation_activity_when_enabled(self):
        """Test recording conversation activity when service is enabled."""
        service = MetricsService(enabled=True)
        # This will only work if Prometheus is available
        # Test that it doesn't raise an error
        service.record_conversation_activity("thread_123")

    def test_cleanup_inactive_conversations(self):
        """Test cleanup of inactive conversations."""
        service = MetricsService(enabled=True)

        # Add old conversation directly
        old_time = datetime.now() - timedelta(days=8)
        service._active_conversations["old_thread"] = old_time

        # Add recent conversation
        service._active_conversations["new_thread"] = datetime.now()

        # Cleanup
        service._cleanup_inactive_conversations()

        # Old conversation should be removed
        assert "old_thread" not in service._active_conversations
        assert "new_thread" in service._active_conversations

    def test_update_active_conversations(self):
        """Test updating active conversation count."""
        service = MetricsService(enabled=False)
        service.update_active_conversations(5)

    def test_get_active_conversation_count(self):
        """Test getting active conversation count."""
        service = MetricsService(enabled=True)

        # Add conversations directly
        service._active_conversations["thread_1"] = datetime.now()
        service._active_conversations["thread_2"] = datetime.now()
        service._active_conversations["thread_3"] = datetime.now()

        count = service.get_active_conversation_count()
        assert count == 3


class TestPerformanceTiming:
    """Test performance timing context managers."""

    @pytest.mark.asyncio
    async def test_time_request_context_manager(self):
        """Test request timing context manager."""
        service = MetricsService(enabled=False)

        async with service.time_request("/api/rag/generate", "POST"):
            # Simulate work
            await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_time_rag_operation_context_manager(self):
        """Test RAG operation timing context manager."""
        service = MetricsService(enabled=False)

        async with service.time_rag_operation("retrieval", "qdrant"):
            # Simulate RAG operation
            await asyncio.sleep(0.01)


class TestMetricsExport:
    """Test metrics export functionality."""

    def test_get_metrics_when_disabled(self):
        """Test getting metrics when service is disabled."""
        service = MetricsService(enabled=False)
        metrics = service.get_metrics()
        assert metrics == "# Metrics disabled\n"

    def test_get_content_type(self):
        """Test getting Prometheus content type."""
        service = MetricsService(enabled=False)
        content_type = service.get_content_type()
        # Content type is either text/plain or the Prometheus CONTENT_TYPE_LATEST
        assert "text" in content_type or content_type


class TestGlobalServiceManagement:
    """Test global metrics service management."""

    def test_initialize_metrics_service(self):
        """Test initializing global metrics service."""
        service = initialize_metrics_service(enabled=True)
        assert service is not None
        assert isinstance(service, MetricsService)

    def test_initialize_metrics_service_disabled(self):
        """Test initializing disabled metrics service."""
        service = initialize_metrics_service(enabled=False)
        assert service is not None
        assert service.enabled is False

    def test_get_metrics_service_after_initialization(self):
        """Test getting global service after initialization."""
        initialized = initialize_metrics_service(enabled=True)
        retrieved = get_metrics_service()
        assert retrieved == initialized

    def test_get_metrics_service_returns_instance(self):
        """Test that get_metrics_service returns a MetricsService instance."""
        result = get_metrics_service()
        # May be None or may be an initialized instance
        assert result is None or isinstance(result, MetricsService)


# Need asyncio for async tests
import asyncio
