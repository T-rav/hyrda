"""
MessageFactory for test utilities
"""


class MessageFactory:
    """Factory for creating test messages"""

    @staticmethod
    def create_user_message(content: str = "Hello") -> dict[str, str]:
        """Create user message"""
        return {"role": "user", "content": content}

    @staticmethod
    def create_assistant_message(content: str = "Hi there!") -> dict[str, str]:
        """Create assistant message"""
        return {"role": "assistant", "content": content}

    @staticmethod
    def create_system_message(
        content: str = "You are a helpful assistant",
    ) -> dict[str, str]:
        """Create system message"""
        return {"role": "system", "content": content}

    @staticmethod
    def create_conversation(
        user_msg: str = "Hello", assistant_msg: str = "Hi!"
    ) -> list[dict[str, str]]:
        """Create simple conversation"""
        return [
            MessageFactory.create_user_message(user_msg),
            MessageFactory.create_assistant_message(assistant_msg),
        ]

    @staticmethod
    def create_conversation_with_system(
        system_msg: str = "You are helpful",
        user_msg: str = "Hello",
        assistant_msg: str = "Hi!",
    ) -> list[dict[str, str]]:
        """Create conversation with system message"""
        return [
            MessageFactory.create_system_message(system_msg),
            MessageFactory.create_user_message(user_msg),
            MessageFactory.create_assistant_message(assistant_msg),
        ]
