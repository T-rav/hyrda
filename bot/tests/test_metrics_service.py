"""
Tests for Metrics Service functionality using factory patterns.

Tests metrics collection and reporting with Prometheus client.
"""

from unittest.mock import Mock, patch

import pytest

from bot.services.metrics_service import (
    MetricsService,
    get_metrics_service,
    initialize_metrics_service,
)


# TDD Factory Patterns for Metrics Service Testing
class MetricsServiceFactory:
    """Factory for creating MetricsService instances with different configurations"""

    @staticmethod
    def create_enabled_service() -> MetricsService:
        """Create enabled metrics service"""
        # Mock Prometheus client to avoid import issues
        with (
            patch("bot.services.metrics_service._prometheus_available", True),
            patch("bot.services.metrics_service.Counter"),
            patch("bot.services.metrics_service.Gauge"),
            patch("bot.services.metrics_service.Histogram"),
        ):
            return MetricsService(enabled=True)

    @staticmethod
    def create_disabled_service() -> MetricsService:
        """Create disabled metrics service"""
        return MetricsService(enabled=False)

    @staticmethod
    def create_service_with_error() -> MetricsService:
        """Create service that throws errors for testing error handling"""
        service = MetricsServiceFactory.create_enabled_service()
        service.messages_processed = Mock()
        service.messages_processed.labels.side_effect = Exception("Test error")
        return service


class MetricsDataFactory:
    """Factory for creating test data for metrics operations"""

    @staticmethod
    def create_message_data(
        user_id: str = "user123", channel_type: str = "dm"
    ) -> dict[str, str]:
        """Create message processing data"""
        return {"user_id": user_id, "channel_type": channel_type}

    @staticmethod
    def create_rag_data(
        provider: str = "elasticsearch",
        entity_filter: str = "apple",
        chunks_found: int = 5,
        avg_similarity: float = 0.85,
    ) -> dict[str, str | int | float]:
        """Create RAG retrieval data"""
        return {
            "provider": provider,
            "entity_filter": entity_filter,
            "chunks_found": chunks_found,
            "avg_similarity": avg_similarity,
        }

    @staticmethod
    def create_llm_request_data(
        provider: str = "openai",
        model: str = "gpt-4",
        status: str = "success",
        duration: float = 1.5,
        tokens: int = 150,
    ) -> dict[str, str | float | int]:
        """Create LLM request data"""
        return {
            "provider": provider,
            "model": model,
            "status": status,
            "duration": duration,
            "tokens": tokens,
        }

    @staticmethod
    def create_cache_operation_data(
        operation: str = "hit", status: str = "success"
    ) -> dict[str, str]:
        """Create cache operation data"""
        return {"operation": operation, "status": status}

    @staticmethod
    def create_conversation_id(conv_id: str = "conv123") -> str:
        """Create conversation ID for testing"""
        return conv_id

    @staticmethod
    def create_api_endpoint_data(
        endpoint: str = "/api/chat", method: str = "POST"
    ) -> dict[str, str]:
        """Create API endpoint data"""
        return {"endpoint": endpoint, "method": method}

    @staticmethod
    def create_rag_operation_data(
        operation: str = "search", provider: str = "elasticsearch"
    ) -> dict[str, str]:
        """Create RAG operation data"""
        return {"operation": operation, "provider": provider}


class PrometheusDataFactory:
    """Factory for creating Prometheus-related test data"""

    @staticmethod
    def create_metrics_text() -> bytes:
        """Create sample metrics text"""
        return b"test metrics"

    @staticmethod
    def create_content_type() -> str:
        """Create Prometheus content type"""
        return "application/test"

    @staticmethod
    def create_disabled_metrics_text() -> str:
        """Create disabled metrics message"""
        return "Metrics collection is disabled"


class TestMetricsService:
    """Test cases for MetricsService using factory patterns"""

    def test_init_enabled(self):
        """Test service initialization when enabled"""
        metrics_service = MetricsServiceFactory.create_enabled_service()

        assert metrics_service.enabled is True
        assert hasattr(metrics_service, "messages_processed")
        assert hasattr(metrics_service, "rag_retrievals")
        assert hasattr(metrics_service, "llm_requests")

    def test_init_disabled(self):
        """Test service initialization when disabled"""
        disabled_metrics_service = MetricsServiceFactory.create_disabled_service()

        assert disabled_metrics_service.enabled is False

    def test_record_message_processed(self):
        """Test recording processed messages"""
        metrics_service = MetricsServiceFactory.create_enabled_service()
        disabled_service = MetricsServiceFactory.create_disabled_service()
        message_data = MetricsDataFactory.create_message_data()

        # Should not raise error
        metrics_service.record_message_processed(
            message_data["user_id"], message_data["channel_type"]
        )

        # With disabled service
        disabled_service.record_message_processed(
            message_data["user_id"], message_data["channel_type"]
        )

    def test_record_message_processed_custom_data(self):
        """Test recording processed messages with custom data"""
        metrics_service = MetricsServiceFactory.create_enabled_service()
        custom_data = MetricsDataFactory.create_message_data(
            user_id="custom_user", channel_type="channel"
        )

        # Should not raise error with custom data
        metrics_service.record_message_processed(
            custom_data["user_id"], custom_data["channel_type"]
        )

    def test_record_rag_retrieval(self):
        """Test recording RAG retrieval operations"""
        metrics_service = MetricsServiceFactory.create_enabled_service()
        disabled_service = MetricsServiceFactory.create_disabled_service()
        rag_data = MetricsDataFactory.create_rag_data()

        metrics_service.record_rag_retrieval(
            provider=rag_data["provider"],
            entity_filter=rag_data["entity_filter"],
            chunks_found=rag_data["chunks_found"],
            avg_similarity=rag_data["avg_similarity"],
        )

        # With disabled service
        disabled_service.record_rag_retrieval("test", "none", 0, 0.0)

    def test_record_rag_retrieval_different_providers(self):
        """Test recording RAG retrieval with different providers"""
        metrics_service = MetricsServiceFactory.create_enabled_service()

        providers = ["elasticsearch", "pinecone", "chroma"]
        for provider in providers:
            rag_data = MetricsDataFactory.create_rag_data(provider=provider)
            metrics_service.record_rag_retrieval(
                provider=rag_data["provider"],
                entity_filter=rag_data["entity_filter"],
                chunks_found=rag_data["chunks_found"],
                avg_similarity=rag_data["avg_similarity"],
            )

    def test_record_llm_request(self):
        """Test recording LLM requests"""
        metrics_service = MetricsServiceFactory.create_enabled_service()
        disabled_service = MetricsServiceFactory.create_disabled_service()
        llm_data = MetricsDataFactory.create_llm_request_data()

        metrics_service.record_llm_request(
            provider=llm_data["provider"],
            model=llm_data["model"],
            status=llm_data["status"],
            duration=llm_data["duration"],
            tokens=llm_data["tokens"],
        )

        # With disabled service
        disabled_service.record_llm_request("test", "model", "success", 0.0, 0)

    def test_record_llm_request_different_providers(self):
        """Test recording LLM requests with different providers"""
        metrics_service = MetricsServiceFactory.create_enabled_service()

        providers = [
            ("openai", "gpt-4"),
            ("anthropic", "claude-3-haiku"),
            ("ollama", "llama2"),
        ]

        for provider, model in providers:
            llm_data = MetricsDataFactory.create_llm_request_data(
                provider=provider, model=model
            )
            metrics_service.record_llm_request(
                provider=llm_data["provider"],
                model=llm_data["model"],
                status=llm_data["status"],
                duration=llm_data["duration"],
                tokens=llm_data["tokens"],
            )

    def test_record_cache_operation(self):
        """Test recording cache operations"""
        metrics_service = MetricsServiceFactory.create_enabled_service()
        disabled_service = MetricsServiceFactory.create_disabled_service()

        cache_hit = MetricsDataFactory.create_cache_operation_data("hit", "success")
        cache_miss = MetricsDataFactory.create_cache_operation_data("miss", "success")

        metrics_service.record_cache_operation(
            cache_hit["operation"], cache_hit["status"]
        )
        metrics_service.record_cache_operation(
            cache_miss["operation"], cache_miss["status"]
        )

        # With disabled service
        disabled_service.record_cache_operation("test", "success")

    def test_update_cache_hit_rate(self):
        """Test updating cache hit rate"""
        metrics_service = MetricsServiceFactory.create_enabled_service()
        disabled_service = MetricsServiceFactory.create_disabled_service()

        metrics_service.update_cache_hit_rate(75.5)

        # With disabled service
        disabled_service.update_cache_hit_rate(80.0)

    def test_conversation_activity_tracking(self):
        """Test conversation activity tracking"""
        metrics_service = MetricsServiceFactory.create_enabled_service()
        conv_id = MetricsDataFactory.create_conversation_id()

        # Record activity
        metrics_service.record_conversation_activity(conv_id)

        # Get count
        count = metrics_service.get_active_conversation_count()
        assert isinstance(count, int)
        assert count >= 0

    def test_conversation_activity_tracking_multiple_conversations(self):
        """Test tracking multiple conversation activities"""
        metrics_service = MetricsServiceFactory.create_enabled_service()

        conv_ids = [
            MetricsDataFactory.create_conversation_id("conv1"),
            MetricsDataFactory.create_conversation_id("conv2"),
            MetricsDataFactory.create_conversation_id("conv3"),
        ]

        # Record activity for multiple conversations
        for conv_id in conv_ids:
            metrics_service.record_conversation_activity(conv_id)

        count = metrics_service.get_active_conversation_count()
        assert isinstance(count, int)
        assert count >= 0

    def test_update_active_conversations(self):
        """Test updating active conversation count"""
        metrics_service = MetricsServiceFactory.create_enabled_service()
        disabled_service = MetricsServiceFactory.create_disabled_service()

        metrics_service.update_active_conversations(5)

        # With disabled service
        disabled_service.update_active_conversations(10)

    @pytest.mark.asyncio
    async def test_time_request_context_manager(self):
        """Test request timing context manager"""
        metrics_service = MetricsServiceFactory.create_enabled_service()
        endpoint_data = MetricsDataFactory.create_api_endpoint_data()

        async with metrics_service.time_request(
            endpoint_data["endpoint"], endpoint_data["method"]
        ):
            pass  # Simulate work

    @pytest.mark.asyncio
    async def test_time_request_context_manager_different_endpoints(self):
        """Test request timing with different endpoints"""
        metrics_service = MetricsServiceFactory.create_enabled_service()

        endpoints = [
            ("/api/chat", "POST"),
            ("/api/health", "GET"),
            ("/api/metrics", "GET"),
        ]

        for endpoint, method in endpoints:
            endpoint_data = MetricsDataFactory.create_api_endpoint_data(
                endpoint, method
            )
            async with metrics_service.time_request(
                endpoint_data["endpoint"], endpoint_data["method"]
            ):
                pass

    @pytest.mark.asyncio
    async def test_time_rag_operation_context_manager(self):
        """Test RAG operation timing context manager"""
        metrics_service = MetricsServiceFactory.create_enabled_service()
        rag_op_data = MetricsDataFactory.create_rag_operation_data()

        async with metrics_service.time_rag_operation(
            rag_op_data["operation"], rag_op_data["provider"]
        ):
            pass  # Simulate work

    @pytest.mark.asyncio
    async def test_context_managers_with_disabled_service(self):
        """Test context managers with disabled service"""
        disabled_service = MetricsServiceFactory.create_disabled_service()

        async with disabled_service.time_request("/test"):
            pass

        async with disabled_service.time_rag_operation("test", "test"):
            pass

    def test_get_metrics_enabled(self):
        """Test getting metrics when enabled"""
        metrics_service = MetricsServiceFactory.create_enabled_service()
        sample_metrics = PrometheusDataFactory.create_metrics_text()

        with patch(
            "bot.services.metrics_service.generate_latest", return_value=sample_metrics
        ):
            metrics_text = metrics_service.get_metrics()
            assert metrics_text == "test metrics"

    def test_get_metrics_disabled(self):
        """Test getting metrics when disabled"""
        disabled_metrics_service = MetricsServiceFactory.create_disabled_service()
        metrics_text = disabled_metrics_service.get_metrics()
        assert "disabled" in metrics_text

    def test_get_content_type(self):
        """Test getting content type for metrics"""
        metrics_service = MetricsServiceFactory.create_enabled_service()
        disabled_metrics_service = MetricsServiceFactory.create_disabled_service()
        sample_content_type = PrometheusDataFactory.create_content_type()

        # Enabled service should return Prometheus content type
        with patch(
            "bot.services.metrics_service.CONTENT_TYPE_LATEST", sample_content_type
        ):
            content_type = metrics_service.get_content_type()
            assert content_type == sample_content_type

        # Disabled service should return plain text
        content_type = disabled_metrics_service.get_content_type()
        assert content_type == "text/plain"

    def test_error_handling_in_record_methods(self):
        """Test error handling in metric recording methods"""
        metrics_service = MetricsServiceFactory.create_service_with_error()

        # Should not raise - errors are caught and logged
        metrics_service.record_message_processed("test", "dm")

    def test_cleanup_inactive_conversations(self):
        """Test cleanup of inactive conversations"""
        metrics_service = MetricsServiceFactory.create_enabled_service()

        # Add some conversation activity
        conv1 = MetricsDataFactory.create_conversation_id("conv1")
        conv2 = MetricsDataFactory.create_conversation_id("conv2")

        metrics_service.record_conversation_activity(conv1)
        metrics_service.record_conversation_activity(conv2)

        initial_count = len(metrics_service._active_conversations)
        assert initial_count >= 0

        # Cleanup should work without errors
        metrics_service._cleanup_inactive_conversations()


class TestGlobalMetricsService:
    """Test global metrics service functions using factory patterns"""

    def test_initialize_metrics_service(self):
        """Test initializing global metrics service"""
        with (
            patch("bot.services.metrics_service._prometheus_available", True),
            patch("bot.services.metrics_service.Counter"),
            patch("bot.services.metrics_service.Gauge"),
            patch("bot.services.metrics_service.Histogram"),
        ):
            service = initialize_metrics_service(enabled=True)
            assert isinstance(service, MetricsService)
            assert service.enabled is True

    def test_initialize_metrics_service_disabled(self):
        """Test initializing disabled global metrics service"""
        service = initialize_metrics_service(enabled=False)
        assert isinstance(service, MetricsService)
        assert service.enabled is False

    def test_get_metrics_service(self):
        """Test getting global metrics service"""
        # Initially should be None or the service from previous test
        service = get_metrics_service()
        assert service is None or isinstance(service, MetricsService)

    def test_factory_creates_consistent_services(self):
        """Test that factory creates consistent service instances"""
        enabled_service = MetricsServiceFactory.create_enabled_service()
        disabled_service = MetricsServiceFactory.create_disabled_service()
        error_service = MetricsServiceFactory.create_service_with_error()

        # Test enabled service
        assert enabled_service.enabled is True
        assert hasattr(enabled_service, "messages_processed")

        # Test disabled service
        assert disabled_service.enabled is False

        # Test error service has mocked error
        assert hasattr(error_service, "messages_processed")
        assert error_service.messages_processed.labels.side_effect is not None

    def test_data_factory_creates_valid_test_data(self):
        """Test that data factories create valid test data"""
        # Test message data
        msg_data = MetricsDataFactory.create_message_data()
        assert "user_id" in msg_data
        assert "channel_type" in msg_data

        # Test RAG data
        rag_data = MetricsDataFactory.create_rag_data()
        assert all(
            key in rag_data
            for key in ["provider", "entity_filter", "chunks_found", "avg_similarity"]
        )

        # Test LLM data
        llm_data = MetricsDataFactory.create_llm_request_data()
        assert all(
            key in llm_data
            for key in ["provider", "model", "status", "duration", "tokens"]
        )

        # Test conversation ID
        conv_id = MetricsDataFactory.create_conversation_id()
        assert isinstance(conv_id, str)
        assert conv_id.startswith("conv")
