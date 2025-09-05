import os
import sys

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from handlers.message_handlers import (
    DEFAULT_SYSTEM_MESSAGE,
    get_user_system_prompt,
    handle_message,
)


class TestMessageHandlers:
    """Tests for message handler functions"""

    def test_default_system_message_exists(self):
        """Test that DEFAULT_SYSTEM_MESSAGE is defined"""
        assert DEFAULT_SYSTEM_MESSAGE is not None
        assert isinstance(DEFAULT_SYSTEM_MESSAGE, str)
        assert len(DEFAULT_SYSTEM_MESSAGE) > 0
        assert "helpful assistant" in DEFAULT_SYSTEM_MESSAGE

    def test_get_user_system_prompt(self):
        """Test get_user_system_prompt function"""
        prompt = get_user_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_handle_message_function_exists(self):
        """Test that handle_message function exists and is callable"""
        assert callable(handle_message)
        assert handle_message.__name__ == "handle_message"
