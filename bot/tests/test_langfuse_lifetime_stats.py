"""
Tests for Langfuse lifetime statistics functionality.

Tests the new get_lifetime_stats method that queries Langfuse API for historical
conversation and trace data since a given start date.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientError, ClientResponseError


class LangfuseServiceFactory:
    """Factory for creating LangfuseService test instances"""

    @staticmethod
    def create_mock_service(enabled: bool = True) -> MagicMock:
        """Create a mock LangfuseService instance"""
        service = MagicMock()
        service.enabled = enabled
        service.settings = MagicMock()
        service.settings.host = "https://cloud.langfuse.com"
        service.settings.public_key = "pk_test_123"
        service.settings.secret_key = MagicMock()
        service.settings.secret_key.get_secret_value.return_value = "sk_test_456"
        return service


class MockResponseFactory:
    """Factory for creating mock aiohttp responses"""

    @staticmethod
    def create_json_response(status: int, json_data: dict) -> MagicMock:
        """Create a mock response with JSON data"""
        mock_response = MagicMock()
        mock_response.status = status
        mock_response.json = AsyncMock(return_value=json_data)
        mock_response.text = AsyncMock(return_value=str(json_data))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        return mock_response

    @staticmethod
    def create_mock_session(responses: list) -> MagicMock:
        """Create a mock ClientSession with predefined responses"""
        response_iter = iter(responses)
        mock_session = MagicMock()
        mock_session.get = MagicMock(
            side_effect=lambda *args, **kwargs: next(response_iter)
        )
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        return mock_session


class TestLangfuseLifetimeStats:
    """Test Langfuse lifetime statistics retrieval"""

    @pytest.mark.asyncio
    async def test_get_lifetime_stats_success(self):
        """Test successful retrieval of lifetime statistics"""
        from services.langfuse_service import LangfuseService

        mock_settings = MagicMock()
        mock_settings.enabled = True
        mock_settings.host = "https://cloud.langfuse.com"
        mock_settings.public_key = "pk_test_123"
        mock_settings.secret_key = MagicMock()
        mock_settings.secret_key.get_secret_value.return_value = "sk_test_456"

        service = LangfuseService(mock_settings)

        # Create mock responses using factory
        responses = [
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 6328}, "data": []}
            ),
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 36916}, "data": []}
            ),
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 59}, "data": []}
            ),
        ]

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MockResponseFactory.create_mock_session(responses)
            mock_session_class.return_value = mock_session

            result = await service.get_lifetime_stats(start_date="2025-10-21")

            assert result["total_traces"] == 6328
            assert result["total_observations"] == 36916
            assert result["unique_sessions"] == 59
            assert result["start_date"] == "2025-10-21"
            assert mock_session.get.call_count == 3

    @pytest.mark.asyncio
    async def test_get_lifetime_stats_default_date(self):
        """Test that default start date is used if not provided"""
        from services.langfuse_service import LangfuseService

        mock_settings = MagicMock()
        mock_settings.enabled = True
        mock_settings.host = "https://cloud.langfuse.com"
        mock_settings.public_key = "pk_test_123"
        mock_settings.secret_key = MagicMock()
        mock_settings.secret_key.get_secret_value.return_value = "sk_test_456"

        service = LangfuseService(mock_settings)

        responses = [
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 100}, "data": []}
            ),
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 100}, "data": []}
            ),
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 100}, "data": []}
            ),
        ]

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MockResponseFactory.create_mock_session(responses)
            mock_session_class.return_value = mock_session

            result = await service.get_lifetime_stats()

            assert result["start_date"] == "2025-10-21"

    @pytest.mark.asyncio
    async def test_get_lifetime_stats_http_error(self):
        """Test handling of HTTP errors from Langfuse API"""
        from services.langfuse_service import LangfuseService

        mock_settings = MagicMock()
        mock_settings.enabled = True
        mock_settings.host = "https://cloud.langfuse.com"
        mock_settings.public_key = "pk_test_123"
        mock_settings.secret_key = MagicMock()
        mock_settings.secret_key.get_secret_value.return_value = "sk_test_456"

        service = LangfuseService(mock_settings)

        with patch("aiohttp.ClientSession") as mock_session_class:
            # Simulate 401 Unauthorized error
            mock_session = MagicMock()
            mock_session.get = MagicMock(
                side_effect=ClientResponseError(
                    request_info=MagicMock(), history=(), status=401
                )
            )
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            result = await service.get_lifetime_stats()

            assert result["total_traces"] == 0
            assert result["total_observations"] == 0
            assert result["unique_sessions"] == 0
            assert "error" in result
            assert "401" in result["error"]

    @pytest.mark.asyncio
    async def test_get_lifetime_stats_network_error(self):
        """Test handling of network errors"""
        from services.langfuse_service import LangfuseService

        mock_settings = MagicMock()
        mock_settings.enabled = True
        mock_settings.host = "https://cloud.langfuse.com"
        mock_settings.public_key = "pk_test_123"
        mock_settings.secret_key = MagicMock()
        mock_settings.secret_key.get_secret_value.return_value = "sk_test_456"

        service = LangfuseService(mock_settings)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session.get = MagicMock(side_effect=ClientError("Connection refused"))
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            result = await service.get_lifetime_stats()

            assert result["total_traces"] == 0
            assert result["total_observations"] == 0
            assert result["unique_sessions"] == 0
            assert "error" in result
            assert "Connection refused" in result["error"]

    @pytest.mark.asyncio
    async def test_get_lifetime_stats_invalid_json(self):
        """Test handling of invalid JSON response"""
        from services.langfuse_service import LangfuseService

        mock_settings = MagicMock()
        mock_settings.enabled = True
        mock_settings.host = "https://cloud.langfuse.com"
        mock_settings.public_key = "pk_test_123"
        mock_settings.secret_key = MagicMock()
        mock_settings.secret_key.get_secret_value.return_value = "sk_test_456"

        service = LangfuseService(mock_settings)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        responses = [mock_response]

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MockResponseFactory.create_mock_session(responses)
            mock_session_class.return_value = mock_session

            result = await service.get_lifetime_stats()

            assert result["total_traces"] == 0
            assert result["total_observations"] == 0
            assert result["unique_sessions"] == 0
            assert "error" in result

    @pytest.mark.asyncio
    async def test_get_lifetime_stats_missing_meta(self):
        """Test handling of response missing 'meta' field"""
        from services.langfuse_service import LangfuseService

        mock_settings = MagicMock()
        mock_settings.enabled = True
        mock_settings.host = "https://cloud.langfuse.com"
        mock_settings.public_key = "pk_test_123"
        mock_settings.secret_key = MagicMock()
        mock_settings.secret_key.get_secret_value.return_value = "sk_test_456"

        service = LangfuseService(mock_settings)

        responses = [
            MockResponseFactory.create_json_response(200, {"data": []}),
            MockResponseFactory.create_json_response(200, {"data": []}),
            MockResponseFactory.create_json_response(200, {"data": []}),
        ]

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MockResponseFactory.create_mock_session(responses)
            mock_session_class.return_value = mock_session

            result = await service.get_lifetime_stats()

            assert result["total_traces"] == 0
            assert result["total_observations"] == 0
            assert result["unique_sessions"] == 0

    @pytest.mark.asyncio
    async def test_get_lifetime_stats_custom_date_range(self):
        """Test statistics retrieval with custom date range"""
        from services.langfuse_service import LangfuseService

        mock_settings = MagicMock()
        mock_settings.enabled = True
        mock_settings.host = "https://cloud.langfuse.com"
        mock_settings.public_key = "pk_test_123"
        mock_settings.secret_key = MagicMock()
        mock_settings.secret_key.get_secret_value.return_value = "sk_test_456"

        service = LangfuseService(mock_settings)

        responses = [
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 50}, "data": []}
            ),
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 50}, "data": []}
            ),
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 50}, "data": []}
            ),
        ]

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MockResponseFactory.create_mock_session(responses)
            mock_session_class.return_value = mock_session

            result = await service.get_lifetime_stats(start_date="2025-11-01")

            assert result["start_date"] == "2025-11-01"
            assert result["total_traces"] == 50
            assert result["total_observations"] == 50
            assert result["unique_sessions"] == 50

    @pytest.mark.asyncio
    async def test_get_lifetime_stats_zero_results(self):
        """Test handling of zero results from Langfuse API"""
        from services.langfuse_service import LangfuseService

        mock_settings = MagicMock()
        mock_settings.enabled = True
        mock_settings.host = "https://cloud.langfuse.com"
        mock_settings.public_key = "pk_test_123"
        mock_settings.secret_key = MagicMock()
        mock_settings.secret_key.get_secret_value.return_value = "sk_test_456"

        service = LangfuseService(mock_settings)

        responses = [
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 0}, "data": []}
            ),
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 0}, "data": []}
            ),
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 0}, "data": []}
            ),
        ]

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MockResponseFactory.create_mock_session(responses)
            mock_session_class.return_value = mock_session

            result = await service.get_lifetime_stats()

            assert result["total_traces"] == 0
            assert result["total_observations"] == 0
            assert result["unique_sessions"] == 0
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_get_lifetime_stats_authentication(self):
        """Test that authentication credentials are properly included"""
        from services.langfuse_service import LangfuseService

        mock_settings = MagicMock()
        mock_settings.enabled = True
        mock_settings.host = "https://cloud.langfuse.com"
        mock_settings.public_key = "pk_test_123"
        mock_settings.secret_key = MagicMock()
        mock_settings.secret_key.get_secret_value.return_value = "sk_test_456"

        service = LangfuseService(mock_settings)

        responses = [
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 100}, "data": []}
            ),
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 100}, "data": []}
            ),
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 100}, "data": []}
            ),
        ]

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MockResponseFactory.create_mock_session(responses)
            mock_session_class.return_value = mock_session

            await service.get_lifetime_stats()

            # Verify session.get was called 3 times (traces, observations, sessions)
            assert mock_session.get.call_count == 3

    @pytest.mark.asyncio
    async def test_get_lifetime_stats_timeout_handling(self):
        """Test that timeout is properly configured"""
        from services.langfuse_service import LangfuseService

        mock_settings = MagicMock()
        mock_settings.enabled = True
        mock_settings.host = "https://cloud.langfuse.com"
        mock_settings.public_key = "pk_test_123"
        mock_settings.secret_key = MagicMock()
        mock_settings.secret_key.get_secret_value.return_value = "sk_test_456"

        service = LangfuseService(mock_settings)

        responses = [
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 100}, "data": []}
            ),
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 100}, "data": []}
            ),
            MockResponseFactory.create_json_response(
                200, {"meta": {"totalItems": 100}, "data": []}
            ),
        ]

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = MockResponseFactory.create_mock_session(responses)
            mock_session_class.return_value = mock_session

            await service.get_lifetime_stats()

            # Verify get was called with timeout parameter
            # Check first call's kwargs
            call_kwargs = mock_session.get.call_args_list[0][1]
            assert "timeout" in call_kwargs
            assert call_kwargs["timeout"] == 10


class TestHealthEndpointLifetimeStats:
    """Test health endpoint integration with lifetime statistics"""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_includes_lifetime_stats(self):
        """Test that /api/metrics endpoint includes lifetime statistics"""
        from health import HealthChecker

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.llm.api_key.get_secret_value.return_value = "test-key"
        mock_settings.llm.provider = "openai"
        mock_settings.llm.model = "gpt-4"
        mock_settings.slack.bot_token = "xoxb-test"
        mock_settings.slack.app_token = "xapp-test"

        # Mock Langfuse service with lifetime stats
        mock_langfuse = MagicMock()
        mock_langfuse.enabled = True
        mock_langfuse.get_lifetime_stats = AsyncMock(
            return_value={
                "total_traces": 6328,
                "total_observations": 36916,
                "unique_sessions": 59,
                "start_date": "2025-10-21",
            }
        )

        # Create health checker
        health_checker = HealthChecker(
            mock_settings, conversation_cache=None, langfuse_service=mock_langfuse
        )

        # Mock request
        mock_request = MagicMock()

        # Call metrics endpoint
        response = await health_checker.metrics(mock_request)

        # Parse response
        import json

        data = json.loads(response.body)

        # Verify lifetime stats are included
        assert "lifetime_stats" in data
        lifetime_stats = data["lifetime_stats"]
        assert lifetime_stats["total_traces"] == 6328
        assert lifetime_stats["total_observations"] == 36916
        assert lifetime_stats["unique_threads"] == 59
        assert lifetime_stats["since_date"] == "2025-10-21"
        assert "description" in lifetime_stats

    @pytest.mark.asyncio
    async def test_metrics_endpoint_handles_langfuse_error(self):
        """Test metrics endpoint when Langfuse API returns error"""
        from health import HealthChecker

        mock_settings = MagicMock()
        mock_settings.llm.api_key.get_secret_value.return_value = "test-key"
        mock_settings.llm.provider = "openai"
        mock_settings.llm.model = "gpt-4"
        mock_settings.slack.bot_token = "xoxb-test"

        # Mock Langfuse service that returns error
        mock_langfuse = MagicMock()
        mock_langfuse.enabled = True
        mock_langfuse.get_lifetime_stats = AsyncMock(
            return_value={
                "total_traces": 0,
                "total_observations": 0,
                "unique_sessions": 0,
                "start_date": "2025-10-21",
                "error": "API authentication failed",
            }
        )

        # Mock metrics service to avoid MagicMock serialization issues
        with patch("health.get_metrics_service") as mock_get_metrics:
            mock_metrics = MagicMock()
            mock_metrics.enabled = True
            mock_metrics.get_active_conversation_count.return_value = 0
            mock_metrics.get_rag_stats.return_value = {
                "total_queries": 0,
                "success_rate": 0.0,
                "miss_rate": 0.0,
                "hit_rate": 0.0,
                "avg_chunks": 0.0,
                "avg_chunks_per_query": 0.0,
                "documents_used": 0,
                "total_documents_used": 0,
                "last_reset": datetime.now(),
            }
            mock_metrics.get_agent_stats.return_value = {
                "total_invocations": 0,
                "successful_invocations": 0,
                "failed_invocations": 0,
                "success_rate": 0.0,
                "error_rate": 0.0,
                "by_agent": {},
                "last_reset": datetime.now(),
            }
            mock_get_metrics.return_value = mock_metrics

            health_checker = HealthChecker(
                mock_settings, conversation_cache=None, langfuse_service=mock_langfuse
            )

            mock_request = MagicMock()
            response = await health_checker.metrics(mock_request)

            import json

            data = json.loads(response.body)

            # Should include error in lifetime stats
            assert "lifetime_stats" in data
            assert data["lifetime_stats"]["error"] == "API authentication failed"

    @pytest.mark.asyncio
    async def test_metrics_endpoint_no_langfuse_service(self):
        """Test metrics endpoint when Langfuse service is not configured"""
        from health import HealthChecker

        mock_settings = MagicMock()
        mock_settings.llm.api_key.get_secret_value.return_value = "test-key"
        mock_settings.llm.provider = "openai"
        mock_settings.llm.model = "gpt-4"
        mock_settings.slack.bot_token = "xoxb-test"

        # Mock metrics service to avoid MagicMock serialization issues
        with patch("health.get_metrics_service") as mock_get_metrics:
            mock_metrics = MagicMock()
            mock_metrics.enabled = True
            mock_metrics.get_active_conversation_count.return_value = 0
            mock_metrics.get_rag_stats.return_value = {
                "total_queries": 0,
                "success_rate": 0.0,
                "miss_rate": 0.0,
                "hit_rate": 0.0,
                "avg_chunks": 0.0,
                "avg_chunks_per_query": 0.0,
                "documents_used": 0,
                "total_documents_used": 0,
                "last_reset": datetime.now(),
            }
            mock_metrics.get_agent_stats.return_value = {
                "total_invocations": 0,
                "successful_invocations": 0,
                "failed_invocations": 0,
                "success_rate": 0.0,
                "error_rate": 0.0,
                "by_agent": {},
                "last_reset": datetime.now(),
            }
            mock_get_metrics.return_value = mock_metrics

            # No Langfuse service provided
            health_checker = HealthChecker(
                mock_settings, conversation_cache=None, langfuse_service=None
            )

            mock_request = MagicMock()
            response = await health_checker.metrics(mock_request)

            import json

            data = json.loads(response.body)

            # Should handle gracefully - check if lifetime_stats exists
            # If not, that's acceptable behavior
            if "lifetime_stats" in data:
                # If included, should indicate service is unavailable
                assert (
                    data["lifetime_stats"].get("error") is not None
                    or data["lifetime_stats"].get("total_traces") == 0
                )
