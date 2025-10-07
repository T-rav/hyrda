"""Tests for BaseAgent."""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.agent_test_utils import AgentContextBuilder, TestAgentFactory


class TestBaseAgent:
    """Tests for BaseAgent"""

    def test_agent_requires_name(self):
        """Test that agent must define name"""
        invalid_agent_class = TestAgentFactory.create_simple_agent(name="")

        with pytest.raises(ValueError, match="must define 'name' attribute"):
            invalid_agent_class()

    def test_agent_with_valid_name(self):
        """Test agent with valid name"""
        valid_agent_class = TestAgentFactory.create_simple_agent(name="valid")
        agent = valid_agent_class()

        assert agent.name == "valid"

    def test_validate_context_valid(self):
        """Test context validation with valid context"""
        agent_class = TestAgentFactory.create_simple_agent(name="test")
        agent = agent_class()

        context = AgentContextBuilder.default()

        assert agent.validate_context(context) is True

    def test_validate_context_missing_fields(self):
        """Test context validation with missing fields"""
        agent_class = TestAgentFactory.create_simple_agent(name="test")
        agent = agent_class()

        context = AgentContextBuilder.invalid_missing_channel()

        assert agent.validate_context(context) is False

    def test_get_info(self):
        """Test getting agent info"""
        agent_class = TestAgentFactory.create_agent_with_aliases(
            name="test", aliases=["t", "tst"]
        )
        agent = agent_class()

        info = agent.get_info()

        assert info["name"] == "test"
        assert info["aliases"] == ["t", "tst"]
        assert "description" in info
