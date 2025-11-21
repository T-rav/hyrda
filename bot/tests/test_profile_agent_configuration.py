"""Tests for ProfileAgent configuration."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.profiler.configuration import ProfileConfiguration


class TestProfileConfiguration:
    """Tests for ProfileConfiguration class"""

    def test_from_env_with_defaults(self):
        """Test loading configuration from environment with defaults"""
        with patch.dict(
            os.environ,
            {
                "SEARCH_API": "tavily",
            },
            clear=False,
        ):
            config = ProfileConfiguration.from_env()

        assert config.search_api == "tavily"
        assert config.max_concurrent_research_units > 0
        assert config.max_researcher_iterations > 0
        assert config.max_react_tool_calls > 0

    def test_from_env_custom_values(self):
        """Test loading custom configuration values"""
        with patch.dict(
            os.environ,
            {
                "SEARCH_API": "tavily",
                "MAX_CONCURRENT_RESEARCH_UNITS": "5",
                "MAX_RESEARCHER_ITERATIONS": "8",
                "MAX_REACT_TOOL_CALLS": "12",
            },
            clear=False,
        ):
            config = ProfileConfiguration.from_env()

        assert config.search_api.value == "tavily"
        assert config.max_concurrent_research_units == 5
        assert config.max_researcher_iterations == 8
        assert config.max_react_tool_calls == 12

    def test_from_env_clarification_enabled(self):
        """Test clarification configuration"""
        with patch.dict(
            os.environ,
            {
                "ALLOW_CLARIFICATION": "true",
            },
            clear=False,
        ):
            config = ProfileConfiguration.from_env()

        assert config.allow_clarification is True

    def test_from_env_clarification_disabled(self):
        """Test clarification disabled"""
        with patch.dict(
            os.environ,
            {
                "ALLOW_CLARIFICATION": "false",
            },
            clear=False,
        ):
            config = ProfileConfiguration.from_env()

        assert config.allow_clarification is False

    def test_from_runnable_config(self):
        """Test loading from runnable config"""
        runnable_config = {
            "configurable": {
                "search_api": "tavily",
                "max_concurrent_research_units": 4,
                "max_researcher_iterations": 6,
                "max_react_tool_calls": 10,
                "allow_clarification": False,
            }
        }

        config = ProfileConfiguration.from_runnable_config(runnable_config)

        assert config.search_api == "tavily"
        assert config.max_concurrent_research_units == 4
        assert config.max_researcher_iterations == 6
        assert config.max_react_tool_calls == 10
        assert config.allow_clarification is False

    def test_from_runnable_config_partial(self):
        """Test loading from config with missing values uses defaults"""
        from agents.profiler.configuration import SearchAPI

        runnable_config = {
            "configurable": {
                "search_api": SearchAPI.TAVILY,
                # Other values not provided
            }
        }

        config = ProfileConfiguration.from_runnable_config(runnable_config)

        assert config.search_api == SearchAPI.TAVILY
        # Should have defaults for other values
        assert config.max_concurrent_research_units > 0

    def test_from_runnable_config_empty(self):
        """Test loading from empty config uses all defaults"""
        runnable_config = {"configurable": {}}

        config = ProfileConfiguration.from_runnable_config(runnable_config)

        # Should have all default values
        assert config.max_concurrent_research_units > 0
        assert config.max_researcher_iterations > 0

    def test_pdf_style_configuration(self):
        """Test PDF style configuration"""
        from agents.profiler.configuration import PDFStyle

        with patch.dict(
            os.environ,
            {
                "PDF_STYLE": "minimal",
            },
            clear=False,
        ):
            config = ProfileConfiguration.from_env()

        assert config.pdf_style == PDFStyle.MINIMAL

    def test_model_configuration(self):
        """Test model configuration"""
        with patch.dict(
            os.environ,
            {
                "RESEARCH_MODEL": "openai:gpt-4o",
                "COMPRESSION_MODEL": "openai:gpt-4o-mini",
                "FINAL_REPORT_MODEL": "openai:gpt-4o",
            },
            clear=False,
        ):
            config = ProfileConfiguration.from_env()

        assert config.research_model == "openai:gpt-4o"
        assert config.compression_model == "openai:gpt-4o-mini"
        assert config.final_report_model == "openai:gpt-4o"

    def test_max_tokens_configuration(self):
        """Test max tokens configuration"""
        with patch.dict(
            os.environ,
            {
                "COMPRESSION_MODEL_MAX_TOKENS": "8000",
                "FINAL_REPORT_MODEL_MAX_TOKENS": "16000",
            },
            clear=False,
        ):
            config = ProfileConfiguration.from_env()

        assert config.compression_model_max_tokens == 8000
        assert config.final_report_model_max_tokens == 16000

    def test_invalid_numeric_values_use_defaults(self):
        """Test invalid numeric values raise errors"""
        with (
            patch.dict(
                os.environ,
                {
                    "MAX_CONCURRENT_RESEARCH_UNITS": "not_a_number",
                },
                clear=False,
            ),
            pytest.raises(ValueError),
        ):
            # Should raise ValueError when parsing fails
            ProfileConfiguration.from_env()


class TestProfileAgentConfiguration:
    """Tests for ProfileAgent initialization with configuration"""

    def test_profile_agent_initialization(self):
        """Test ProfileAgent initializes with configuration"""
        from agents.profile_agent import ProfileAgent

        with patch.dict(
            os.environ,
            {
                "SEARCH_API": "tavily",
            },
            clear=False,
        ):
            agent = ProfileAgent()

        assert agent.config is not None
        assert agent.config.search_api == "tavily"
        assert agent.graph is not None

    def test_profile_agent_name_and_aliases(self):
        """Test ProfileAgent has correct name and aliases"""
        from agents.profile_agent import ProfileAgent

        assert ProfileAgent.name == "profile"
        assert "-profile" in ProfileAgent.aliases

    def test_profile_agent_description(self):
        """Test ProfileAgent has description"""
        from agents.profile_agent import ProfileAgent

        assert len(ProfileAgent.description) > 0
        assert "profile" in ProfileAgent.description.lower()
