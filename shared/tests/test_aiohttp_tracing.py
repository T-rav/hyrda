"""Tests for aiohttp tracing middleware."""

import pytest
from unittest.mock import patch
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.middleware.aiohttp_tracing import create_tracing_middleware


class TestAiohttpTracingMiddleware(AioHTTPTestCase):
    """Test aiohttp tracing middleware functionality."""

    async def get_application(self):
        """Create test application with tracing middleware."""
        app = web.Application(middlewares=[create_tracing_middleware("test-service")])

        async def health_handler(request):
            return web.json_response({"status": "healthy"})

        async def error_handler(request):
            raise web.HTTPBadRequest(text="Bad request")

        async def exception_handler(request):
            raise ValueError("Unexpected error")

        app.router.add_get("/health", health_handler)
        app.router.add_get("/error", error_handler)
        app.router.add_get("/exception", exception_handler)

        return app

    @unittest_run_loop
    async def test_successful_request_adds_trace_id_header(self):
        """Test that successful requests get X-Trace-Id in response."""
        response = await self.client.request("GET", "/health")

        assert response.status == 200
        assert "X-Trace-Id" in response.headers
        assert response.headers["X-Trace-Id"].startswith("trace_")

    @unittest_run_loop
    async def test_incoming_trace_id_is_preserved(self):
        """Test that incoming X-Trace-Id is preserved in response."""
        incoming_trace_id = "trace_incoming123"
        headers = {"X-Trace-Id": incoming_trace_id}

        response = await self.client.request("GET", "/health", headers=headers)

        assert response.status == 200
        assert response.headers["X-Trace-Id"] == incoming_trace_id

    @unittest_run_loop
    async def test_http_exception_is_logged_and_propagated(self):
        """Test that HTTP exceptions are logged and re-raised."""
        response = await self.client.request("GET", "/error")

        assert response.status == 400
        # Trace ID should still be added even on error
        assert "X-Trace-Id" in response.headers

    @unittest_run_loop
    async def test_unexpected_exception_is_logged(self):
        """Test that unexpected exceptions are logged with trace info."""
        with pytest.raises(Exception):
            await self.client.request("GET", "/exception")


class TestTracingMiddlewareLogging:
    """Test logging behavior of tracing middleware."""

    @pytest.mark.asyncio
    async def test_request_start_is_logged(self):
        """Test that request start is logged with trace info."""
        app = web.Application(middlewares=[create_tracing_middleware("test-service")])

        async def handler(request):
            return web.json_response({"ok": True})

        app.router.add_get("/test", handler)

        with patch("shared.middleware.aiohttp_tracing.logger") as mock_logger:
            from aiohttp.test_utils import TestClient, TestServer

            async with TestClient(TestServer(app)) as client:
                await client.get("/test")

            # Verify logging was called for start and completion
            assert mock_logger.info.call_count >= 2

            # Check that trace info was included
            calls = mock_logger.info.call_args_list
            assert any("started" in str(call) for call in calls)
            assert any("success" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_error_is_logged_with_trace_info(self):
        """Test that errors are logged with trace information."""
        app = web.Application(middlewares=[create_tracing_middleware("test-service")])

        async def handler(request):
            raise ValueError("Test error")

        app.router.add_get("/error", handler)

        with patch("shared.middleware.aiohttp_tracing.logger") as mock_logger:
            from aiohttp.test_utils import TestClient, TestServer

            async with TestClient(TestServer(app)) as client:
                try:
                    await client.get("/error")
                except Exception:
                    pass

            # Verify error was logged
            assert mock_logger.error.called or mock_logger.warning.called


class TestTracingMiddlewareFactory:
    """Test the middleware factory function."""

    def test_creates_middleware_with_service_name(self):
        """Test that factory creates middleware with correct service name."""
        middleware = create_tracing_middleware("my-service")
        assert callable(middleware)

    def test_different_services_create_different_middlewares(self):
        """Test that different service names create distinct middlewares."""
        middleware1 = create_tracing_middleware("service-a")
        middleware2 = create_tracing_middleware("service-b")

        # They should be different function objects
        assert middleware1 is not middleware2
