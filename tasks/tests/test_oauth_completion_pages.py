"""Tests for OAuth completion pages (success and error templates)."""

from pathlib import Path


class TestOAuthCompletionPages:
    """Test that OAuth completion templates exist and are properly structured."""

    def test_oauth_success_template_exists(self):
        """Test that the OAuth success template file exists."""
        template_path = (
            Path(__file__).parent.parent / "templates" / "oauth_success.html"
        )
        assert template_path.exists(), "oauth_success.html template should exist"

    def test_oauth_error_template_exists(self):
        """Test that the OAuth error template file exists."""
        template_path = Path(__file__).parent.parent / "templates" / "oauth_error.html"
        assert template_path.exists(), "oauth_error.html template should exist"

    def test_oauth_success_template_structure(self):
        """Test that oauth_success.html contains required elements."""
        template_path = (
            Path(__file__).parent.parent / "templates" / "oauth_success.html"
        )
        content = template_path.read_text()

        # Check for essential elements
        assert "Authentication Successful" in content
        assert "credential_name" in content  # Jinja2 variable
        assert "closeWindow()" in content  # Auto-close function
        assert "countdown" in content  # Countdown timer
        assert "window.close()" in content  # Auto-close call

    def test_oauth_error_template_structure(self):
        """Test that oauth_error.html contains required elements."""
        template_path = Path(__file__).parent.parent / "templates" / "oauth_error.html"
        content = template_path.read_text()

        # Check for essential elements
        assert "Authentication Failed" in content
        assert "{% if error %}" in content  # Jinja2 conditional for error display
        assert "{{ error }}" in content  # Jinja2 variable for error message
        assert "window.close()" in content  # Close button functionality

    def test_oauth_success_has_auto_close_timer(self):
        """Test that success page has countdown timer logic."""
        template_path = (
            Path(__file__).parent.parent / "templates" / "oauth_success.html"
        )
        content = template_path.read_text()

        # Check countdown timer implementation
        assert "let countdown = 3" in content or "countdown = 3" in content
        assert "setInterval" in content or "setTimeout" in content
        assert "countdownElement" in content or "countdown" in content

    def test_oauth_templates_are_valid_html(self):
        """Test that templates contain basic HTML structure."""
        for template_name in ["oauth_success.html", "oauth_error.html"]:
            template_path = Path(__file__).parent.parent / "templates" / template_name
            content = template_path.read_text()

            # Check basic HTML5 structure
            assert "<!DOCTYPE html>" in content
            assert "<html" in content
            assert "<head>" in content
            assert "<body>" in content
            assert "</html>" in content

    def test_oauth_templates_have_styling(self):
        """Test that templates include CSS styling."""
        for template_name in ["oauth_success.html", "oauth_error.html"]:
            template_path = Path(__file__).parent.parent / "templates" / template_name
            content = template_path.read_text()

            # Check for CSS styling
            assert "<style>" in content
            assert "</style>" in content
            assert "background" in content  # Should have some background styling
            assert "color" in content  # Should have color styling

    def test_oauth_templates_are_mobile_responsive(self):
        """Test that templates include viewport meta tag for mobile."""
        for template_name in ["oauth_success.html", "oauth_error.html"]:
            template_path = Path(__file__).parent.parent / "templates" / template_name
            content = template_path.read_text()

            # Check for responsive design meta tag
            assert 'name="viewport"' in content
            assert "width=device-width" in content
