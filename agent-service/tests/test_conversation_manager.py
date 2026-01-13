"""Comprehensive tests for ConversationManager service.

Tests cover:
- Initialization with configuration parameters
- Should summarize logic (message count and token thresholds)
- Token estimation utilities
- Context management with summarization
- Incremental summarization with existing summaries
- System message building with summaries
- Message formatting for summarization
- Managed history retrieval
- Error handling and fallback behaviors
- Edge cases and boundary conditions
"""

import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.conversation_manager import (
    ConversationManager,
    estimate_message_tokens,
    should_trigger_summarization,
)


class TestConversationManagerInitialization:
    """Test ConversationManager initialization."""

    def test_default_initialization(self):
        """Test initialization with default parameters."""
        # Arrange
        mock_llm = AsyncMock()

        # Act
        manager = ConversationManager(mock_llm)

        # Assert
        assert manager.llm_provider == mock_llm
        assert manager.max_messages == 20
        assert manager.keep_recent == 4
        assert manager.summarize_threshold == 0.75
        assert manager.model_context_window == 128000
        assert manager.max_context_tokens == int(128000 * 0.75)

    def test_custom_initialization(self):
        """Test initialization with custom parameters."""
        # Arrange
        mock_llm = AsyncMock()

        # Act
        manager = ConversationManager(
            llm_provider=mock_llm,
            max_messages=30,
            keep_recent=6,
            summarize_threshold=0.8,
            model_context_window=100000,
        )

        # Assert
        assert manager.max_messages == 30
        assert manager.keep_recent == 6
        assert manager.summarize_threshold == 0.8
        assert manager.model_context_window == 100000
        assert manager.max_context_tokens == int(100000 * 0.8)

    def test_max_context_tokens_calculation(self):
        """Test max_context_tokens is calculated correctly."""
        # Arrange
        mock_llm = AsyncMock()

        # Act
        manager = ConversationManager(
            mock_llm, model_context_window=200000, summarize_threshold=0.6
        )

        # Assert
        expected_max_tokens = int(200000 * 0.6)
        assert manager.max_context_tokens == expected_max_tokens


class TestEstimateTokens:
    """Test token estimation method."""

    def test_estimate_tokens_empty_messages(self):
        """Test token estimation with empty message list."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        messages = []

        # Act
        tokens = manager.estimate_tokens(messages)

        # Assert
        assert tokens == 0

    def test_estimate_tokens_single_message(self):
        """Test token estimation with single message."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        messages = [{"role": "user", "content": "Hello there!"}]  # 12 chars

        # Act
        tokens = manager.estimate_tokens(messages)

        # Assert
        assert tokens == 3  # 12 chars / 4 = 3 tokens

    def test_estimate_tokens_multiple_messages(self):
        """Test token estimation with multiple messages."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        messages = [
            {"role": "user", "content": "Hello"},  # 5 chars
            {"role": "assistant", "content": "Hi there"},  # 8 chars
            {"role": "user", "content": "How are you?"},  # 12 chars
        ]

        # Act
        tokens = manager.estimate_tokens(messages)

        # Assert
        # Total: 25 chars / 4 = 6 tokens
        assert tokens == 6

    def test_estimate_tokens_long_content(self):
        """Test token estimation with long content."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        long_content = "a" * 4000  # 4000 chars
        messages = [{"role": "user", "content": long_content}]

        # Act
        tokens = manager.estimate_tokens(messages)

        # Assert
        assert tokens == 1000  # 4000 / 4 = 1000 tokens

    def test_estimate_tokens_missing_content(self):
        """Test token estimation with missing content field."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        messages = [{"role": "user"}, {"role": "assistant", "content": "Hi"}]

        # Act
        tokens = manager.estimate_tokens(messages)

        # Assert
        assert tokens == 0  # Missing content treated as 0 chars

    def test_estimate_tokens_empty_content(self):
        """Test token estimation with empty content."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        messages = [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": ""},
        ]

        # Act
        tokens = manager.estimate_tokens(messages)

        # Assert
        assert tokens == 0


class TestShouldSummarize:
    """Test should_summarize decision logic."""

    def test_should_not_summarize_few_messages(self):
        """Test no summarization with few messages."""
        # Arrange
        manager = ConversationManager(AsyncMock(), max_messages=20)
        messages = [{"role": "user", "content": "Hi"}] * 10

        # Act
        result = manager.should_summarize(messages)

        # Assert
        assert result is False

    def test_should_summarize_exceeds_message_count(self):
        """Test summarization triggered by message count."""
        # Arrange
        manager = ConversationManager(AsyncMock(), max_messages=20)
        messages = [{"role": "user", "content": "Hi"}] * 25

        # Act
        result = manager.should_summarize(messages)

        # Assert
        assert result is True

    def test_should_summarize_exactly_at_threshold(self):
        """Test no summarization at exact message threshold."""
        # Arrange
        manager = ConversationManager(AsyncMock(), max_messages=20)
        messages = [{"role": "user", "content": "Hi"}] * 20

        # Act
        result = manager.should_summarize(messages)

        # Assert
        assert result is False  # Only triggers ABOVE max_messages

    def test_should_summarize_exceeds_token_threshold(self):
        """Test summarization triggered by token count."""
        # Arrange
        manager = ConversationManager(
            AsyncMock(), max_messages=100, model_context_window=1000, summarize_threshold=0.5
        )
        # Create messages that exceed 500 tokens (50% of 1000)
        long_content = "a" * 2500  # 2500 chars = ~625 tokens
        messages = [{"role": "user", "content": long_content}]

        # Act
        result = manager.should_summarize(messages)

        # Assert
        assert result is True

    def test_should_summarize_includes_system_message_tokens(self):
        """Test that system message tokens are included in calculation."""
        # Arrange
        manager = ConversationManager(
            AsyncMock(), max_messages=100, model_context_window=1000, summarize_threshold=0.5
        )
        messages = [{"role": "user", "content": "a" * 1000}]  # 250 tokens
        system_message = "b" * 1200  # 300 tokens
        # Total: 550 tokens > 500 threshold

        # Act
        result = manager.should_summarize(messages, system_message=system_message)

        # Assert
        assert result is True

    def test_should_summarize_includes_existing_summary_tokens(self):
        """Test that existing summary tokens are included."""
        # Arrange
        manager = ConversationManager(
            AsyncMock(), max_messages=100, model_context_window=1000, summarize_threshold=0.5
        )
        messages = [{"role": "user", "content": "a" * 800}]  # 200 tokens
        existing_summary = "c" * 1400  # 350 tokens
        # Total: 550 tokens > 500 threshold

        # Act
        result = manager.should_summarize(
            messages, existing_summary=existing_summary
        )

        # Assert
        assert result is True

    def test_should_summarize_all_factors_combined(self):
        """Test summarization with all token sources."""
        # Arrange
        manager = ConversationManager(
            AsyncMock(), max_messages=100, model_context_window=1000, summarize_threshold=0.5
        )
        messages = [{"role": "user", "content": "a" * 600}]  # 150 tokens
        system_message = "b" * 800  # 200 tokens
        existing_summary = "c" * 800  # 200 tokens
        # Total: 550 tokens > 500 threshold

        # Act
        result = manager.should_summarize(
            messages, system_message=system_message, existing_summary=existing_summary
        )

        # Assert
        assert result is True

    def test_should_not_summarize_below_token_threshold(self):
        """Test no summarization when below token threshold."""
        # Arrange
        manager = ConversationManager(
            AsyncMock(), max_messages=100, model_context_window=10000, summarize_threshold=0.75
        )
        messages = [{"role": "user", "content": "Short message"}]

        # Act
        result = manager.should_summarize(messages)

        # Assert
        assert result is False


class TestManageContext:
    """Test manage_context method."""

    @pytest.mark.asyncio
    async def test_manage_context_no_summarization_needed(self):
        """Test context management without summarization."""
        # Arrange
        mock_llm = AsyncMock()
        manager = ConversationManager(mock_llm, max_messages=20)
        messages = [{"role": "user", "content": "Hi"}] * 5
        system_message = "You are helpful"

        # Act
        updated_system, managed_messages = await manager.manage_context(
            messages, system_message=system_message
        )

        # Assert
        assert updated_system == system_message
        assert managed_messages == messages
        mock_llm.get_response.assert_not_called()

    @pytest.mark.asyncio
    async def test_manage_context_triggers_summarization(self):
        """Test context management with summarization."""
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.get_response = AsyncMock(return_value="This is a summary")
        manager = ConversationManager(mock_llm, max_messages=10, keep_recent=3)
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(15)]
        system_message = "You are helpful"

        # Act
        updated_system, managed_messages = await manager.manage_context(
            messages, system_message=system_message
        )

        # Assert
        assert len(managed_messages) == 3  # Only recent messages
        assert "Previous Conversation Summary" in updated_system
        assert "This is a summary" in updated_system
        mock_llm.get_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_manage_context_with_existing_summary(self):
        """Test context management with existing summary."""
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.get_response = AsyncMock(return_value="Updated summary")
        manager = ConversationManager(mock_llm, max_messages=10, keep_recent=3)
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(15)]
        existing_summary = "Old summary"

        # Act
        updated_system, managed_messages = await manager.manage_context(
            messages, existing_summary=existing_summary
        )

        # Assert
        assert len(managed_messages) == 3
        assert "Updated summary" in updated_system
        # Check that incremental summarization was used
        call_args = mock_llm.get_response.call_args
        assert "Previous Summary" in str(call_args)

    @pytest.mark.asyncio
    async def test_manage_context_handles_summarization_error(self):
        """Test context management with summarization error fallback."""
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.get_response = AsyncMock(side_effect=Exception("API error"))
        manager = ConversationManager(mock_llm, max_messages=10, keep_recent=3)
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(15)]
        system_message = "You are helpful"

        # Act
        updated_system, managed_messages = await manager.manage_context(
            messages, system_message=system_message
        )

        # Assert
        # Should fallback to sliding window
        assert updated_system == system_message
        assert len(managed_messages) == 10  # max_messages
        assert managed_messages == messages[-10:]

    @pytest.mark.asyncio
    async def test_manage_context_no_system_message(self):
        """Test context management without system message."""
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.get_response = AsyncMock(return_value="Summary text")
        manager = ConversationManager(mock_llm, max_messages=10, keep_recent=3)
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(15)]

        # Act
        updated_system, managed_messages = await manager.manage_context(messages)

        # Assert
        assert "Previous Conversation Summary" in updated_system
        assert "Summary text" in updated_system
        assert len(managed_messages) == 3

    @pytest.mark.asyncio
    async def test_manage_context_keeps_correct_recent_messages(self):
        """Test that correct recent messages are kept."""
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.get_response = AsyncMock(return_value="Summary")
        manager = ConversationManager(mock_llm, max_messages=10, keep_recent=4)
        messages = [{"role": "user", "content": f"Msg {i}"} for i in range(20)]

        # Act
        _, managed_messages = await manager.manage_context(messages)

        # Assert
        assert len(managed_messages) == 4
        # Should be last 4 messages
        assert managed_messages[0]["content"] == "Msg 16"
        assert managed_messages[1]["content"] == "Msg 17"
        assert managed_messages[2]["content"] == "Msg 18"
        assert managed_messages[3]["content"] == "Msg 19"


class TestSummarizeMessages:
    """Test _summarize_messages method."""

    @pytest.mark.asyncio
    async def test_summarize_empty_messages(self):
        """Test summarization with empty message list."""
        # Arrange
        mock_llm = AsyncMock()
        manager = ConversationManager(mock_llm)
        messages = []

        # Act
        summary = await manager._summarize_messages(messages)

        # Assert
        assert summary == ""
        mock_llm.get_response.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarize_empty_with_existing_summary(self):
        """Test summarization with empty messages but existing summary."""
        # Arrange
        mock_llm = AsyncMock()
        manager = ConversationManager(mock_llm)
        messages = []
        existing_summary = "Previous summary"

        # Act
        summary = await manager._summarize_messages(messages, existing_summary)

        # Assert
        assert summary == "Previous summary"
        mock_llm.get_response.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarize_first_time(self):
        """Test first-time summarization."""
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.get_response = AsyncMock(return_value="Generated summary")
        manager = ConversationManager(mock_llm)
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

        # Act
        summary = await manager._summarize_messages(messages)

        # Assert
        assert summary == "Generated summary"
        call_args = mock_llm.get_response.call_args
        assert "Conversation to Summarize" in str(call_args)
        assert "Previous Summary" not in str(call_args)

    @pytest.mark.asyncio
    async def test_summarize_incremental(self):
        """Test incremental summarization with existing summary."""
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.get_response = AsyncMock(return_value="Updated summary")
        manager = ConversationManager(mock_llm)
        messages = [{"role": "user", "content": "New message"}]
        existing_summary = "Old summary"

        # Act
        summary = await manager._summarize_messages(messages, existing_summary)

        # Assert
        assert summary == "Updated summary"
        call_args = mock_llm.get_response.call_args
        assert "Previous Summary" in str(call_args)
        assert "Old summary" in str(call_args)

    @pytest.mark.asyncio
    async def test_summarize_handles_dict_response(self):
        """Test summarization handles dict response from LLM."""
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.get_response = AsyncMock(
            return_value={"content": "Summary from dict"}
        )
        manager = ConversationManager(mock_llm)
        messages = [{"role": "user", "content": "Test"}]

        # Act
        summary = await manager._summarize_messages(messages)

        # Assert
        assert summary == "Summary from dict"

    @pytest.mark.asyncio
    async def test_summarize_handles_empty_response(self):
        """Test summarization handles empty LLM response."""
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.get_response = AsyncMock(return_value="")
        manager = ConversationManager(mock_llm)
        messages = [{"role": "user", "content": "Test"}]
        existing_summary = "Fallback summary"

        # Act
        summary = await manager._summarize_messages(messages, existing_summary)

        # Assert
        assert summary == "Fallback summary"

    @pytest.mark.asyncio
    async def test_summarize_handles_none_response(self):
        """Test summarization handles None LLM response."""
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.get_response = AsyncMock(return_value=None)
        manager = ConversationManager(mock_llm)
        messages = [{"role": "user", "content": "Test"}]

        # Act
        summary = await manager._summarize_messages(messages)

        # Assert
        assert summary == ""

    @pytest.mark.asyncio
    async def test_summarize_uses_correct_system_message(self):
        """Test that summarization uses correct system message."""
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.get_response = AsyncMock(return_value="Summary")
        manager = ConversationManager(mock_llm)
        messages = [{"role": "user", "content": "Test"}]

        # Act
        await manager._summarize_messages(messages)

        # Assert
        call_args = mock_llm.get_response.call_args
        assert call_args[1]["system_message"] == "You are a conversation summarization assistant. Create clear, concise summaries that preserve important context."
        assert call_args[1]["max_tokens"] == 4000


class TestFormatMessagesForSummary:
    """Test _format_messages_for_summary method."""

    def test_format_empty_messages(self):
        """Test formatting empty message list."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        messages = []

        # Act
        formatted = manager._format_messages_for_summary(messages)

        # Assert
        assert formatted == ""

    def test_format_user_message(self):
        """Test formatting user message."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        messages = [{"role": "user", "content": "Hello there"}]

        # Act
        formatted = manager._format_messages_for_summary(messages)

        # Assert
        assert formatted == "User: Hello there"

    def test_format_assistant_message(self):
        """Test formatting assistant message."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        messages = [{"role": "assistant", "content": "Hi back"}]

        # Act
        formatted = manager._format_messages_for_summary(messages)

        # Assert
        assert formatted == "Assistant: Hi back"

    def test_format_system_message_skipped(self):
        """Test that system messages are skipped."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
        ]

        # Act
        formatted = manager._format_messages_for_summary(messages)

        # Assert
        assert "system" not in formatted.lower()
        assert formatted == "User: Hello"

    def test_format_multiple_messages(self):
        """Test formatting multiple messages."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "How are you?"},
        ]

        # Act
        formatted = manager._format_messages_for_summary(messages)

        # Assert
        assert "User: Hello" in formatted
        assert "Assistant: Hi" in formatted
        assert "User: How are you?" in formatted
        assert formatted.count("\n\n") == 2  # Messages separated by double newline

    def test_format_missing_role(self):
        """Test formatting with missing role field."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        messages = [{"content": "Message without role"}]

        # Act
        formatted = manager._format_messages_for_summary(messages)

        # Assert
        # Should handle gracefully (unknown role not included in output)
        assert formatted == ""

    def test_format_missing_content(self):
        """Test formatting with missing content field."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        messages = [{"role": "user"}]

        # Act
        formatted = manager._format_messages_for_summary(messages)

        # Assert
        assert formatted == "User: "


class TestBuildSystemWithSummary:
    """Test _build_system_with_summary method."""

    def test_build_with_base_and_summary(self):
        """Test building system message with both base and summary."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        base_system = "You are a helpful assistant."
        summary = "Previous conversation summary here."

        # Act
        result = manager._build_system_with_summary(base_system, summary)

        # Assert
        assert "You are a helpful assistant." in result
        assert "Previous Conversation Summary" in result
        assert "Previous conversation summary here." in result
        assert "---" in result

    def test_build_with_none_base(self):
        """Test building with None base system message."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        summary = "Summary text"

        # Act
        result = manager._build_system_with_summary(None, summary)

        # Assert
        assert "Previous Conversation Summary" in result
        assert "Summary text" in result

    def test_build_with_empty_base(self):
        """Test building with empty base system message."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        summary = "Summary text"

        # Act
        result = manager._build_system_with_summary("", summary)

        # Assert
        assert "Previous Conversation Summary" in result
        assert "Summary text" in result

    def test_build_without_summary(self):
        """Test building without summary returns base."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        base_system = "You are helpful."

        # Act
        result = manager._build_system_with_summary(base_system, "")

        # Assert
        assert result == base_system

    def test_build_with_none_summary(self):
        """Test building with None summary returns base."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        base_system = "You are helpful."

        # Act
        result = manager._build_system_with_summary(base_system, None)

        # Assert
        assert result == base_system

    def test_build_includes_continuation_instruction(self):
        """Test that result includes continuation instruction."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        base_system = "Base"
        summary = "Summary"

        # Act
        result = manager._build_system_with_summary(base_system, summary)

        # Assert
        assert "Continue naturally based on both the summary and the recent messages" in result


class TestGetManagedHistory:
    """Test get_managed_history method."""

    def test_get_managed_history_within_limit(self):
        """Test getting history within max_messages limit."""
        # Arrange
        manager = ConversationManager(AsyncMock(), max_messages=10)
        messages = [{"role": "user", "content": f"Msg {i}"} for i in range(5)]

        # Act
        result = manager.get_managed_history(messages)

        # Assert
        assert len(result) == 5
        assert result == messages

    def test_get_managed_history_exceeds_limit(self):
        """Test getting history exceeding max_messages."""
        # Arrange
        manager = ConversationManager(AsyncMock(), max_messages=10)
        messages = [{"role": "user", "content": f"Msg {i}"} for i in range(20)]

        # Act
        result = manager.get_managed_history(messages)

        # Assert
        assert len(result) == 10
        # Should return last 10 messages
        assert result[0]["content"] == "Msg 10"
        assert result[-1]["content"] == "Msg 19"

    def test_get_managed_history_with_summary_ignored(self):
        """Test that summary parameter doesn't affect result."""
        # Arrange
        manager = ConversationManager(AsyncMock(), max_messages=5)
        messages = [{"role": "user", "content": f"Msg {i}"} for i in range(10)]
        summary = "Some summary"

        # Act
        result = manager.get_managed_history(messages, summary=summary)

        # Assert
        assert len(result) == 5
        assert result == messages[-5:]

    def test_get_managed_history_empty_messages(self):
        """Test getting history with empty messages."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        messages = []

        # Act
        result = manager.get_managed_history(messages)

        # Assert
        assert result == []


class TestUtilityFunctions:
    """Test module-level utility functions."""

    def test_estimate_message_tokens_empty(self):
        """Test token estimation utility with empty messages."""
        # Arrange
        messages = []

        # Act
        tokens = estimate_message_tokens(messages)

        # Assert
        assert tokens == 0

    def test_estimate_message_tokens_single(self):
        """Test token estimation utility with single message."""
        # Arrange
        messages = [{"role": "user", "content": "Test message"}]  # 12 chars

        # Act
        tokens = estimate_message_tokens(messages)

        # Assert
        assert tokens == 3  # 12 / 4 = 3

    def test_estimate_message_tokens_multiple(self):
        """Test token estimation utility with multiple messages."""
        # Arrange
        messages = [
            {"role": "user", "content": "Hello"},  # 5 chars
            {"role": "assistant", "content": "Hi there!"},  # 9 chars
        ]

        # Act
        tokens = estimate_message_tokens(messages)

        # Assert
        assert tokens == 3  # 14 / 4 = 3

    def test_should_trigger_summarization_below_threshold(self):
        """Test summarization trigger utility below threshold."""
        # Arrange
        messages = [{"role": "user", "content": "Hi"}] * 10

        # Act
        result = should_trigger_summarization(messages, max_messages=20)

        # Assert
        assert result is False

    def test_should_trigger_summarization_above_threshold(self):
        """Test summarization trigger utility above threshold."""
        # Arrange
        messages = [{"role": "user", "content": "Hi"}] * 25

        # Act
        result = should_trigger_summarization(messages, max_messages=20)

        # Assert
        assert result is True

    def test_should_trigger_summarization_at_threshold(self):
        """Test summarization trigger utility at exact threshold."""
        # Arrange
        messages = [{"role": "user", "content": "Hi"}] * 20

        # Act
        result = should_trigger_summarization(messages, max_messages=20)

        # Assert
        assert result is False

    def test_should_trigger_summarization_default_max(self):
        """Test summarization trigger utility with default max."""
        # Arrange
        messages = [{"role": "user", "content": "Hi"}] * 21

        # Act
        result = should_trigger_summarization(messages)

        # Assert
        assert result is True  # Default max_messages is 20


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_manage_context_with_one_message(self):
        """Test context management with single message."""
        # Arrange
        mock_llm = AsyncMock()
        manager = ConversationManager(mock_llm, max_messages=20)
        messages = [{"role": "user", "content": "Hello"}]

        # Act
        _, managed = await manager.manage_context(messages)

        # Assert
        assert len(managed) == 1
        assert managed == messages

    @pytest.mark.asyncio
    async def test_manage_context_keep_recent_equals_message_count(self):
        """Test when keep_recent equals total message count."""
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.get_response = AsyncMock(return_value="Summary")
        manager = ConversationManager(mock_llm, max_messages=5, keep_recent=10)
        messages = [{"role": "user", "content": f"Msg {i}"} for i in range(10)]

        # Act
        _, managed = await manager.manage_context(messages)

        # Assert
        # Should keep all 10 recent messages since keep_recent=10
        assert len(managed) == 10

    @pytest.mark.asyncio
    async def test_manage_context_keep_recent_greater_than_message_count(self):
        """Test when keep_recent > message count after split."""
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.get_response = AsyncMock(return_value="Summary")
        manager = ConversationManager(mock_llm, max_messages=5, keep_recent=20)
        messages = [{"role": "user", "content": f"Msg {i}"} for i in range(10)]

        # Act
        _, managed = await manager.manage_context(messages)

        # Assert
        # Should keep all 10 messages (all are "recent")
        assert len(managed) == 10

    def test_estimate_tokens_very_large_message(self):
        """Test token estimation with very large message."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        huge_content = "x" * 1_000_000  # 1 million chars
        messages = [{"role": "user", "content": huge_content}]

        # Act
        tokens = manager.estimate_tokens(messages)

        # Assert
        assert tokens == 250_000  # 1M / 4 = 250k tokens

    @pytest.mark.asyncio
    async def test_summarize_messages_with_dict_missing_content(self):
        """Test summarization with dict response missing content."""
        # Arrange
        mock_llm = AsyncMock()
        mock_llm.get_response = AsyncMock(return_value={"error": "No content"})
        manager = ConversationManager(mock_llm)
        messages = [{"role": "user", "content": "Test"}]
        existing = "Existing summary"

        # Act
        summary = await manager._summarize_messages(messages, existing)

        # Assert
        assert summary == "Existing summary"  # Fallback to existing

    def test_build_system_with_summary_special_characters(self):
        """Test building system message with special characters."""
        # Arrange
        manager = ConversationManager(AsyncMock())
        base = "Base with 'quotes' and \"double quotes\""
        summary = "Summary with\nnewlines\tand\ttabs"

        # Act
        result = manager._build_system_with_summary(base, summary)

        # Assert
        assert base in result
        assert summary in result

    @pytest.mark.asyncio
    async def test_manage_context_all_system_messages(self):
        """Test context management with only system messages."""
        # Arrange
        mock_llm = AsyncMock()
        manager = ConversationManager(mock_llm, max_messages=20)
        messages = [{"role": "system", "content": "System msg"}] * 25

        # Act with patch to avoid logger issues
        with patch("services.conversation_manager.logger"):
            _, managed = await manager.manage_context(messages)

        # Assert - should still process even if all system messages
        assert len(managed) <= 20 or len(managed) == manager.keep_recent
