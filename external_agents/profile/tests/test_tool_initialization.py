"""Tests for tool initialization and import paths."""

import pytest


def test_sec_query_tool_loads():
    """Test that SEC query tool loads correctly with fixed import path."""
    from external_agents.profile.utils import sec_query_tool

    tool = sec_query_tool()

    # Tool should load successfully (not None)
    assert tool is not None, "SEC query tool failed to load - check import path"

    # Verify it's the correct type
    assert hasattr(tool, 'name'), "Tool missing 'name' attribute"
    assert tool.name == "sec_query", f"Expected tool name 'sec_query', got '{tool.name}'"

    # Verify it has the required methods
    assert hasattr(tool, '_arun'), "Tool missing '_arun' method"
    assert hasattr(tool, 'description'), "Tool missing 'description' attribute"


def test_internal_search_tool_loads():
    """Test that internal search tool loads correctly with fixed import path."""
    from external_agents.profile.utils import internal_search_tool

    tool = internal_search_tool()

    # Tool should load successfully (not None)
    assert tool is not None, "Internal search tool failed to load - check import path"

    # Verify it's the correct type
    assert hasattr(tool, 'name'), "Tool missing 'name' attribute"
    assert tool.name == "internal_search", f"Expected tool name 'internal_search', got '{tool.name}'"

    # Verify it has the required methods
    assert hasattr(tool, '_arun'), "Tool missing '_arun' method"
    assert hasattr(tool, 'description'), "Tool missing 'description' attribute"


def test_sec_query_tool_singleton():
    """Test that SEC query tool returns same instance (singleton pattern)."""
    from external_agents.profile.utils import sec_query_tool

    tool1 = sec_query_tool()
    tool2 = sec_query_tool()

    # Should return the same instance
    assert tool1 is tool2, "SEC query tool not following singleton pattern"


def test_internal_search_tool_singleton():
    """Test that internal search tool returns same instance (singleton pattern)."""
    from external_agents.profile.utils import internal_search_tool

    tool1 = internal_search_tool()
    tool2 = internal_search_tool()

    # Should return the same instance
    assert tool1 is tool2, "Internal search tool not following singleton pattern"


def test_tools_have_correct_imports():
    """Test that tool imports are using correct relative paths."""
    import inspect
    from external_agents.profile import utils

    # Get the source code of the utils module
    source = inspect.getsource(utils)

    # Verify correct import paths (relative imports)
    assert "from .tools.sec_query import SECQueryTool" in source, \
        "SEC query tool import should use relative path: 'from .tools.sec_query'"

    assert "from .tools.internal_search import InternalSearchTool" in source, \
        "Internal search tool import should use relative path: 'from .tools.internal_search'"

    # Verify incorrect paths are NOT present
    assert "from agents.system.research.tools.sec_query" not in source, \
        "Found old incorrect import path for SEC query tool"

    assert "from agents.system.research.tools.internal_search" not in source, \
        "Found old incorrect import path for internal search tool"
