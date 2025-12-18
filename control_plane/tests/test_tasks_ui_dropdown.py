"""
Tests for tasks UI logout dropdown menu functionality.

Tests verify:
1. Dropdown structure in tasks JSX matches control plane
2. User email displayed in dropdown (not next to logout button)
3. Dropdown positioned correctly with CSS
4. CSS classes applied properly
"""

import pytest
from pathlib import Path


class TestTasksUIDropdownStructure:
    """Tests for tasks UI dropdown menu HTML structure in App.jsx."""

    def test_tasks_logout_dropdown_wrapper_exists(self):
        """Tasks logout button should be wrapped in logout-dropdown div."""
        app_jsx = Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.jsx"

        if not app_jsx.exists():
            pytest.skip("tasks App.jsx not found (UI may not be built)")

        content = app_jsx.read_text()

        # Should have logout-dropdown wrapper
        assert (
            'className="logout-dropdown"' in content
        ), "Tasks UI should have logout-dropdown wrapper div"

    def test_tasks_dropdown_menu_element_exists(self):
        """Tasks dropdown menu element should exist in structure."""
        app_jsx = Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.jsx"

        if not app_jsx.exists():
            pytest.skip("tasks App.jsx not found")

        content = app_jsx.read_text()

        # Should have dropdown-menu div
        assert (
            'className="dropdown-menu"' in content
        ), "Tasks UI should have dropdown-menu element"

    def test_tasks_user_email_in_dropdown(self):
        """Tasks user email should be displayed in dropdown menu."""
        app_jsx = Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.jsx"

        if not app_jsx.exists():
            pytest.skip("tasks App.jsx not found")

        content = app_jsx.read_text()

        # Should display currentUser.email inside dropdown-menu
        lines = content.split('\n')
        in_dropdown = False
        has_email = False

        for i, line in enumerate(lines):
            if 'className="dropdown-menu"' in line:
                in_dropdown = True
            elif in_dropdown and 'currentUser.email' in line:
                has_email = True
                break
            elif in_dropdown and '</div>' in line and 'dropdown' in content[max(0, content.find('className="dropdown-menu"')):content.find(line)]:
                # Moved past dropdown-menu
                break

        assert has_email, "Tasks UI user email should be displayed inside dropdown-menu"

    def test_tasks_dropdown_has_user_email_class(self):
        """Tasks dropdown item should have user-email class."""
        app_jsx = Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.jsx"

        if not app_jsx.exists():
            pytest.skip("tasks App.jsx not found")

        content = app_jsx.read_text()

        # Should have dropdown-item user-email class
        assert (
            'className="dropdown-item user-email"' in content
        ), "Tasks UI dropdown item should have user-email class"

    def test_tasks_logout_button_inside_dropdown_wrapper(self):
        """Tasks logout button should be inside logout-dropdown wrapper."""
        app_jsx = Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.jsx"

        if not app_jsx.exists():
            pytest.skip("tasks App.jsx not found")

        content = app_jsx.read_text()

        # Find logout-dropdown and verify logout-btn is inside
        lines = content.split('\n')
        in_dropdown_wrapper = False
        has_logout_btn = False

        for line in lines:
            if 'className="logout-dropdown"' in line:
                in_dropdown_wrapper = True
            elif in_dropdown_wrapper and 'className="nav-link logout-btn"' in line:
                has_logout_btn = True
                break

        assert has_logout_btn, "Tasks UI logout button should be inside logout-dropdown wrapper"

    def test_tasks_no_separate_user_info_div(self):
        """Tasks UI should not have separate user-info div outside dropdown."""
        app_jsx = Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.jsx"

        if not app_jsx.exists():
            pytest.skip("tasks App.jsx not found")

        content = app_jsx.read_text()

        # The old pattern was a separate user-info div with currentUser.email
        # We want to ensure this is NOT present (email should only be in dropdown)
        lines = content.split('\n')

        # Look for user-info div that's NOT inside dropdown-menu
        has_separate_user_info = False
        in_dropdown_menu = False

        for i, line in enumerate(lines):
            if 'className="dropdown-menu"' in line:
                in_dropdown_menu = True
            elif 'className="user-info"' in line and not in_dropdown_menu:
                # Check if this user-info contains the email display
                # Look ahead a few lines
                for j in range(i, min(i + 5, len(lines))):
                    if 'currentUser.email' in lines[j]:
                        has_separate_user_info = True
                        break
            elif '</div>' in line and in_dropdown_menu:
                in_dropdown_menu = False

        assert not has_separate_user_info, "Tasks UI should NOT have separate user-info div outside dropdown (email should only be in dropdown)"


class TestTasksUIDropdownCSS:
    """Tests for tasks UI dropdown menu CSS styling."""

    def test_tasks_logout_dropdown_css_exists(self):
        """CSS for tasks logout-dropdown should exist."""
        app_css = Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.css"

        if not app_css.exists():
            pytest.skip("tasks App.css not found")

        content = app_css.read_text()

        assert (
            '.logout-dropdown' in content
        ), "Tasks UI should have .logout-dropdown CSS class"

    def test_tasks_dropdown_menu_css_exists(self):
        """CSS for tasks dropdown-menu should exist."""
        app_css = Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.css"

        if not app_css.exists():
            pytest.skip("tasks App.css not found")

        content = app_css.read_text()

        assert (
            '.dropdown-menu' in content
        ), "Tasks UI should have .dropdown-menu CSS class"

    def test_tasks_dropdown_menu_positioned_absolute(self):
        """Tasks dropdown menu should be positioned absolutely."""
        app_css = Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.css"

        if not app_css.exists():
            pytest.skip("tasks App.css not found")

        content = app_css.read_text()

        # Find .dropdown-menu block and check for position: absolute
        lines = content.split('\n')
        in_dropdown_menu = False
        has_absolute = False

        for line in lines:
            if '.dropdown-menu' in line and '{' in line or (in_dropdown_menu is False and '.dropdown-menu' in line):
                in_dropdown_menu = True
            elif in_dropdown_menu and 'position:' in line.replace(' ', ''):
                if 'absolute' in line:
                    has_absolute = True
                    break
            elif in_dropdown_menu and '}' in line:
                break

        assert has_absolute, "Tasks UI dropdown menu should have position: absolute"

    def test_tasks_dropdown_hidden_by_default(self):
        """Tasks dropdown should be hidden by default (opacity: 0 or visibility: hidden)."""
        app_css = Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.css"

        if not app_css.exists():
            pytest.skip("tasks App.css not found")

        content = app_css.read_text()

        # Find .dropdown-menu block and check for visibility or opacity
        lines = content.split('\n')
        in_dropdown_menu = False
        is_hidden = False

        for line in lines:
            if '.dropdown-menu' in line and '{' in line or (in_dropdown_menu is False and '.dropdown-menu' in line):
                in_dropdown_menu = True
            elif in_dropdown_menu:
                if 'visibility:' in line.replace(' ', '') and 'hidden' in line:
                    is_hidden = True
                    break
                elif 'opacity:' in line.replace(' ', '') and '0' in line:
                    is_hidden = True
                    break
            elif in_dropdown_menu and '}' in line:
                break

        assert is_hidden, "Tasks UI dropdown should be hidden by default (opacity: 0 or visibility: hidden)"

    def test_tasks_dropdown_hover_shows_menu(self):
        """Hovering tasks dropdown wrapper should show menu."""
        app_css = Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.css"

        if not app_css.exists():
            pytest.skip("tasks App.css not found")

        content = app_css.read_text()

        # Should have .logout-dropdown:hover .dropdown-menu rule
        assert (
            '.logout-dropdown:hover .dropdown-menu' in content
        ), "Tasks UI should have hover rule to show dropdown menu"

    def test_tasks_dropdown_item_css_exists(self):
        """CSS for tasks dropdown-item should exist."""
        app_css = Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.css"

        if not app_css.exists():
            pytest.skip("tasks App.css not found")

        content = app_css.read_text()

        assert (
            '.dropdown-item' in content
        ), "Tasks UI should have .dropdown-item CSS class"

    def test_tasks_user_email_dropdown_item_css_exists(self):
        """CSS for tasks user-email dropdown item should exist."""
        app_css = Path(__file__).parent.parent.parent / "tasks" / "ui" / "src" / "App.css"

        if not app_css.exists():
            pytest.skip("tasks App.css not found")

        content = app_css.read_text()

        assert (
            '.dropdown-item.user-email' in content
        ), "Tasks UI should have .dropdown-item.user-email CSS class"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
