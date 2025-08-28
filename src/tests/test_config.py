import sys
import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.settings import SlackSettings, LLMSettings, Settings, AgentSettings


class TestConfig:
    """Tests for the configuration system"""

    def test_slack_settings(self):
        """Test SlackSettings configuration"""
        # Test with environment variables
        with patch.dict(os.environ, {
            "SLACK_BOT_TOKEN": "xoxb-test-token",
            "SLACK_APP_TOKEN": "xapp-test-token",
            "SLACK_BOT_ID": "B12345678"
        }):
            settings = SlackSettings()
            assert settings.bot_token == "xoxb-test-token"
            assert settings.app_token == "xapp-test-token"
            assert settings.bot_id == "B12345678"

    def test_llm_settings(self):
        """Test LLMSettings configuration"""
        # Test with environment variables
        with patch.dict(os.environ, {
            "LLM_API_URL": "http://test-api.com",
            "LLM_API_KEY": "test-api-key",
            "LLM_MODEL": "test-model"
        }):
            settings = LLMSettings()
            assert settings.api_url == "http://test-api.com"
            assert settings.api_key.get_secret_value() == "test-api-key"
            assert settings.model == "test-model"

    def test_settings_defaults(self):
        """Test Settings default values"""
        # Test default settings
        settings = Settings()
        
        # Check attribute types
        assert isinstance(settings.slack, SlackSettings)
        assert isinstance(settings.llm, LLMSettings)
        assert isinstance(settings.agent, AgentSettings)
        assert isinstance(settings.debug, bool)
        assert isinstance(settings.log_level, str)
        
        # Check default values for basic properties
        assert settings.debug is False
        assert settings.log_level == "INFO" 