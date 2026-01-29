"""
Tests for logout dropdown menu functionality.

Tests verify:
1. Dropdown structure in JSX
2. User email displayed in dropdown
3. Dropdown positioned correctly
4. CSS classes applied properly
"""

import pytest
from pathlib import Path


class TestLogoutDropdownStructure:
    """Tests for dropdown menu HTML structure in App.jsx."""

    def test_logout_dropdown_wrapper_exists(self):
        """Logout button should be wrapped in logout-dropdown div."""
        app_jsx = Path(__file__).parent.parent / "ui" / "src" / "App.jsx"

        if not app_jsx.exists():
            pytest.skip("App.jsx not found (UI may not be built)")

        content = app_jsx.read_text()

        # Should have logout-dropdown wrapper
        assert 'className="logout-dropdown"' in content, (
            "Should have logout-dropdown wrapper div"
        )

    def test_dropdown_menu_element_exists(self):
        """Dropdown menu element should exist in structure."""
        app_jsx = Path(__file__).parent.parent / "ui" / "src" / "App.jsx"

        if not app_jsx.exists():
            pytest.skip("App.jsx not found")

        content = app_jsx.read_text()

        # Should have dropdown-menu div
        assert 'className="dropdown-menu"' in content, (
            "Should have dropdown-menu element"
        )

    def test_user_email_in_dropdown(self):
        """User email should be displayed in dropdown menu."""
        app_jsx = Path(__file__).parent.parent / "ui" / "src" / "App.jsx"

        if not app_jsx.exists():
            pytest.skip("App.jsx not found")

        content = app_jsx.read_text()

        # Should display currentUserEmail inside dropdown-menu
        lines = content.split("\n")
        in_dropdown = False
        has_email = False

        for i, line in enumerate(lines):
            if 'className="dropdown-menu"' in line:
                in_dropdown = True
            elif in_dropdown and "currentUserEmail" in line:
                has_email = True
                break
            elif (
                in_dropdown
                and "</div>" in line
                and "dropdown-menu" in lines[max(0, i - 10) : i + 1]
            ):
                # End of dropdown-menu
                break

        assert has_email, "User email should be displayed inside dropdown-menu"

    def test_dropdown_has_user_email_class(self):
        """Dropdown item should have user-email class."""
        app_jsx = Path(__file__).parent.parent / "ui" / "src" / "App.jsx"

        if not app_jsx.exists():
            pytest.skip("App.jsx not found")

        content = app_jsx.read_text()

        # Should have dropdown-item user-email class
        assert 'className="dropdown-item user-email"' in content, (
            "Dropdown item should have user-email class"
        )

    def test_logout_button_inside_dropdown_wrapper(self):
        """Logout button should be inside logout-dropdown wrapper."""
        app_jsx = Path(__file__).parent.parent / "ui" / "src" / "App.jsx"

        if not app_jsx.exists():
            pytest.skip("App.jsx not found")

        content = app_jsx.read_text()

        # Find logout-dropdown and verify logout-btn is inside
        lines = content.split("\n")
        in_dropdown_wrapper = False
        has_logout_btn = False

        for line in lines:
            if 'className="logout-dropdown"' in line:
                in_dropdown_wrapper = True
            elif in_dropdown_wrapper and 'className="nav-link logout-btn"' in line:
                has_logout_btn = True
                break
            elif in_dropdown_wrapper and "</div>" in line and in_dropdown_wrapper:
                # Check if this might be closing the wrapper
                if "logout-dropdown" not in line:
                    continue
                break

        assert has_logout_btn, "Logout button should be inside logout-dropdown wrapper"


class TestLogoutDropdownCSS:
    """Tests for dropdown menu CSS styling."""

    def test_logout_dropdown_css_exists(self):
        """CSS for logout-dropdown should exist."""
        app_css = Path(__file__).parent.parent / "ui" / "src" / "App.css"

        if not app_css.exists():
            pytest.skip("App.css not found")

        content = app_css.read_text()

        assert ".logout-dropdown" in content, "Should have .logout-dropdown CSS class"

    def test_dropdown_menu_css_exists(self):
        """CSS for dropdown-menu should exist."""
        app_css = Path(__file__).parent.parent / "ui" / "src" / "App.css"

        if not app_css.exists():
            pytest.skip("App.css not found")

        content = app_css.read_text()

        assert ".dropdown-menu" in content, "Should have .dropdown-menu CSS class"

    def test_dropdown_menu_positioned_absolute(self):
        """Dropdown menu should be positioned absolutely."""
        app_css = Path(__file__).parent.parent / "ui" / "src" / "App.css"

        if not app_css.exists():
            pytest.skip("App.css not found")

        content = app_css.read_text()

        # Find .dropdown-menu block and check for position: absolute
        lines = content.split("\n")
        in_dropdown_menu = False
        has_absolute = False

        for line in lines:
            if (
                ".dropdown-menu" in line
                and "{" in line
                or (in_dropdown_menu is False and ".dropdown-menu" in line)
            ):
                in_dropdown_menu = True
            elif in_dropdown_menu and "position:" in line.replace(" ", ""):
                if "absolute" in line:
                    has_absolute = True
                    break
            elif in_dropdown_menu and "}" in line:
                break

        assert has_absolute, "Dropdown menu should have position: absolute"

    def test_dropdown_hidden_by_default(self):
        """Dropdown should be hidden by default (opacity: 0 or visibility: hidden)."""
        app_css = Path(__file__).parent.parent / "ui" / "src" / "App.css"

        if not app_css.exists():
            pytest.skip("App.css not found")

        content = app_css.read_text()

        # Find .dropdown-menu block and check for visibility or opacity
        lines = content.split("\n")
        in_dropdown_menu = False
        is_hidden = False

        for line in lines:
            if (
                ".dropdown-menu" in line
                and "{" in line
                or (in_dropdown_menu is False and ".dropdown-menu" in line)
            ):
                in_dropdown_menu = True
            elif in_dropdown_menu:
                if "visibility:" in line.replace(" ", "") and "hidden" in line:
                    is_hidden = True
                    break
                elif "opacity:" in line.replace(" ", "") and "0" in line:
                    is_hidden = True
                    break
            elif in_dropdown_menu and "}" in line:
                break

        assert is_hidden, (
            "Dropdown should be hidden by default (opacity: 0 or visibility: hidden)"
        )

    def test_dropdown_hover_shows_menu(self):
        """Hovering dropdown wrapper should show menu."""
        app_css = Path(__file__).parent.parent / "ui" / "src" / "App.css"

        if not app_css.exists():
            pytest.skip("App.css not found")

        content = app_css.read_text()

        # Should have .logout-dropdown:hover .dropdown-menu rule
        assert ".logout-dropdown:hover .dropdown-menu" in content, (
            "Should have hover rule to show dropdown menu"
        )

    def test_dropdown_item_css_exists(self):
        """CSS for dropdown-item should exist."""
        app_css = Path(__file__).parent.parent / "ui" / "src" / "App.css"

        if not app_css.exists():
            pytest.skip("App.css not found")

        content = app_css.read_text()

        assert ".dropdown-item" in content, "Should have .dropdown-item CSS class"

    def test_user_email_dropdown_item_css_exists(self):
        """CSS for user-email dropdown item should exist."""
        app_css = Path(__file__).parent.parent / "ui" / "src" / "App.css"

        if not app_css.exists():
            pytest.skip("App.css not found")

        content = app_css.read_text()

        assert ".dropdown-item.user-email" in content, (
            "Should have .dropdown-item.user-email CSS class"
        )


class TestLogoutDropdownConditional:
    """Tests for conditional rendering of dropdown based on user email."""

    def test_dropdown_menu_conditional_on_user_email(self):
        """Dropdown menu should only render when currentUserEmail exists."""
        app_jsx = Path(__file__).parent.parent / "ui" / "src" / "App.jsx"

        if not app_jsx.exists():
            pytest.skip("App.jsx not found")

        content = app_jsx.read_text()

        # Should have conditional check for currentUserEmail before dropdown-menu
        lines = content.split("\n")
        found_conditional = False
        found_dropdown_menu = False

        for i, line in enumerate(lines):
            if "currentUserEmail &&" in line or "{currentUserEmail &&" in line:
                # Check next few lines for dropdown-menu
                for j in range(i, min(i + 10, len(lines))):
                    if "dropdown-menu" in lines[j]:
                        found_conditional = True
                        found_dropdown_menu = True
                        break
                if found_conditional:
                    break

        assert found_conditional and found_dropdown_menu, (
            "Dropdown menu should be conditionally rendered based on currentUserEmail"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
