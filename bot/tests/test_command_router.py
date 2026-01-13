"""Tests for CommandRouter (HTTP-based architecture)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.router import CommandRouter


class TestCommandRouter:
    """Tests for CommandRouter"""

    def test_route_research_agent_with_at_symbol(self):
        """Test routing to research agent with @ prefix"""
        router = CommandRouter()

        agent_info, query, primary_name = router.route("@research tell me about AI")

        assert agent_info is not None
        assert agent_info["name"] == "research"
        assert query == "tell me about ai"
        assert primary_name == "research"

    def test_route_research_agent_with_colon(self):
        """Test routing to research agent with colon format"""
        router = CommandRouter()

        agent_info, query, primary_name = router.route("research: what is ML?")

        assert agent_info is not None
        assert agent_info["name"] == "research"
        assert query == "what is ml?"
        assert primary_name == "research"

    def test_route_research_agent_without_prefix(self):
        """Test routing to research agent without special prefix"""
        router = CommandRouter()

        agent_info, query, primary_name = router.route("research latest trends")

        assert agent_info is not None
        assert agent_info["name"] == "research"
        assert query == "latest trends"
        assert primary_name == "research"

    def test_route_via_alias(self):
        """Test routing to agent via alias"""
        router = CommandRouter()

        agent_info, query, primary_name = router.route("@investigate deep dive topic")

        assert agent_info is not None
        assert agent_info["name"] == "research"  # Resolves to primary name
        assert query == "deep dive topic"
        assert primary_name == "research"

    def test_route_profile_agent(self):
        """Test routing to profile agent"""
        router = CommandRouter()

        agent_info, query, primary_name = router.route("@profile company analysis")

        assert agent_info is not None
        assert agent_info["name"] == "profile"
        assert query == "company analysis"
        assert primary_name == "profile"

    def test_route_meddic_agent(self):
        """Test routing to meddic agent"""
        router = CommandRouter()

        agent_info, query, primary_name = router.route("@meddic deal review")

        assert agent_info is not None
        assert agent_info["name"] == "meddic"
        assert query == "deal review"
        assert primary_name == "meddic"

    def test_route_help_agent(self):
        """Test routing to help agent"""
        router = CommandRouter()

        agent_info, query, primary_name = router.route("@help list agents")

        assert agent_info is not None
        assert agent_info["name"] == "help"
        assert query == "list agents"
        assert primary_name == "help"

    def test_route_case_insensitive(self):
        """Test that routing is case-insensitive"""
        router = CommandRouter()

        agent_info, query, primary_name = router.route("@RESEARCH test query")

        assert agent_info is not None
        assert agent_info["name"] == "research"
        assert query == "test query"
        assert primary_name == "research"

    def test_route_unrecognized_command_returns_none(self):
        """Test that unrecognized commands return None"""
        router = CommandRouter()

        agent_info, query, primary_name = router.route("@unknown command")

        assert agent_info is None
        assert query == "@unknown command"  # Returns original text
        assert primary_name is None

    def test_route_no_command_returns_none(self):
        """Test that regular text returns None (no agent routing)"""
        router = CommandRouter()

        agent_info, query, primary_name = router.route("Just regular text")

        assert agent_info is None
        assert query == "Just regular text"  # Returns original text unchanged
        assert primary_name is None

    def test_alias_company_profile_maps_to_profile(self):
        """Test that 'company profile' alias maps to profile agent"""
        router = CommandRouter()

        agent_info, query, primary_name = router.route("company profile: acme corp")

        assert agent_info is not None
        assert agent_info["name"] == "profile"
        assert query == "acme corp"
        assert primary_name == "profile"

    def test_alias_medic_maps_to_meddic(self):
        """Test that 'medic' alias maps to meddic agent"""
        router = CommandRouter()

        agent_info, query, primary_name = router.route("@medic deal analysis")

        assert agent_info is not None
        assert agent_info["name"] == "meddic"
        assert query == "deal analysis"
        assert primary_name == "meddic"
