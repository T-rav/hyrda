"""Tests for profile agent tool imports.

Verifies that research tools can be imported correctly from the system agents.
"""

import pytest


def test_internal_search_tool_import():
    """Test that internal search tool can be imported from correct path."""
    try:
        from agents.system.research.tools.internal_search import InternalSearchTool

        # Should be able to instantiate (even if it fails due to missing config)
        assert InternalSearchTool is not None
        assert callable(InternalSearchTool)
    except ImportError as e:
        pytest.fail(f"Failed to import InternalSearchTool: {e}")


def test_sec_query_tool_import():
    """Test that SEC query tool can be imported from correct path."""
    try:
        from agents.system.research.tools.sec_query import SECQueryTool

        # Should be able to import the class
        assert SECQueryTool is not None
        assert callable(SECQueryTool)
    except ImportError as e:
        pytest.fail(f"Failed to import SECQueryTool: {e}")


def test_profile_utils_singleton_initialization():
    """Test that profile utils can initialize tool singletons without crashing."""
    from external_agents.profile.utils import (
        internal_search_tool,
        sec_query_tool,
    )

    # These may return None if configuration is missing, but should not crash
    # The important thing is that the imports work
    try:
        internal_tool = internal_search_tool()
        # May be None, but should not raise ImportError
        assert internal_tool is None or hasattr(internal_tool, '__call__')
    except ImportError:
        pytest.fail("internal_search_tool() raised ImportError - imports are broken")

    try:
        sec_tool = sec_query_tool()
        # May be None, but should not raise ImportError
        assert sec_tool is None or hasattr(sec_tool, '__call__')
    except ImportError:
        pytest.fail("sec_query_tool() raised ImportError - imports are broken")


def test_web_search_tool_available():
    """Test that web search tool is available to profile agent."""
    try:
        from agents.system.research.tools.web_search_tool import web_search_tool

        # Should be importable
        assert web_search_tool is not None
        assert callable(web_search_tool)
    except ImportError as e:
        pytest.fail(f"Failed to import web_search_tool: {e}")
