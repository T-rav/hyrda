"""
Tests for OAuth redirect flow.

Tests verify:
1. Redirect parameter passed from tasks to login
2. Login page JavaScript passes redirect to OAuth start
3. OAuth callback redirects back to original URL
4. prompt="select_account" instead of "consent"
"""

import pytest
from pathlib import Path


class TestRedirectParameterFlow:
    """Tests for redirect parameter handling in OAuth flow."""

    def test_login_page_has_redirect_javascript(self):
        """Login page should have JavaScript to handle redirect parameter."""
        login_html = Path(__file__).parent.parent / "templates" / "login.html"

        if not login_html.exists():
            pytest.skip("login.html not found")

        content = login_html.read_text()

        # Should have JavaScript to read redirect from URL
        assert "URLSearchParams" in content, (
            "Should use URLSearchParams to read redirect from URL"
        )

        assert "redirect" in content, "Should handle redirect parameter"

    def test_login_page_modifies_oauth_button_href(self):
        """Login page JavaScript should modify OAuth button href with redirect."""
        login_html = Path(__file__).parent.parent / "templates" / "login.html"

        if not login_html.exists():
            pytest.skip("login.html not found")

        content = login_html.read_text()

        # Should get redirect from URL params
        assert (
            "urlParams.get('redirect')" in content
            or 'urlParams.get("redirect")' in content
        ), "Should read redirect parameter from URL"

        # Should modify button href
        assert "btn.href" in content or ".href =" in content, (
            "Should modify button href with redirect parameter"
        )

        # Should append redirect to /auth/start
        assert "/auth/start" in content and "redirect" in content, (
            "Should append redirect to /auth/start URL"
        )

    def test_oauth_start_accepts_redirect_parameter(self):
        """OAuth start endpoint should accept redirect parameter."""
        auth_file = Path(__file__).parent.parent / "api" / "auth.py"
        content = auth_file.read_text()

        # Find the auth_start function (formerly auth_login)
        lines = content.split("\n")
        found_start_function = False
        has_redirect_param = False

        for i, line in enumerate(lines):
            if "async def auth_start" in line or "def auth_start(" in line:
                found_start_function = True
                # Check function signature for redirect parameter
                if "redirect" in line or "redirect:" in lines[i : i + 3]:
                    has_redirect_param = True
                    break
                # Check next few lines for redirect parameter
                for j in range(i, min(i + 5, len(lines))):
                    if "redirect" in lines[j] and ":" in lines[j]:
                        has_redirect_param = True
                        break
                if has_redirect_param:
                    break

        assert found_start_function, "Should have auth_start function"
        assert has_redirect_param, "auth_start should accept redirect parameter"

    def test_oauth_stores_redirect_in_session(self):
        """OAuth start should store redirect parameter in session."""
        auth_file = Path(__file__).parent.parent / "api" / "auth.py"
        content = auth_file.read_text()

        # Should store redirect in session as oauth_redirect
        assert (
            'session["oauth_redirect"]' in content
            or "session['oauth_redirect']" in content
        ), "Should store redirect in session as oauth_redirect"

    def test_oauth_callback_reads_redirect_from_session(self):
        """OAuth callback should read redirect from session."""
        auth_file = Path(__file__).parent.parent / "api" / "auth.py"
        content = auth_file.read_text()

        # Should read oauth_redirect from session
        assert (
            'session.get("oauth_redirect"' in content
            or "session.get('oauth_redirect'" in content
        ), "Callback should read oauth_redirect from session"

    def test_oauth_callback_redirects_to_stored_url(self):
        """OAuth callback should redirect to URL from session."""
        auth_file = Path(__file__).parent.parent / "api" / "auth.py"
        content = auth_file.read_text()

        # Find callback function and verify it uses redirect_url
        lines = content.split("\n")
        found_redirect_url = False
        uses_redirect_url = False

        for i, line in enumerate(lines):
            if "redirect_url" in line and "session.get" in line:
                found_redirect_url = True
            if (
                found_redirect_url
                and "RedirectResponse" in line
                and "redirect_url" in line
            ):
                uses_redirect_url = True
                break

        assert found_redirect_url, "Should get redirect_url from session"
        assert uses_redirect_url, "Should use redirect_url in RedirectResponse"

    def test_oauth_callback_defaults_to_root(self):
        """OAuth callback should default to / if no redirect stored."""
        auth_file = Path(__file__).parent.parent / "api" / "auth.py"
        content = auth_file.read_text()

        # Should have default value of "/" for redirect
        assert (
            'session.get("oauth_redirect", "/"' in content
            or "session.get('oauth_redirect', '/" in content
        ), "Should default to / if no redirect parameter"


class TestOAuthPromptParameter:
    """Tests for OAuth prompt parameter."""

    def test_oauth_uses_select_account_prompt(self):
        """OAuth should use prompt='select_account' not 'consent'."""
        auth_file = Path(__file__).parent.parent / "api" / "auth.py"
        content = auth_file.read_text()

        # Should use prompt="select_account"
        assert (
            'prompt="select_account"' in content or "prompt='select_account'" in content
        ), "Should use prompt='select_account' to avoid consent screen every time"

    def test_oauth_does_not_force_consent(self):
        """OAuth should NOT use prompt='consent' which forces consent every time."""
        auth_file = Path(__file__).parent.parent / "api" / "auth.py"
        content = auth_file.read_text()

        # Find authorization_url call
        lines = content.split("\n")
        in_auth_url_call = False
        has_consent_prompt = False

        for i, line in enumerate(lines):
            if "authorization_url" in line:
                in_auth_url_call = True
            if in_auth_url_call:
                if 'prompt="consent"' in line or "prompt='consent'" in line:
                    has_consent_prompt = True
                    break
                if ")" in line and in_auth_url_call:
                    break

        assert not has_consent_prompt, (
            "Should NOT use prompt='consent' - this forces consent screen every time"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
