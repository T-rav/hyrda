"""
EnvironmentVariableFactory for test utilities
"""


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
