import os
import sys
from unittest.mock import patch

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import AgentSettings, LLMSettings, Settings, SlackSettings


# TDD Factory Patterns for Configuration Testing
class EnvironmentVariableFactory:
    """Factory for creating environment variable configurations"""

    @staticmethod
    def create_slack_env_vars(
        bot_token: str = "xoxb-test-token",
        app_token: str = "xapp-test-token",
        bot_id: str = "B12345678",
    ) -> dict[str, str]:
        """Create Slack environment variables"""
        return {
            "SLACK_BOT_TOKEN": bot_token,
            "SLACK_APP_TOKEN": app_token,
            "SLACK_BOT_ID": bot_id,
        }

    @staticmethod
    def create_llm_env_vars(
        provider: str = "openai",
        api_key: str = "test-api-key",
        model: str = "test-model",
        base_url: str = "http://test-api.com",
    ) -> dict[str, str]:
        """Create LLM environment variables"""
        return {
            "LLM_PROVIDER": provider,
            "LLM_API_KEY": api_key,
            "LLM_MODEL": model,
            "LLM_BASE_URL": base_url,
        }

    @staticmethod
    def create_complete_env_vars(
        slack_token: str = "xoxb-test-token",
        slack_app_token: str = "xapp-test-token",
        llm_api_url: str = "http://test-api.com",
        llm_api_key: str = "test-api-key",
        database_url: str = "postgresql://test:test@localhost:5432/test_db",
    ) -> dict[str, str]:
        """Create complete environment variables for Settings"""
        return {
            "SLACK_BOT_TOKEN": slack_token,
            "SLACK_APP_TOKEN": slack_app_token,
            "LLM_API_URL": llm_api_url,
            "LLM_API_KEY": llm_api_key,
            "DATABASE_URL": database_url,
        }

    @staticmethod
    def create_anthropic_env_vars() -> dict[str, str]:
        """Create Anthropic-specific environment variables"""
        return EnvironmentVariableFactory.create_llm_env_vars(
            provider="anthropic",
            api_key="sk-ant-test-key",
            model="claude-3-haiku-20240307",
            base_url="https://api.anthropic.com",
        )

    @staticmethod
    def create_ollama_env_vars() -> dict[str, str]:
        """Create Ollama-specific environment variables"""
        return EnvironmentVariableFactory.create_llm_env_vars(
            provider="ollama",
            api_key="",
            model="llama2",
            base_url="http://localhost:11434",
        )


class ConfigurationFactory:
    """Factory for creating configuration objects"""

    @staticmethod
    def create_slack_settings(
        bot_token: str = "xoxb-test-token",
        app_token: str = "xapp-test-token",
        bot_id: str = "B12345678",
    ) -> SlackSettings:
        """Create SlackSettings with environment variables"""
        env_vars = EnvironmentVariableFactory.create_slack_env_vars(
            bot_token=bot_token, app_token=app_token, bot_id=bot_id
        )
        with patch.dict(os.environ, env_vars):
            return SlackSettings()

    @staticmethod
    def create_llm_settings(
        provider: str = "openai",
        api_key: str = "test-api-key",
        model: str = "test-model",
        base_url: str = "http://test-api.com",
    ) -> LLMSettings:
        """Create LLMSettings with environment variables"""
        env_vars = EnvironmentVariableFactory.create_llm_env_vars(
            provider=provider, api_key=api_key, model=model, base_url=base_url
        )
        with patch.dict(os.environ, env_vars):
            return LLMSettings()

    @staticmethod
    def create_complete_settings() -> Settings:
        """Create complete Settings with all required environment variables"""
        env_vars = EnvironmentVariableFactory.create_complete_env_vars()
        with patch.dict(os.environ, env_vars):
            return Settings()

    @staticmethod
    def create_anthropic_settings() -> LLMSettings:
        """Create Anthropic LLMSettings"""
        env_vars = EnvironmentVariableFactory.create_anthropic_env_vars()
        with patch.dict(os.environ, env_vars):
            return LLMSettings()

    @staticmethod
    def create_ollama_settings() -> LLMSettings:
        """Create Ollama LLMSettings"""
        env_vars = EnvironmentVariableFactory.create_ollama_env_vars()
        with patch.dict(os.environ, env_vars):
            return LLMSettings()


class TestConfig:
    """Tests for the configuration system using factory patterns"""

    def test_slack_settings_default(self):
        """Test SlackSettings configuration with default values"""
        settings = ConfigurationFactory.create_slack_settings()

        assert settings.bot_token == "xoxb-test-token"
        assert settings.app_token == "xapp-test-token"
        assert settings.bot_id == "B12345678"

    def test_slack_settings_custom(self):
        """Test SlackSettings configuration with custom values"""
        custom_bot_token = "xoxb-custom-token"
        custom_app_token = "xapp-custom-token"
        custom_bot_id = "B87654321"

        settings = ConfigurationFactory.create_slack_settings(
            bot_token=custom_bot_token,
            app_token=custom_app_token,
            bot_id=custom_bot_id,
        )

        assert settings.bot_token == custom_bot_token
        assert settings.app_token == custom_app_token
        assert settings.bot_id == custom_bot_id

    def test_llm_settings_openai(self):
        """Test LLMSettings configuration for OpenAI"""
        settings = ConfigurationFactory.create_llm_settings()

        assert settings.provider == "openai"
        assert settings.api_key.get_secret_value() == "test-api-key"
        assert settings.model == "test-model"
        assert settings.base_url == "http://test-api.com"

    def test_llm_settings_anthropic(self):
        """Test LLMSettings configuration for Anthropic"""
        settings = ConfigurationFactory.create_anthropic_settings()

        assert settings.provider == "anthropic"
        assert settings.api_key.get_secret_value() == "sk-ant-test-key"
        assert settings.model == "claude-3-haiku-20240307"
        assert settings.base_url == "https://api.anthropic.com"

    def test_llm_settings_ollama(self):
        """Test LLMSettings configuration for Ollama"""
        settings = ConfigurationFactory.create_ollama_settings()

        assert settings.provider == "ollama"
        assert settings.api_key.get_secret_value() == ""
        assert settings.model == "llama2"
        assert settings.base_url == "http://localhost:11434"

    def test_llm_settings_custom(self):
        """Test LLMSettings configuration with custom values"""
        custom_provider = "custom"
        custom_api_key = "custom-key"
        custom_model = "custom-model"
        custom_base_url = "http://custom-api.com"

        settings = ConfigurationFactory.create_llm_settings(
            provider=custom_provider,
            api_key=custom_api_key,
            model=custom_model,
            base_url=custom_base_url,
        )

        assert settings.provider == custom_provider
        assert settings.api_key.get_secret_value() == custom_api_key
        assert settings.model == custom_model
        assert settings.base_url == custom_base_url

    def test_settings_defaults(self):
        """Test Settings default values and structure"""
        settings = ConfigurationFactory.create_complete_settings()

        # Check attribute types
        assert isinstance(settings.slack, SlackSettings)
        assert isinstance(settings.llm, LLMSettings)
        assert isinstance(settings.agent, AgentSettings)
        assert isinstance(settings.debug, bool)
        assert isinstance(settings.log_level, str)

        # Check default values for basic properties
        assert settings.debug is False
        # Log level might be set by test environment, so check it exists
        assert hasattr(settings, "log_level") and isinstance(settings.log_level, str)

    def test_environment_variable_factory_slack(self):
        """Test EnvironmentVariableFactory for Slack configuration"""
        env_vars = EnvironmentVariableFactory.create_slack_env_vars(
            bot_token="custom-bot", app_token="custom-app", bot_id="CUSTOM123"
        )

        assert env_vars["SLACK_BOT_TOKEN"] == "custom-bot"
        assert env_vars["SLACK_APP_TOKEN"] == "custom-app"
        assert env_vars["SLACK_BOT_ID"] == "CUSTOM123"

    def test_environment_variable_factory_llm(self):
        """Test EnvironmentVariableFactory for LLM configuration"""
        env_vars = EnvironmentVariableFactory.create_llm_env_vars(
            provider="custom",
            api_key="key123",
            model="model456",
            base_url="http://test.com",
        )

        assert env_vars["LLM_PROVIDER"] == "custom"
        assert env_vars["LLM_API_KEY"] == "key123"
        assert env_vars["LLM_MODEL"] == "model456"
        assert env_vars["LLM_BASE_URL"] == "http://test.com"
