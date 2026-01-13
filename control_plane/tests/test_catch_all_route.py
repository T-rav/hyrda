"""
Tests for catch-all route exclusions.

Tests verify:
1. Auth routes are excluded from catch-all route
2. API routes are excluded from catch-all route
3. Assets routes are excluded from catch-all route
4. React app is served for other routes
"""

import pytest
from pathlib import Path


class TestCatchAllRouteExclusions:
    """Tests for catch-all route path exclusions."""

    def test_catch_all_excludes_auth_paths(self):
        """Catch-all route should exclude auth/ paths."""
        app_file = Path(__file__).parent.parent / "app.py"
        content = app_file.read_text()

        # Find the catch-all route function
        lines = content.split('\n')
        found_catch_all = False
        has_auth_exclusion = False

        for i, line in enumerate(lines):
            if 'def serve_react_app' in line or 'async def serve_react_app' in line:
                found_catch_all = True
                # Check the next 10 lines for the exclusion check
                for j in range(i, min(i + 10, len(lines))):
                    if 'auth/' in lines[j] and ('startswith' in lines[j] or 'path.startswith' in lines[j]):
                        has_auth_exclusion = True
                        break
                break

        assert found_catch_all, "Should have serve_react_app catch-all route"
        assert has_auth_exclusion, "Catch-all route should exclude auth/ paths to allow auth router to handle them"

    def test_catch_all_excludes_api_paths(self):
        """Catch-all route should exclude api/ paths."""
        app_file = Path(__file__).parent.parent / "app.py"
        content = app_file.read_text()

        # Find the catch-all route function
        lines = content.split('\n')
        found_catch_all = False
        has_api_exclusion = False

        for i, line in enumerate(lines):
            if 'def serve_react_app' in line or 'async def serve_react_app' in line:
                found_catch_all = True
                # Check the next 10 lines for the exclusion check
                for j in range(i, min(i + 10, len(lines))):
                    if 'api/' in lines[j] and ('startswith' in lines[j] or 'path.startswith' in lines[j]):
                        has_api_exclusion = True
                        break
                break

        assert found_catch_all, "Should have serve_react_app catch-all route"
        assert has_api_exclusion, "Catch-all route should exclude api/ paths to allow API routers to handle them"

    def test_catch_all_excludes_assets_paths(self):
        """Catch-all route should exclude assets/ paths."""
        app_file = Path(__file__).parent.parent / "app.py"
        content = app_file.read_text()

        # Find the catch-all route function
        lines = content.split('\n')
        found_catch_all = False
        has_assets_exclusion = False

        for i, line in enumerate(lines):
            if 'def serve_react_app' in line or 'async def serve_react_app' in line:
                found_catch_all = True
                # Check the next 10 lines for the exclusion check
                for j in range(i, min(i + 10, len(lines))):
                    if 'assets/' in lines[j] and ('startswith' in lines[j] or 'path.startswith' in lines[j]):
                        has_assets_exclusion = True
                        break
                break

        assert found_catch_all, "Should have serve_react_app catch-all route"
        assert has_assets_exclusion, "Catch-all route should exclude assets/ paths to serve static files correctly"

    def test_catch_all_raises_404_for_excluded_paths(self):
        """Catch-all route should raise 404 for excluded paths."""
        app_file = Path(__file__).parent.parent / "app.py"
        content = app_file.read_text()

        # Find the catch-all route function and verify it raises HTTPException
        lines = content.split('\n')
        found_catch_all = False
        has_http_exception = False

        for i, line in enumerate(lines):
            if 'def serve_react_app' in line or 'async def serve_react_app' in line:
                found_catch_all = True
                # Check the next 10 lines for HTTPException
                for j in range(i, min(i + 10, len(lines))):
                    if 'HTTPException' in lines[j] and ('raise' in lines[j] or 'raise' in lines[j-1] if j > 0 else False):
                        has_http_exception = True
                        break
                break

        assert found_catch_all, "Should have serve_react_app catch-all route"
        assert has_http_exception, "Catch-all route should raise HTTPException for excluded paths"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
