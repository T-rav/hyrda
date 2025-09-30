"""
ConversationBuilder for test utilities
"""


class ConversationBuilder:
    """Builder for creating conversation histories"""

    def __init__(self):
        self._messages = []

    def add_user_message(self, content: str):
        """Add user message"""
        self._messages.append({"role": "user", "content": content})
        return self

    def add_assistant_message(self, content: str):
        """Add assistant message"""
        self._messages.append({"role": "assistant", "content": content})
        return self

    def add_system_message(self, content: str):
        """Add system message"""
        self._messages.append({"role": "system", "content": content})
        return self

    def add_message(self, role: str, content: str):
        """Add custom message"""
        self._messages.append({"role": role, "content": content})
        return self

    def add_messages(self, messages: list[dict[str, str]]):
        """Add multiple messages"""
        self._messages.extend(messages)
        return self

    def build(self) -> list[dict[str, str]]:
        """Build the conversation"""
        return self._messages.copy()
