"""
SlackSettingsFactory for test utilities
"""

import os
from unittest.mock import patch

from config.settings import (
    SlackSettings,
)


class SlackSettingsFactory:
    """Factory for creating Slack settings"""

    @staticmethod
    def create_basic_settings(
        bot_token: str = "xoxb-test-token",
        app_token: str = "xapp-test-token",
        bot_id: str = "B12345678",
    ) -> SlackSettings:
        """Create SlackSettings with environment variables"""
        from .environment_variable_factory import EnvironmentVariableFactory

        env_vars = EnvironmentVariableFactory.create_slack_env_vars(
            bot_token=bot_token, app_token=app_token, bot_id=bot_id
        )
        with patch.dict(os.environ, env_vars):
            return SlackSettings()
