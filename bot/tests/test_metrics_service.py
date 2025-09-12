"""
Tests for Metrics Service functionality.

Tests metrics collection and reporting with Prometheus client.
"""

from unittest.mock import Mock, patch

import pytest

from bot.services.metrics_service import (
    MetricsService,
    get_metrics_service,
    initialize_metrics_service,
)


class TestMetricsService:
    """Test cases for MetricsService"""

    @pytest.fixture
    def metrics_service(self):
        """Create metrics service for testing"""
        # Mock Prometheus client to avoid import issues
        with patch('bot.services.metrics_service._prometheus_available', True), \
             patch('bot.services.metrics_service.Counter'), \
             patch('bot.services.metrics_service.Gauge'), \
             patch('bot.services.metrics_service.Histogram'):
            return MetricsService(enabled=True)

    @pytest.fixture
    def disabled_metrics_service(self):
        """Create disabled metrics service for testing"""
        return MetricsService(enabled=False)

    def test_init_enabled(self, metrics_service):
        """Test service initialization when enabled"""
        assert metrics_service.enabled is True
        assert hasattr(metrics_service, 'messages_processed')
        assert hasattr(metrics_service, 'rag_retrievals')
        assert hasattr(metrics_service, 'llm_requests')

    def test_init_disabled(self, disabled_metrics_service):
        """Test service initialization when disabled"""
        assert disabled_metrics_service.enabled is False

    def test_record_message_processed(self, metrics_service):
        """Test recording processed messages"""
        # Should not raise error
        metrics_service.record_message_processed("user123", "dm")

        # With disabled service
        disabled_service = MetricsService(enabled=False)
        disabled_service.record_message_processed("user123", "dm")

    def test_record_rag_retrieval(self, metrics_service):
        """Test recording RAG retrieval operations"""
        metrics_service.record_rag_retrieval(
            provider="elasticsearch",
            entity_filter="apple",
            chunks_found=5,
            avg_similarity=0.85
        )

        # With disabled service
        disabled_service = MetricsService(enabled=False)
        disabled_service.record_rag_retrieval("test", "none", 0, 0.0)

    def test_record_llm_request(self, metrics_service):
        """Test recording LLM requests"""
        metrics_service.record_llm_request(
            provider="openai",
            model="gpt-4",
            status="success",
            duration=1.5,
            tokens=150
        )

        # With disabled service
        disabled_service = MetricsService(enabled=False)
        disabled_service.record_llm_request("test", "model", "success", 0.0, 0)

    def test_record_cache_operation(self, metrics_service):
        """Test recording cache operations"""
        metrics_service.record_cache_operation("hit", "success")
        metrics_service.record_cache_operation("miss", "success")

        # With disabled service
        disabled_service = MetricsService(enabled=False)
        disabled_service.record_cache_operation("test", "success")

    def test_update_cache_hit_rate(self, metrics_service):
        """Test updating cache hit rate"""
        metrics_service.update_cache_hit_rate(75.5)

        # With disabled service
        disabled_service = MetricsService(enabled=False)
        disabled_service.update_cache_hit_rate(80.0)

    def test_conversation_activity_tracking(self, metrics_service):
        """Test conversation activity tracking"""
        conv_id = "conv123"

        # Record activity
        metrics_service.record_conversation_activity(conv_id)

        # Get count
        count = metrics_service.get_active_conversation_count()
        assert isinstance(count, int)
        assert count >= 0

    def test_update_active_conversations(self, metrics_service):
        """Test updating active conversation count"""
        metrics_service.update_active_conversations(5)

        # With disabled service
        disabled_service = MetricsService(enabled=False)
        disabled_service.update_active_conversations(10)

    @pytest.mark.asyncio
    async def test_time_request_context_manager(self, metrics_service):
        """Test request timing context manager"""
        async with metrics_service.time_request("/api/chat", "POST"):
            pass  # Simulate work

    @pytest.mark.asyncio
    async def test_time_rag_operation_context_manager(self, metrics_service):
        """Test RAG operation timing context manager"""
        async with metrics_service.time_rag_operation("search", "elasticsearch"):
            pass  # Simulate work

    @pytest.mark.asyncio
    async def test_context_managers_with_disabled_service(self):
        """Test context managers with disabled service"""
        disabled_service = MetricsService(enabled=False)

        async with disabled_service.time_request("/test"):
            pass

        async with disabled_service.time_rag_operation("test", "test"):
            pass

    def test_get_metrics_enabled(self, metrics_service):
        """Test getting metrics when enabled"""
        with patch('bot.services.metrics_service.generate_latest', return_value=b'test metrics'):
            metrics_text = metrics_service.get_metrics()
            assert metrics_text == "test metrics"

    def test_get_metrics_disabled(self, disabled_metrics_service):
        """Test getting metrics when disabled"""
        metrics_text = disabled_metrics_service.get_metrics()
        assert "disabled" in metrics_text

    def test_get_content_type(self, metrics_service, disabled_metrics_service):
        """Test getting content type for metrics"""
        # Enabled service should return Prometheus content type
        with patch('bot.services.metrics_service.CONTENT_TYPE_LATEST', 'application/test'):
            content_type = metrics_service.get_content_type()
            assert content_type == 'application/test'

        # Disabled service should return plain text
        content_type = disabled_metrics_service.get_content_type()
        assert content_type == "text/plain"

    def test_error_handling_in_record_methods(self, metrics_service):
        """Test error handling in metric recording methods"""
        # Mock a metric that raises an error
        metrics_service.messages_processed = Mock()
        metrics_service.messages_processed.labels.side_effect = Exception("Test error")

        # Should not raise - errors are caught and logged
        metrics_service.record_message_processed("test", "dm")

    def test_cleanup_inactive_conversations(self, metrics_service):
        """Test cleanup of inactive conversations"""
        # Add some conversation activity
        metrics_service.record_conversation_activity("conv1")
        metrics_service.record_conversation_activity("conv2")

        initial_count = len(metrics_service._active_conversations)
        assert initial_count >= 0

        # Cleanup should work without errors
        metrics_service._cleanup_inactive_conversations()


class TestGlobalMetricsService:
    """Test global metrics service functions"""

    def test_initialize_metrics_service(self):
        """Test initializing global metrics service"""
        with patch('bot.services.metrics_service._prometheus_available', True), \
             patch('bot.services.metrics_service.Counter'), \
             patch('bot.services.metrics_service.Gauge'), \
             patch('bot.services.metrics_service.Histogram'):

            service = initialize_metrics_service(enabled=True)
            assert isinstance(service, MetricsService)
            assert service.enabled is True

    def test_get_metrics_service(self):
        """Test getting global metrics service"""
        # Initially should be None or the service from previous test
        service = get_metrics_service()
        assert service is None or isinstance(service, MetricsService)
