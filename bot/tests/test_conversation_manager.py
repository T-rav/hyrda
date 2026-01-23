"""Tests for services/conversation_manager.py"""

from unittest.mock import AsyncMock, Mock

import pytest

from services.conversation_manager import ConversationManager


@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider for testing."""
    mock = Mock()
    mock.get_response = AsyncMock(return_value="Summary of conversation")
    return mock


@pytest.fixture
def manager(mock_llm_provider):
    """Create ConversationManager instance."""
    return ConversationManager(
        llm_provider=mock_llm_provider,
        max_messages=20,
        keep_recent=4,
        summarize_threshold=0.75,
        model_context_window=128000,
    )


class TestConversationManager:
    """Tests for ConversationManager."""

    def test_init(self, mock_llm_provider):
        """Test ConversationManager initialization."""
        manager = ConversationManager(
            llm_provider=mock_llm_provider,
            max_messages=10,
            keep_recent=3,
            summarize_threshold=0.8,
            model_context_window=100000,
        )

        assert manager.llm_provider == mock_llm_provider
        assert manager.max_messages == 10
        assert manager.keep_recent == 3
        assert manager.summarize_threshold == 0.8
        assert manager.model_context_window == 100000
        assert manager.max_context_tokens == int(100000 * 0.8)

    def test_estimate_tokens(self, manager):
        """Test token estimation."""
        messages = [
            {"content": "Hello"},  # 5 chars
            {"content": "This is a test message"},  # 23 chars
            {"content": "x" * 40},  # 40 chars
        ]

        tokens = manager.estimate_tokens(messages)

        # Total: 68 chars / 4 = 17 tokens (but int division gives 16)
        assert tokens == 16

    def test_estimate_tokens_empty_messages(self, manager):
        """Test token estimation with empty messages."""
        tokens = manager.estimate_tokens([])
        assert tokens == 0

    def test_should_summarize_message_count_threshold(self, manager):
        """Test summarization trigger based on message count."""
        # Create more messages than max_messages
        messages = [{"content": f"Message {i}"} for i in range(25)]

        should_summarize = manager.should_summarize(messages)

        # Should trigger because 25 > 20 (max_messages)
        assert should_summarize is True

    def test_should_summarize_not_needed(self, manager):
        """Test that summarization is not triggered for short conversations."""
        messages = [{"content": f"Message {i}"} for i in range(5)]

        should_summarize = manager.should_summarize(messages)

        assert should_summarize is False

    def test_should_summarize_token_threshold(self, manager):
        """Test summarization trigger based on token count."""
        # Create messages that exceed token threshold
        # max_context_tokens = 128000 * 0.75 = 96000
        # Each message needs ~4 chars per token
        large_content = "x" * 400000  # ~100k tokens
        messages = [{"content": large_content}]

        should_summarize = manager.should_summarize(messages)

        # Should trigger because estimated tokens > max_context_tokens
        assert should_summarize is True

    def test_should_summarize_with_system_message(self, manager):
        """Test summarization considers system message tokens."""
        messages = [{"content": "x" * 300000}]  # ~75k tokens
        system_message = "x" * 100000  # ~25k tokens

        should_summarize = manager.should_summarize(
            messages, system_message=system_message
        )

        # Total ~100k tokens > 96k threshold
        assert should_summarize is True

    def test_should_summarize_with_existing_summary(self, manager):
        """Test summarization considers existing summary tokens."""
        messages = [{"content": "x" * 300000}]  # ~75k tokens
        existing_summary = "x" * 100000  # ~25k tokens

        should_summarize = manager.should_summarize(
            messages, existing_summary=existing_summary
        )

        # Total ~100k tokens > 96k threshold
        assert should_summarize is True

    @pytest.mark.asyncio
    async def test_manage_context_no_summarization_needed(self, manager):
        """Test manage_context when no summarization is needed."""
        messages = [{"content": f"Message {i}"} for i in range(5)]
        system_message = "You are a helpful assistant"

        system_msg, managed_msgs = await manager.manage_context(
            messages, system_message
        )

        # Should return original messages unchanged
        assert system_msg == system_message
        assert managed_msgs == messages
        # LLM should not be called
        manager.llm_provider.get_response.assert_not_called()

    @pytest.mark.asyncio
    async def test_manage_context_triggers_summarization(
        self, manager, mock_llm_provider
    ):
        """Test manage_context triggers summarization."""
        # Create conversation that needs summarization
        messages = [{"content": f"Message {i}"} for i in range(25)]
        system_message = "You are a helpful assistant"

        mock_llm_provider.get_response.return_value = "Summary of old messages"

        system_msg, managed_msgs = await manager.manage_context(
            messages, system_message
        )

        # Should call LLM to generate summary
        mock_llm_provider.get_response.assert_called_once()

        # Should return system message with summary and recent messages
        assert "Summary of old messages" in system_msg
        # Should keep last 4 messages (keep_recent=4)
        assert len(managed_msgs) == 4
        assert managed_msgs == messages[-4:]

    @pytest.mark.asyncio
    async def test_manage_context_with_existing_summary(
        self, manager, mock_llm_provider
    ):
        """Test manage_context updates existing summary."""
        messages = [{"content": f"Message {i}"} for i in range(25)]
        system_message = "You are a helpful assistant"
        existing_summary = "Previous summary"

        mock_llm_provider.get_response.return_value = "Updated summary"

        system_msg, managed_msgs = await manager.manage_context(
            messages, system_message, existing_summary
        )

        # Should generate new summary
        assert "Updated summary" in system_msg
        # Old summary should not be in new system message
        assert system_msg != system_message

    @pytest.mark.asyncio
    async def test_manage_context_handles_summarization_error(
        self, manager, mock_llm_provider
    ):
        """Test manage_context handles errors during summarization."""
        messages = [{"content": f"Message {i}"} for i in range(25)]
        system_message = "You are a helpful assistant"

        # LLM fails to generate summary
        mock_llm_provider.get_response.side_effect = Exception("API error")

        system_msg, managed_msgs = await manager.manage_context(
            messages, system_message
        )

        # Should return original system message on error
        assert system_msg == system_message
        # On error, returns sliding window (max_messages)
        assert len(managed_msgs) == manager.max_messages

    @pytest.mark.asyncio
    async def test_manage_context_no_system_message(self, manager):
        """Test manage_context with no system message."""
        messages = [{"content": f"Message {i}"} for i in range(5)]

        system_msg, managed_msgs = await manager.manage_context(messages, None)

        # Should handle None system message
        assert system_msg is None
        assert managed_msgs == messages

    @pytest.mark.asyncio
    async def test_manage_context_keeps_recent_messages(
        self, manager, mock_llm_provider
    ):
        """Test that manage_context keeps correct number of recent messages."""
        # Create exactly 25 messages
        messages = [{"content": f"Message {i}"} for i in range(25)]

        mock_llm_provider.get_response.return_value = "Summary"

        _, managed_msgs = await manager.manage_context(messages, "System")

        # Should keep last 4 messages (keep_recent=4)
        assert len(managed_msgs) == 4
        assert managed_msgs[0]["content"] == "Message 21"
        assert managed_msgs[-1]["content"] == "Message 24"
