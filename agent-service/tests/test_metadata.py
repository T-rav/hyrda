"""Tests for agent metadata decorator."""

from agents.metadata import agent_metadata


class TestAgentMetadataDecorator:
    """Test suite for @agent_metadata decorator."""

    def test_decorator_attaches_metadata(self):
        """Test that decorator attaches __agent_metadata__ to function."""

        @agent_metadata(
            display_name="Test Agent",
            description="A test agent",
            aliases=["test", "agent"],
            is_system=False,
        )
        def test_func():
            return "result"

        assert hasattr(test_func, "__agent_metadata__")
        metadata = test_func.__agent_metadata__

        assert metadata["display_name"] == "Test Agent"
        assert metadata["description"] == "A test agent"
        assert metadata["aliases"] == ["test", "agent"]
        assert metadata["is_system"] is False

    def test_decorated_function_remains_callable(self):
        """Test that decorated functions remain callable."""

        @agent_metadata(
            display_name="Callable Test", description="Test callable", aliases=[]
        )
        def test_func(x, y):
            return x + y

        # Function should still be callable
        result = test_func(5, 3)
        assert result == 8

    def test_decorated_function_returns_correct_value(self):
        """Test that decorated function returns expected value."""

        @agent_metadata(
            display_name="Return Test", description="Test return", aliases=[]
        )
        def build_agent():
            return {"agent": "graph"}

        result = build_agent()
        assert result == {"agent": "graph"}

    def test_decorator_with_empty_aliases(self):
        """Test decorator works with empty aliases list."""

        @agent_metadata(
            display_name="No Aliases", description="Agent with no aliases", aliases=[]
        )
        def test_func():
            return None

        metadata = test_func.__agent_metadata__
        assert metadata["aliases"] == []

    def test_decorator_with_none_aliases(self):
        """Test decorator works with None aliases (uses default)."""

        @agent_metadata(
            display_name="None Aliases", description="Agent with None aliases"
        )
        def test_func():
            return None

        metadata = test_func.__agent_metadata__
        assert metadata["aliases"] == []

    def test_decorator_system_agent_true(self):
        """Test decorator with is_system=True."""

        @agent_metadata(
            display_name="System Agent",
            description="A system agent",
            aliases=["sys"],
            is_system=True,
        )
        def test_func():
            return None

        metadata = test_func.__agent_metadata__
        assert metadata["is_system"] is True

    def test_decorator_system_agent_false(self):
        """Test decorator with is_system=False (default)."""

        @agent_metadata(
            display_name="Regular Agent", description="A regular agent", aliases=[]
        )
        def test_func():
            return None

        metadata = test_func.__agent_metadata__
        assert metadata["is_system"] is False

    def test_decorator_with_multiple_aliases(self):
        """Test decorator with multiple aliases."""

        @agent_metadata(
            display_name="Multi Alias",
            description="Multiple aliases",
            aliases=["alias1", "alias2", "alias3"],
        )
        def test_func():
            return None

        metadata = test_func.__agent_metadata__
        assert len(metadata["aliases"]) == 3
        assert "alias1" in metadata["aliases"]
        assert "alias2" in metadata["aliases"]
        assert "alias3" in metadata["aliases"]

    def test_decorator_preserves_function_name(self):
        """Test that decorator preserves function name."""

        @agent_metadata(display_name="Name Test", description="Test name", aliases=[])
        def my_agent_function():
            return None

        assert my_agent_function.__name__ == "my_agent_function"

    def test_decorator_preserves_docstring(self):
        """Test that decorator preserves function docstring."""

        @agent_metadata(
            display_name="Docstring Test", description="Test docstring", aliases=[]
        )
        def test_func():
            """This is a test docstring."""
            return None

        assert test_func.__doc__ == "This is a test docstring."

    def test_decorator_with_function_args(self):
        """Test decorated function with arguments."""

        @agent_metadata(display_name="Args Test", description="Test args", aliases=[])
        def test_func(a, b, c=None):
            return (a, b, c)

        result = test_func(1, 2, c=3)
        assert result == (1, 2, 3)

    def test_decorator_with_kwargs(self):
        """Test decorated function with **kwargs."""

        @agent_metadata(
            display_name="Kwargs Test", description="Test kwargs", aliases=[]
        )
        def test_func(**kwargs):
            return kwargs

        result = test_func(x=1, y=2, z=3)
        assert result == {"x": 1, "y": 2, "z": 3}

    def test_multiple_decorated_functions_independent(self):
        """Test that multiple decorated functions have independent metadata."""

        @agent_metadata(
            display_name="Agent 1", description="First agent", aliases=["a1"]
        )
        def agent1():
            return "agent1"

        @agent_metadata(
            display_name="Agent 2", description="Second agent", aliases=["a2"]
        )
        def agent2():
            return "agent2"

        metadata1 = agent1.__agent_metadata__
        metadata2 = agent2.__agent_metadata__

        assert metadata1["display_name"] == "Agent 1"
        assert metadata2["display_name"] == "Agent 2"
        assert metadata1["aliases"] == ["a1"]
        assert metadata2["aliases"] == ["a2"]

    def test_decorator_metadata_structure(self):
        """Test that metadata has correct structure."""

        @agent_metadata(
            display_name="Structure Test",
            description="Test structure",
            aliases=["test"],
            is_system=True,
        )
        def test_func():
            return None

        metadata = test_func.__agent_metadata__

        # Check all expected keys exist
        assert "display_name" in metadata
        assert "description" in metadata
        assert "aliases" in metadata
        assert "is_system" in metadata

        # Check types
        assert isinstance(metadata["display_name"], str)
        assert isinstance(metadata["description"], str)
        assert isinstance(metadata["aliases"], list)
        assert isinstance(metadata["is_system"], bool)

    def test_real_agent_pattern_research(self):
        """Test decorator matches real research agent pattern."""

        @agent_metadata(
            display_name="Research Agent",
            description="Deep research agent for comprehensive company analysis",
            aliases=["research", "deep_research"],
            is_system=True,
        )
        def research_agent():
            """Build and return research agent graph."""
            return "mock_research_graph"

        # Verify it's callable
        result = research_agent()
        assert result == "mock_research_graph"

        # Verify metadata
        metadata = research_agent.__agent_metadata__
        assert metadata["display_name"] == "Research Agent"
        assert metadata["is_system"] is True
        assert "research" in metadata["aliases"]
        assert "deep_research" in metadata["aliases"]

    def test_real_agent_pattern_help(self):
        """Test decorator matches real help agent pattern."""

        @agent_metadata(
            display_name="Help Agent",
            description="List available bot agents and their aliases (filtered by your access)",
            aliases=["help", "agents"],
            is_system=False,
        )
        def help_agent():
            """Build and return help agent graph."""
            return "mock_help_graph"

        # Verify it's callable
        result = help_agent()
        assert result == "mock_help_graph"

        # Verify metadata
        metadata = help_agent.__agent_metadata__
        assert metadata["display_name"] == "Help Agent"
        assert metadata["is_system"] is False
        assert "help" in metadata["aliases"]
        assert "agents" in metadata["aliases"]
