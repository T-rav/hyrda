"""Tests for auth utility functions (utils/auth.py)."""


class TestGetRedirectUri:
    """Test get_redirect_uri utility function."""

    def test_get_redirect_uri_basic(self):
        """Test basic redirect URI generation."""
        from utils.auth import get_redirect_uri

        uri = get_redirect_uri("http://localhost:5001")
        assert uri == "http://localhost:5001/auth/callback"

    def test_get_redirect_uri_with_trailing_slash(self):
        """Test redirect URI strips trailing slash from base URL."""
        from utils.auth import get_redirect_uri

        uri = get_redirect_uri("http://localhost:5001/")
        assert uri == "http://localhost:5001/auth/callback"

    def test_get_redirect_uri_multiple_trailing_slashes(self):
        """Test redirect URI handles multiple trailing slashes."""
        from utils.auth import get_redirect_uri

        uri = get_redirect_uri("http://localhost:5001///")
        assert uri == "http://localhost:5001/auth/callback"

    def test_get_redirect_uri_custom_callback_path(self):
        """Test redirect URI with custom callback path."""
        from utils.auth import get_redirect_uri

        uri = get_redirect_uri("http://localhost:5001", "/custom/callback")
        assert uri == "http://localhost:5001/custom/callback"

    def test_get_redirect_uri_https(self):
        """Test redirect URI with HTTPS."""
        from utils.auth import get_redirect_uri

        uri = get_redirect_uri("https://example.com")
        assert uri == "https://example.com/auth/callback"

    def test_get_redirect_uri_with_port(self):
        """Test redirect URI with custom port."""
        from utils.auth import get_redirect_uri

        uri = get_redirect_uri("http://localhost:8080")
        assert uri == "http://localhost:8080/auth/callback"

    def test_get_redirect_uri_production_url(self):
        """Test redirect URI with production URL."""
        from utils.auth import get_redirect_uri

        uri = get_redirect_uri("https://tasks.example.com")
        assert uri == "https://tasks.example.com/auth/callback"

    def test_get_redirect_uri_with_path(self):
        """Test redirect URI when base URL includes path."""
        from utils.auth import get_redirect_uri

        uri = get_redirect_uri("http://example.com/app")
        assert uri == "http://example.com/app/auth/callback"


class TestVerifyDomain:
    """Test verify_domain utility function."""

    def test_verify_domain_valid_email(self, monkeypatch):
        """Test domain verification with valid email."""
        from utils.auth import verify_domain

        monkeypatch.setenv("ALLOWED_EMAIL_DOMAIN", "example.com")
        # Re-import to pick up new env var
        import importlib

        import utils.auth

        importlib.reload(utils.auth)
        from utils.auth import verify_domain

        assert verify_domain("user@example.com") is True

    def test_verify_domain_invalid_email(self, monkeypatch):
        """Test domain verification with invalid domain."""
        from utils.auth import verify_domain

        monkeypatch.setenv("ALLOWED_EMAIL_DOMAIN", "example.com")
        import importlib

        import utils.auth

        importlib.reload(utils.auth)
        from utils.auth import verify_domain

        assert verify_domain("user@otherdomain.com") is False

    def test_verify_domain_empty_email(self):
        """Test domain verification with empty email."""
        from utils.auth import verify_domain

        assert verify_domain("") is False

    def test_verify_domain_none_email(self):
        """Test domain verification with None."""
        from utils.auth import verify_domain

        assert verify_domain(None) is False  # type: ignore

    def test_verify_domain_no_at_sign(self, monkeypatch):
        """Test domain verification with malformed email."""
        from utils.auth import verify_domain

        monkeypatch.setenv("ALLOWED_EMAIL_DOMAIN", "example.com")
        import importlib

        import utils.auth

        importlib.reload(utils.auth)
        from utils.auth import verify_domain

        assert verify_domain("userexample.com") is False

    def test_verify_domain_case_sensitive(self, monkeypatch):
        """Test domain verification is case-sensitive."""
        from utils.auth import verify_domain

        monkeypatch.setenv("ALLOWED_EMAIL_DOMAIN", "example.com")
        import importlib

        import utils.auth

        importlib.reload(utils.auth)
        from utils.auth import verify_domain

        # Should match exact case
        assert verify_domain("user@EXAMPLE.COM") is False
        assert verify_domain("user@example.com") is True

    def test_verify_domain_subdomain(self, monkeypatch):
        """Test domain verification with subdomain."""
        from utils.auth import verify_domain

        monkeypatch.setenv("ALLOWED_EMAIL_DOMAIN", "example.com")
        import importlib

        import utils.auth

        importlib.reload(utils.auth)
        from utils.auth import verify_domain

        # sub.example.com@example.com would pass
        # but user@sub.example.com would not match @example.com
        assert verify_domain("user@sub.example.com") is False


class TestGetRedirectUriEdgeCases:
    """Test edge cases for get_redirect_uri."""

    def test_empty_base_url(self):
        """Test with empty base URL."""
        from utils.auth import get_redirect_uri

        uri = get_redirect_uri("")
        assert uri == "/auth/callback"

    def test_base_url_only_protocol(self):
        """Test with protocol-only base URL."""
        from utils.auth import get_redirect_uri

        uri = get_redirect_uri("http://")
        assert uri == "http:/auth/callback"  # Strips trailing slashes

    def test_callback_path_with_query_params(self):
        """Test callback path with query parameters."""
        from utils.auth import get_redirect_uri

        uri = get_redirect_uri("http://localhost:5001", "/auth/callback?service=test")
        assert uri == "http://localhost:5001/auth/callback?service=test"

    def test_ipv4_address(self):
        """Test with IPv4 address."""
        from utils.auth import get_redirect_uri

        uri = get_redirect_uri("http://192.168.1.100:5001")
        assert uri == "http://192.168.1.100:5001/auth/callback"

    def test_localhost_variations(self):
        """Test different localhost variations."""
        from utils.auth import get_redirect_uri

        assert get_redirect_uri("http://localhost") == "http://localhost/auth/callback"
        assert get_redirect_uri("http://127.0.0.1") == "http://127.0.0.1/auth/callback"
        assert get_redirect_uri("http://0.0.0.0") == "http://0.0.0.0/auth/callback"
