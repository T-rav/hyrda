"""
Tests for authentication endpoint paths and unauthenticated request handling.

Tests verify:
1. Logout endpoint is at /auth/logout (not /api/auth/logout)
2. Backend gracefully handles unauthenticated requests with proper 401/403
3. No aggressive redirects needed on frontend
"""

import pytest
from pathlib import Path


class TestLogoutEndpointPath:
    """Tests for logout endpoint path correctness - simplified source code verification."""

    def test_auth_router_has_auth_prefix(self):
        """Auth router should have /auth prefix, not /api/auth."""
        auth_file = Path(__file__).parent.parent / "api" / "auth.py"
        assert auth_file.exists(), "api/auth.py should exist"

        content = auth_file.read_text()

        # Verify router is defined with /auth prefix
        assert (
            'router = APIRouter(prefix="/auth"' in content
        ), "Auth router should have /auth prefix"

        # Should NOT have /api/auth prefix
        assert (
            'prefix="/api/auth"' not in content
        ), "Auth router should not have /api/auth prefix"

    def test_ui_calls_correct_logout_path(self):
        """UI should call /auth/logout, not /api/auth/logout."""
        app_jsx = Path(__file__).parent.parent / "ui" / "src" / "App.jsx"

        if not app_jsx.exists():
            pytest.skip("App.jsx not found (UI may not be built yet)")

        content = app_jsx.read_text()

        # Should call /auth/logout
        assert (
            "'/auth/logout'" in content
        ), "App.jsx should call /auth/logout for logout"

        # Should NOT call /api/auth/logout (the bug we fixed)
        assert (
            "'/api/auth/logout'" not in content
        ), "App.jsx should not call /api/auth/logout (incorrect path)"

    def test_logout_endpoint_is_post_method(self):
        """Logout endpoint should only accept POST requests."""
        auth_file = Path(__file__).parent.parent / "api" / "auth.py"
        content = auth_file.read_text()

        # Find the logout function definition
        lines = content.split("\n")
        logout_found = False
        post_decorator_found = False

        for i, line in enumerate(lines):
            if "@router.post" in line and "/logout" in line:
                post_decorator_found = True
            if "async def logout" in line or "def logout(" in line:
                logout_found = True
                # Check if POST decorator is within 5 lines above
                if i >= 1:
                    for j in range(max(0, i - 5), i):
                        if "@router.post" in lines[j]:
                            post_decorator_found = True
                            break

        assert logout_found, "logout function should exist in auth.py"
        assert (
            post_decorator_found
        ), "logout should use @router.post decorator (not GET)"


class TestUnauthenticatedRequestHandling:
    """Tests for graceful handling of unauthenticated requests - source code verification."""

    def test_get_current_user_email_raises_401_on_missing_auth(self):
        """get_current_user_email should raise 401 when auth is missing."""
        # Check dependencies/auth.py where the function actually lives
        auth_deps_file = Path(__file__).parent.parent / "dependencies" / "auth.py"

        if not auth_deps_file.exists():
            # Fallback to api/auth.py if dependencies doesn't exist
            auth_deps_file = Path(__file__).parent.parent / "api" / "auth.py"

        content = auth_deps_file.read_text()

        # Should have function that checks authentication
        assert (
            "def get_current_user" in content
        ), "Should have get_current_user or similar auth function"

        # Should raise HTTPException with status_code 401
        assert "HTTPException" in content, "Should use HTTPException"
        assert 'status_code=401' in content or "401" in content, "Should return 401 for missing auth"

    def test_auth_dependency_exists_in_endpoints(self):
        """API endpoints should have auth dependencies."""
        # Check users endpoint
        users_file = Path(__file__).parent.parent / "api" / "users.py"
        assert users_file.exists(), "api/users.py should exist"

        content = users_file.read_text()

        # Should import auth dependency
        assert (
            "from dependencies.auth import" in content
            or "from api.auth import" in content
        ), "users.py should import auth dependencies"

        # Should use get_current_user or similar
        assert (
            "get_current_user" in content
        ), "users.py should use auth dependency"

    def test_agents_endpoint_has_auth(self):
        """Agents endpoint should require authentication."""
        agents_file = Path(__file__).parent.parent / "api" / "agents.py"
        assert agents_file.exists(), "api/agents.py should exist"

        content = agents_file.read_text()

        # Should have auth dependency
        assert (
            "get_current_user" in content
            or "Depends" in content
        ), "agents.py should have authentication"

    def test_groups_endpoint_has_auth(self):
        """Groups endpoint should require authentication."""
        groups_file = Path(__file__).parent.parent / "api" / "groups.py"
        assert groups_file.exists(), "api/groups.py should exist"

        content = groups_file.read_text()

        # Should have auth dependency
        assert (
            "get_current_user" in content
            or "Depends" in content
        ), "groups.py should have authentication"


class TestFrontendAuthReliance:
    """Tests that verify frontend can rely on backend auth without aggressive checks."""

    def test_no_aggressive_auth_check_in_control_plane_ui(self):
        """Verify control-plane App.jsx doesn't have aggressive auth check on mount."""
        control_plane_app_jsx = (
            Path(__file__).parent.parent / "ui" / "src" / "App.jsx"
        )

        if not control_plane_app_jsx.exists():
            pytest.skip("App.jsx not found (may not be built yet)")

        content = control_plane_app_jsx.read_text()

        # Should NOT have aggressive redirect to login on mount
        # Either no redirect at all, or should have comment explaining removal
        has_redirect = "window.location.href = '/auth/login'" in content
        has_explanation = (
            "Removed aggressive auth check" in content
            or "let server-side auth handle it" in content
        )

        assert (
            not has_redirect or has_explanation
        ), "App.jsx should not aggressively redirect to login on mount without explanation"

        # Should have comment explaining that server-side auth is used
        assert (
            has_explanation
        ), "Should have comment explaining that server-side auth handles authentication"

    def test_no_aggressive_auth_check_in_tasks_ui(self):
        """Verify tasks App.jsx doesn't have aggressive redirect on auth failure."""
        tasks_app_jsx = Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.jsx"

        if not tasks_app_jsx.exists():
            pytest.skip("tasks/ui/src/App.jsx not found (may not be built yet)")

        content = tasks_app_jsx.read_text()

        # Check for the specific pattern we removed
        has_aggressive_redirect = (
            "window.location.href = 'http://localhost:6001/auth/login'" in content
        )
        has_explanation = (
            "without aggressive redirect" in content.lower()
            or "don't redirect" in content.lower()
        )

        assert (
            not has_aggressive_redirect or has_explanation
        ), "tasks App.jsx should not aggressively redirect on auth failure"

    def test_logout_clears_cookie_with_matching_params(self):
        """Logout should delete cookie with parameters matching cookie creation."""
        auth_file = Path(__file__).parent.parent / "api" / "auth.py"
        content = auth_file.read_text()

        # Find cookie deletion
        assert "delete_cookie" in content, "Should have delete_cookie call"

        # Should delete with httponly flag
        assert (
            "httponly=True" in content
        ), "Should set httponly flag when deleting cookie"

        # Should delete with samesite policy
        assert (
            'samesite="lax"' in content or "samesite='lax'" in content
        ), "Should set samesite policy when deleting cookie"

        # Should specify path when deleting
        assert 'path="/"' in content or "path='/" in content, "Should set path when deleting cookie"

    def test_index_html_has_no_cache_headers(self):
        """FastAPI should serve index.html with no-cache headers."""
        app_file = Path(__file__).parent.parent / "app.py"
        content = app_file.read_text()

        # Should have cache-control headers for index.html
        assert (
            "Cache-Control" in content
        ), "Should set Cache-Control header for index.html"
        assert (
            "no-cache, no-store, must-revalidate" in content
        ), "Should have comprehensive no-cache policy"

        # Should also have Pragma and Expires for compatibility
        assert "Pragma" in content, "Should set Pragma header for HTTP/1.0 compatibility"
        assert "Expires" in content, "Should set Expires header"


class TestNginxConfiguration:
    """Tests for nginx cache configuration in tasks service."""

    def test_nginx_prevents_index_html_caching(self):
        """Nginx should prevent caching of index.html."""
        nginx_conf = Path(__file__).parent.parent.parent / "tasks" / "nginx.conf"

        if not nginx_conf.exists():
            pytest.skip("nginx.conf not found")

        content = nginx_conf.read_text()

        # Should have location block for index.html
        assert (
            "location = /index.html" in content
        ), "Should have specific location block for index.html"

        # Should have no-cache headers
        assert (
            'Cache-Control "no-cache, no-store, must-revalidate"' in content
        ), "Should set Cache-Control header in nginx"

        assert (
            'Pragma "no-cache"' in content
        ), "Should set Pragma header in nginx"

        assert 'Expires "0"' in content, "Should set Expires header in nginx"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
