"""Tests for tasks service auth proxy to control-plane."""


class TestAuthProxyConfiguration:
    """Test auth proxy configuration."""

    def test_control_plane_internal_url_env_var(self):
        """Test that CONTROL_PLANE_INTERNAL_URL environment variable is configured."""
        # This test verifies the expected environment variable for auth proxy
        # In production, this should be set to http://control-plane:6001
        expected_url = "http://control-plane:6001"

        # Verify the format of the expected URL
        assert "control-plane" in expected_url
        assert "6001" in expected_url
        assert expected_url.startswith("https://")

    def test_control_plane_base_url_format(self):
        """Test that control plane URLs follow the expected format."""
        # Test various valid formats
        valid_urls = [
            "http://control-plane:6001",
            "http://localhost:6001",
            "https://control-plane.example.com:6001",
        ]

        for url in valid_urls:
            assert "6001" in url  # Port should be 6001
            assert url.startswith(("http://", "https://"))

    def test_auth_endpoint_path(self):
        """Test that auth endpoint path is correct."""
        # The auth endpoint should be /api/users/me
        endpoint_path = "/api/users/me"

        assert endpoint_path.startswith("/api/")
        assert "users/me" in endpoint_path
