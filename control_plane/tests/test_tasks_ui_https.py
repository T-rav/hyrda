"""
Tests for tasks UI using HTTPS URLs for control plane.

Tests verify:
1. Tasks UI uses HTTPS URLs for control plane auth endpoints
2. Tasks UI uses HTTPS URLs for control plane API endpoints
3. No HTTP URLs remain for control plane communication
"""

import pytest
from pathlib import Path


class TestTasksUIHTTPS:
    """Tests for tasks UI using HTTPS for control plane."""

    def test_tasks_ui_uses_https_for_auth_login(self):
        """Tasks UI should use HTTPS for control plane login endpoint."""
        tasks_app_jsx = (
            Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.jsx"
        )

        if not tasks_app_jsx.exists():
            pytest.skip("tasks App.jsx not found")

        content = tasks_app_jsx.read_text()

        # Should use https://localhost:6001/auth/login
        assert (
            "https://localhost:6001/auth/login" in content
        ), "Tasks UI should use HTTPS for control plane login URL"

        # Should NOT use http://localhost:6001/auth/login
        assert (
            "http://localhost:6001/auth/login" not in content
        ), "Tasks UI should NOT use HTTP for control plane login URL (must use HTTPS)"

    def test_tasks_ui_uses_https_for_auth_logout(self):
        """Tasks UI should use HTTPS for control plane logout endpoint."""
        tasks_app_jsx = (
            Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.jsx"
        )

        if not tasks_app_jsx.exists():
            pytest.skip("tasks App.jsx not found")

        content = tasks_app_jsx.read_text()

        # Should use https://localhost:6001/auth/logout
        assert (
            "https://localhost:6001/auth/logout" in content
        ), "Tasks UI should use HTTPS for control plane logout URL"

        # Should NOT use http://localhost:6001/auth/logout
        assert (
            "http://localhost:6001/auth/logout" not in content
        ), "Tasks UI should NOT use HTTP for control plane logout URL (must use HTTPS)"

    def test_tasks_ui_uses_https_for_users_api(self):
        """Tasks UI should use HTTPS for control plane users API."""
        tasks_app_jsx = (
            Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.jsx"
        )

        if not tasks_app_jsx.exists():
            pytest.skip("tasks App.jsx not found")

        content = tasks_app_jsx.read_text()

        # Should use https://localhost:6001/api/users/me
        assert (
            "https://localhost:6001/api/users/me" in content
        ), "Tasks UI should use HTTPS for control plane users API"

        # Should NOT use http://localhost:6001/api/users/me
        assert (
            "http://localhost:6001/api/users/me" not in content
        ), "Tasks UI should NOT use HTTP for control plane users API (must use HTTPS)"

    def test_tasks_ui_no_http_control_plane_urls(self):
        """Tasks UI should not have any HTTP URLs for control plane (port 6001)."""
        tasks_app_jsx = (
            Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.jsx"
        )

        if not tasks_app_jsx.exists():
            pytest.skip("tasks App.jsx not found")

        content = tasks_app_jsx.read_text()

        # Count occurrences of http://localhost:6001
        http_count = content.count("http://localhost:6001")

        assert (
            http_count == 0
        ), f"Tasks UI should NOT have any HTTP URLs for control plane (found {http_count} occurrences). Control plane runs on HTTPS."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
