"""
MessageBuilder for test utilities
"""

from typing import Any


class MessageBuilder:
    """Builder for creating message objects with fluent API"""

    def __init__(self):
        self._role = "user"
        self._content = "Test message"
        self._name = None
        self._function_call = None

    def as_user(self):
        """Set role as user"""
        self._role = "user"
        return self

    def as_assistant(self):
        """Set role as assistant"""
        self._role = "assistant"
        return self

    def as_system(self):
        """Set role as system"""
        self._role = "system"
        return self

    def with_content(self, content: str):
        """Set message content"""
        self._content = content
        return self

    def with_name(self, name: str):
        """Set message name"""
        self._name = name
        return self

    def with_function_call(self, function_call: dict[str, Any]):
        """Set function call"""
        self._function_call = function_call
        return self

    def build(self) -> dict[str, Any]:
        """Build the message"""
        message = {
            "role": self._role,
            "content": self._content,
        }
        if self._name:
            message["name"] = self._name
        if self._function_call:
            message["function_call"] = self._function_call
        return message
