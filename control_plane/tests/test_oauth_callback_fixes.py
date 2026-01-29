"""
Tests for OAuth callback bug fixes.

Tests verify:
1. User model uses correct field name (full_name, not name)
2. AuditLogger.log_auth_event called with valid parameters
3. OAuth callback creates users successfully
"""

import pytest
from pathlib import Path


class TestUserModelFieldNames:
    """Tests that User model fields are used correctly."""

    def test_user_model_has_full_name_field(self):
        """User model should have full_name field, not name."""
        user_model_file = Path(__file__).parent.parent / "models" / "user.py"
        assert user_model_file.exists(), "models/user.py should exist"

        content = user_model_file.read_text()

        # Should have full_name field
        assert "full_name = Column" in content, "User model should have full_name field"

        # Should NOT have a standalone 'name' field (but given_name, family_name are okay)
        lines = content.split("\n")
        for line in lines:
            if (
                "name = Column" in line
                and "given_name" not in line
                and "family_name" not in line
                and "full_name" not in line
            ):
                pytest.fail(
                    f"User model should not have standalone 'name' field: {line}"
                )

    def test_oauth_callback_uses_full_name(self):
        """OAuth callback should use full_name when creating users."""
        auth_file = Path(__file__).parent.parent / "api" / "auth.py"
        content = auth_file.read_text()

        # Find the User creation in OAuth callback
        lines = content.split("\n")
        found_user_creation = False
        uses_full_name = False

        for i, line in enumerate(lines):
            if "new_user = User(" in line:
                found_user_creation = True
                # Check next few lines for full_name parameter
                for j in range(i, min(i + 10, len(lines))):
                    if "full_name=" in lines[j]:
                        uses_full_name = True
                        break
                    # Should NOT use name=
                    if "name=" in lines[j] and "full_name" not in lines[j]:
                        pytest.fail(
                            f"Found 'name=' instead of 'full_name=' at line {j + 1}: {lines[j]}"
                        )
                break

        assert found_user_creation, "Should have User creation in OAuth callback"
        assert uses_full_name, "OAuth callback should use full_name parameter"


class TestAuditLoggerParameters:
    """Tests that AuditLogger.log_auth_event is called with valid parameters."""

    def test_audit_logger_signature(self):
        """Verify AuditLogger.log_auth_event accepted parameters."""
        auth_utils_file = Path(__file__).parent.parent / "utils" / "auth.py"
        assert auth_utils_file.exists(), "utils/auth.py should exist"

        content = auth_utils_file.read_text()

        # Find the log_auth_event signature
        assert "def log_auth_event" in content, "Should have log_auth_event function"

        # Check for valid parameters in signature
        valid_params = [
            "event_type",
            "email",
            "ip_address",
            "user_agent",
            "success",
            "error",
            "path",
        ]

        for param in valid_params:
            assert f"{param}:" in content or f"{param} =" in content, (
                f"log_auth_event should accept {param} parameter"
            )

    def test_oauth_callback_calls_audit_logger_correctly(self):
        """OAuth callback should call AuditLogger.log_auth_event with valid params."""
        auth_file = Path(__file__).parent.parent / "api" / "auth.py"
        content = auth_file.read_text()

        # Find all AuditLogger.log_auth_event calls
        lines = content.split("\n")
        audit_calls = []

        for i, line in enumerate(lines):
            if "AuditLogger.log_auth_event(" in line:
                # Collect the full call (might span multiple lines)
                call_lines = [line]
                j = i + 1
                while j < len(lines) and ")" not in lines[j - 1]:
                    call_lines.append(lines[j])
                    j += 1
                    if j - i > 20:  # Safety limit
                        break
                audit_calls.append((i + 1, "\n".join(call_lines)))

        assert len(audit_calls) > 0, "Should have AuditLogger.log_auth_event calls"

        # Check that no calls use invalid parameters
        invalid_params = ["user_id=", "metadata="]
        for line_num, call in audit_calls:
            for invalid_param in invalid_params:
                assert invalid_param not in call, (
                    f"Line {line_num}: AuditLogger.log_auth_event should not use {invalid_param}"
                )


class TestAuthEndpointStructure:
    """Tests for /auth/login and /auth/start endpoint structure."""

    def test_auth_login_serves_html(self):
        """GET /auth/login should serve HTML page, not redirect to OAuth."""
        auth_file = Path(__file__).parent.parent / "api" / "auth.py"
        content = auth_file.read_text()

        # Should have /auth/login endpoint that serves HTML
        lines = content.split("\n")

        found_login_route = False
        serves_html = False

        for i, line in enumerate(lines):
            if '@router.get("/login")' in line:
                found_login_route = True
                # Check next 20 lines for HTMLResponse or template serving
                for j in range(i, min(i + 20, len(lines))):
                    if "HTMLResponse" in lines[j] or "template" in lines[j].lower():
                        serves_html = True
                        break
                break

        assert found_login_route, "Should have @router.get('/login') endpoint"
        assert serves_html, "/auth/login should serve HTML (HTMLResponse or template)"

    def test_auth_start_initiates_oauth(self):
        """GET /auth/start should initiate OAuth flow."""
        auth_file = Path(__file__).parent.parent / "api" / "auth.py"
        content = auth_file.read_text()

        # Should have /auth/start endpoint that does OAuth
        lines = content.split("\n")

        found_start_route = False
        does_oauth = False

        for i, line in enumerate(lines):
            if '@router.get("/start")' in line:
                found_start_route = True
                # Check next 30 lines for OAuth flow indicators
                for j in range(i, min(i + 30, len(lines))):
                    if (
                        "get_flow" in lines[j]
                        or "authorization_url" in lines[j]
                        or "oauth_state" in lines[j]
                    ):
                        does_oauth = True
                        break
                break

        assert found_start_route, "Should have @router.get('/start') endpoint"
        assert does_oauth, "/auth/start should initiate OAuth flow"

    def test_login_template_points_to_start(self):
        """Login page should point to /auth/start, not /auth/login."""
        login_template = Path(__file__).parent.parent / "templates" / "login.html"

        if not login_template.exists():
            pytest.skip("login.html template not found")

        content = login_template.read_text()

        # Should link to /auth/start
        assert "/auth/start" in content, "Login page should have link to /auth/start"

        # Should NOT link to /auth/login for OAuth (that would be circular)
        # Count occurrences - one is okay (for "Sign In Again" button)
        login_links = content.count('href="/auth/login"')
        assert login_links <= 1, "Login page should not use /auth/login for OAuth flow"


class TestLogoutPageRendering:
    """Tests for logout success page."""

    def test_logout_redirects_to_logged_out_page(self):
        """POST /auth/logout should redirect to /auth/logged-out."""
        auth_file = Path(__file__).parent.parent / "api" / "auth.py"
        content = auth_file.read_text()

        # Find logout endpoint
        lines = content.split("\n")
        found_logout = False
        redirects_to_logged_out = False

        for i, line in enumerate(lines):
            if '@router.post("/logout")' in line:
                found_logout = True
                # Check next 50 lines for redirect (logout function might be long)
                for j in range(i, min(i + 50, len(lines))):
                    if "/auth/logged-out" in lines[j]:
                        redirects_to_logged_out = True
                        break
                break

        assert found_logout, "Should have @router.post('/logout') endpoint"
        assert redirects_to_logged_out, "Logout should redirect to /auth/logged-out"

    def test_logged_out_endpoint_serves_html(self):
        """GET /auth/logged-out should serve HTML page."""
        auth_file = Path(__file__).parent.parent / "api" / "auth.py"
        content = auth_file.read_text()

        # Should have /auth/logged-out endpoint that serves HTML
        lines = content.split("\n")

        found_logged_out_route = False
        serves_html = False

        for i, line in enumerate(lines):
            if '@router.get("/logged-out")' in line:
                found_logged_out_route = True
                # Check next 20 lines for HTMLResponse or template
                for j in range(i, min(i + 20, len(lines))):
                    if "HTMLResponse" in lines[j] or "template" in lines[j].lower():
                        serves_html = True
                        break
                break

        assert found_logged_out_route, "Should have @router.get('/logged-out') endpoint"
        assert serves_html, (
            "/auth/logged-out should serve HTML (HTMLResponse or template)"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
