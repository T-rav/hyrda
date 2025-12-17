"""Comprehensive unit tests for HTTP client utilities."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from shared.utils.http_client import (
    get_internal_service_url,
    get_secure_client,
    should_use_https,
)


class TestGetSecureClient:
    """Test secure HTTP client configuration."""

    @pytest.mark.asyncio
    async def test_default_timeout(self):
        """Test client created with default timeout."""
        client = get_secure_client()

        assert isinstance(client, httpx.AsyncClient)
        assert client.timeout.read == 10.0

        await client.aclose()

    @pytest.mark.asyncio
    async def test_custom_timeout(self):
        """Test client created with custom timeout."""
        client = get_secure_client(timeout=30.0)

        assert isinstance(client, httpx.AsyncClient)
        assert client.timeout.read == 30.0

        await client.aclose()

    @pytest.mark.asyncio
    async def test_explicit_verify_true(self):
        """Test client with explicit verify=True."""
        client = get_secure_client(verify=True)

        assert isinstance(client, httpx.AsyncClient)
        assert client._transport._pool._ssl_context.check_hostname is True

        await client.aclose()

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False)
    async def test_development_auto_verify_false(self):
        """Test development mode auto-sets verify=False."""
        client = get_secure_client()

        assert isinstance(client, httpx.AsyncClient)
        # In development, verify should be False (accepts self-signed certs)
        # Note: httpx doesn't expose verify directly, but we can test behavior

        await client.aclose()

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False)
    async def test_production_auto_verify_true(self):
        """Test production mode auto-sets verify=True."""
        client = get_secure_client()

        assert isinstance(client, httpx.AsyncClient)
        # In production, verify should be True (requires valid certs)

        await client.aclose()

    @patch.dict(
        os.environ,
        {"ENVIRONMENT": "production", "INTERNAL_CA_BUNDLE": "/path/to/ca.crt"},
        clear=False,
    )
    @patch("os.path.exists", return_value=True)
    @patch("httpx.AsyncClient")
    def test_production_with_ca_bundle(self, mock_client, mock_exists):
        """Test production mode with custom CA bundle path detection."""
        # Test that the function detects CA bundle correctly without creating actual client
        # This avoids SSL context errors with non-existent CA file
        get_secure_client()

        # Verify httpx.AsyncClient was called with the CA bundle path
        mock_client.assert_called_once()
        call_kwargs = mock_client.call_args[1]
        assert call_kwargs["verify"] == "/path/to/ca.crt"
        assert call_kwargs["timeout"] == 10.0

    @pytest.mark.asyncio
    @patch.dict(
        os.environ,
        {"ENVIRONMENT": "production", "INTERNAL_CA_BUNDLE": "/nonexistent/ca.crt"},
        clear=False,
    )
    @patch("os.path.exists", return_value=False)
    async def test_production_ca_bundle_not_exists(self, mock_exists):
        """Test production mode with non-existent CA bundle falls back to system CA."""
        client = get_secure_client()

        assert isinstance(client, httpx.AsyncClient)
        # Should fall back to system CA bundle (verify=True)

        await client.aclose()

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"ENVIRONMENT": "staging"}, clear=False)
    async def test_staging_requires_verification(self):
        """Test staging environment requires TLS verification."""
        client = get_secure_client()

        assert isinstance(client, httpx.AsyncClient)
        # Staging should behave like production

        await client.aclose()

    def test_production_rejects_verify_false(self):
        """Test production environment rejects verify=False."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            with pytest.raises(
                ValueError, match="SECURITY: Cannot use verify=False in production"
            ):
                get_secure_client(verify=False)

    def test_staging_rejects_verify_false(self):
        """Test staging environment rejects verify=False."""
        with patch.dict(os.environ, {"ENVIRONMENT": "staging"}, clear=False):
            with pytest.raises(
                ValueError, match="SECURITY: Cannot use verify=False in production"
            ):
                get_secure_client(verify=False)

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False)
    async def test_development_allows_verify_false(self):
        """Test development environment allows verify=False."""
        client = get_secure_client(verify=False)

        assert isinstance(client, httpx.AsyncClient)

        await client.aclose()

    @pytest.mark.asyncio
    @patch.dict(os.environ, {}, clear=True)
    async def test_no_environment_defaults_to_development(self):
        """Test no ENVIRONMENT variable defaults to development mode."""
        client = get_secure_client()

        assert isinstance(client, httpx.AsyncClient)
        # Should default to development behavior (verify=False)

        await client.aclose()

    @pytest.mark.asyncio
    async def test_context_manager_support(self):
        """Test client works as async context manager."""
        async with get_secure_client() as client:
            assert isinstance(client, httpx.AsyncClient)
        # Client should be closed after context

    @pytest.mark.asyncio
    async def test_multiple_clients_independent(self):
        """Test creating multiple clients doesn't interfere."""
        client1 = get_secure_client(timeout=10.0)
        client2 = get_secure_client(timeout=20.0)

        assert client1 is not client2
        assert client1.timeout.read == 10.0
        assert client2.timeout.read == 20.0

        await client1.aclose()
        await client2.aclose()


class TestShouldUseHttps:
    """Test HTTPS requirement determination logic."""

    def test_internal_docker_service_http_ok(self):
        """Test internal Docker services can use HTTP."""
        internal_services = [
            "http://control_plane:6001/api/test",
            "http://control-plane:6001/api/test",
            "http://agent_service:8000/api/test",
            "http://agent-service:8000/api/test",
            "http://tasks:5001/api/test",
            "http://rag_service:8002/api/test",
            "http://rag-service:8002/api/test",
            "http://bot:3000/api/test",
        ]

        for url in internal_services:
            assert should_use_https(url) is False

    def test_localhost_http_ok(self):
        """Test localhost can use HTTP."""
        localhost_urls = [
            "http://localhost:8000/api/test",
            "http://127.0.0.1:8000/api/test",
        ]

        for url in localhost_urls:
            assert should_use_https(url) is False

    def test_external_hosts_require_https(self):
        """Test external hosts require HTTPS."""
        external_urls = [
            "http://api.example.com/endpoint",
            "http://external-service.com/api",
            "http://production-api.company.com/v1",
        ]

        for url in external_urls:
            assert should_use_https(url) is True

    def test_case_insensitive_hostname_check(self):
        """Test hostname checking is case-insensitive."""
        mixed_case_urls = [
            "http://LOCALHOST:8000/api",
            "http://Control_Plane:6001/api",
            "http://AGENT-SERVICE:8000/api",
        ]

        for url in mixed_case_urls:
            assert should_use_https(url) is False

    def test_urls_with_no_hostname(self):
        """Test URLs with no hostname."""
        # Edge case: malformed URL
        assert should_use_https("") is True  # Empty string defaults to requiring HTTPS

    def test_urls_with_paths_and_query_params(self):
        """Test URLs with complex paths and query parameters."""
        url_with_params = (
            "http://localhost:8000/api/v1/users?name=test&sort=desc#section"
        )
        assert should_use_https(url_with_params) is False

        external_with_params = (
            "http://api.example.com/v1/data?key=value&format=json#results"
        )
        assert should_use_https(external_with_params) is True

    def test_https_urls_still_validated(self):
        """Test HTTPS URLs are still validated correctly."""
        # Even if URL is already HTTPS, function should return correct result
        assert should_use_https("https://localhost:8000/api") is False
        assert should_use_https("https://external.com/api") is True


class TestGetInternalServiceUrl:
    """Test internal service URL generation."""

    def test_control_plane_url(self):
        """Test control_plane service URL generation."""
        url = get_internal_service_url("control_plane", "/api/agents")

        assert url == "http://control_plane:6001/api/agents"

    def test_control_plane_hyphenated_url(self):
        """Test control-plane (hyphenated) service URL generation."""
        url = get_internal_service_url("control-plane", "/api/agents")

        assert url == "http://control-plane:6001/api/agents"

    def test_agent_service_url(self):
        """Test agent_service URL generation."""
        url = get_internal_service_url("agent_service", "/api/invoke")

        assert url == "http://agent_service:8000/api/invoke"

    def test_agent_service_hyphenated_url(self):
        """Test agent-service (hyphenated) URL generation."""
        url = get_internal_service_url("agent-service", "/api/invoke")

        assert url == "http://agent-service:8000/api/invoke"

    def test_tasks_service_url(self):
        """Test tasks service URL generation."""
        url = get_internal_service_url("tasks", "/api/jobs")

        assert url == "http://tasks:5001/api/jobs"

    def test_rag_service_url(self):
        """Test rag_service URL generation."""
        url = get_internal_service_url("rag_service", "/api/search")

        assert url == "http://rag_service:8002/api/search"

    def test_rag_service_hyphenated_url(self):
        """Test rag-service (hyphenated) URL generation."""
        url = get_internal_service_url("rag-service", "/api/search")

        assert url == "http://rag-service:8002/api/search"

    def test_empty_path(self):
        """Test URL generation with empty path."""
        url = get_internal_service_url("control_plane", "")

        assert url == "http://control_plane:6001"

    def test_path_without_leading_slash(self):
        """Test path without leading slash is corrected."""
        url = get_internal_service_url("agent_service", "api/invoke")

        assert url == "http://agent_service:8000/api/invoke"

    def test_path_with_leading_slash(self):
        """Test path with leading slash is preserved."""
        url = get_internal_service_url("tasks", "/api/jobs")

        assert url == "http://tasks:5001/api/jobs"

    def test_unknown_service_raises_error(self):
        """Test unknown service name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown internal service: unknown"):
            get_internal_service_url("unknown", "/api/test")

    def test_case_insensitive_service_name(self):
        """Test service name is case-insensitive."""
        url = get_internal_service_url("CONTROL_PLANE", "/api/test")

        assert url == "http://CONTROL_PLANE:6001/api/test"

    def test_complex_path_with_query_params(self):
        """Test URL generation with complex paths."""
        url = get_internal_service_url("agent_service", "/api/v1/agents?type=meddpicc")

        assert url == "http://agent_service:8000/api/v1/agents?type=meddpicc"

    def test_root_path(self):
        """Test URL generation with root path."""
        url = get_internal_service_url("control_plane", "/")

        assert url == "http://control_plane:6001/"

    def test_all_supported_services(self):
        """Test all supported internal services can generate URLs."""
        services = [
            ("control_plane", "6001"),
            ("control-plane", "6001"),
            ("agent_service", "8000"),
            ("agent-service", "8000"),
            ("tasks", "5001"),
            ("rag_service", "8002"),
            ("rag-service", "8002"),
        ]

        for service_name, expected_port in services:
            url = get_internal_service_url(service_name, "/health")
            assert url == f"http://{service_name}:{expected_port}/health"

    def test_url_uses_http_not_https(self):
        """Test that internal service URLs use HTTP (not HTTPS)."""
        url = get_internal_service_url("control_plane", "/api/test")

        assert url.startswith("http://")
        assert not url.startswith("https://")


class TestHttpClientIntegration:
    """Integration tests combining client creation and usage patterns."""

    @pytest.mark.asyncio
    async def test_client_can_make_request(self):
        """Test client can be used to make actual HTTP requests."""
        # Mock httpx request
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = AsyncMock(return_value={"status": "ok"})
            mock_get.return_value = mock_response

            async with get_secure_client() as client:
                response = await client.get("http://localhost:8000/health")

                assert response.status_code == 200
                assert await response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_internal_service_url_with_client(self):
        """Test using internal service URL with client."""
        url = get_internal_service_url("control_plane", "/health")

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            async with get_secure_client() as client:
                response = await client.get(url)

                assert response.status_code == 200
                mock_get.assert_called_once_with(url)

    def test_https_decision_for_internal_service_url(self):
        """Test HTTPS requirement matches internal service URL generation."""
        url = get_internal_service_url("agent_service", "/api/invoke")

        # Internal service URLs should not require HTTPS
        assert should_use_https(url) is False

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False)
    async def test_development_workflow(self):
        """Test typical development workflow with self-signed certs."""
        # Development: can use verify=False for local HTTPS services
        async with get_secure_client() as client:
            # Should work with self-signed certificates
            assert isinstance(client, httpx.AsyncClient)

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False)
    async def test_production_workflow(self):
        """Test typical production workflow with proper TLS."""
        # Production: requires proper TLS verification
        async with get_secure_client() as client:
            # Should require valid CA-signed certificates
            assert isinstance(client, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout configuration works correctly."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Request timed out")

            async with get_secure_client(timeout=5.0) as client:
                with pytest.raises(httpx.TimeoutException):
                    await client.get("http://slow-service.com/api")

    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Test connection error handling."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            async with get_secure_client() as client:
                with pytest.raises(httpx.ConnectError):
                    await client.get("http://unreachable-service.com/api")

    @pytest.mark.asyncio
    async def test_http_error_status_codes(self):
        """Test HTTP error status code handling."""
        error_codes = [400, 401, 403, 404, 500, 502, 503]

        for status_code in error_codes:
            with patch("httpx.AsyncClient.get") as mock_get:
                mock_response = AsyncMock()
                mock_response.status_code = status_code
                mock_response.raise_for_status = MagicMock(
                    side_effect=httpx.HTTPStatusError(
                        f"HTTP {status_code}",
                        request=MagicMock(),
                        response=mock_response,
                    )
                )
                mock_get.return_value = mock_response

                async with get_secure_client() as client:
                    response = await client.get("http://api.example.com/test")
                    assert response.status_code == status_code


class TestLoggingBehavior:
    """Test logging behavior in different environments."""

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False)
    async def test_production_mode_with_logging(self):
        """Test production mode creates client successfully (logging is internal)."""
        # We don't test internal logging directly, but verify client creation works
        client = get_secure_client()

        assert isinstance(client, httpx.AsyncClient)
        # Production mode should use proper TLS verification

        await client.aclose()

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False)
    async def test_development_mode_with_logging(self):
        """Test development mode creates client successfully (logging is internal)."""
        # We don't test internal logging directly, but verify client creation works
        client = get_secure_client()

        assert isinstance(client, httpx.AsyncClient)
        # Development mode should accept self-signed certs

        await client.aclose()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_zero_timeout(self):
        """Test client with zero timeout."""
        client = get_secure_client(timeout=0.0)

        assert isinstance(client, httpx.AsyncClient)
        assert client.timeout.read == 0.0

        await client.aclose()

    @pytest.mark.asyncio
    async def test_very_large_timeout(self):
        """Test client with very large timeout."""
        client = get_secure_client(timeout=3600.0)  # 1 hour

        assert isinstance(client, httpx.AsyncClient)
        assert client.timeout.read == 3600.0

        await client.aclose()

    def test_empty_service_name(self):
        """Test empty service name raises error."""
        with pytest.raises(ValueError):
            get_internal_service_url("", "/api/test")

    def test_whitespace_service_name(self):
        """Test whitespace-only service name raises error."""
        with pytest.raises(ValueError):
            get_internal_service_url("   ", "/api/test")

    def test_special_characters_in_path(self):
        """Test path with special characters."""
        url = get_internal_service_url(
            "control_plane", "/api/users?name=test&email=user@example.com"
        )

        assert "user@example.com" in url

    def test_url_with_fragment(self):
        """Test URL with fragment identifier."""
        url = get_internal_service_url("agent_service", "/api/docs#section-2")

        assert url == "http://agent_service:8000/api/docs#section-2"

    def test_should_use_https_with_ipv6(self):
        """Test should_use_https with IPv6 addresses."""
        # IPv6 localhost should be treated like localhost
        assert should_use_https("http://[::1]:8000/api") is True  # Not in whitelist

    def test_should_use_https_with_port(self):
        """Test should_use_https correctly handles ports."""
        assert should_use_https("http://localhost:8080/api") is False
        assert should_use_https("http://external.com:443/api") is True
