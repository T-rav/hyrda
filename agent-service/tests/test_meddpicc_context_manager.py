"""Comprehensive tests for MeddpiccContextManager service.

Tests cover:
- Initialization with default and custom settings
- Message addition to conversation history
- Compression detection based on message count and token threshold
- History compression with semantic summarization
- Context prompt building for different modes (analysis, followup, qa)
- Complete context management workflow
- Error handling and fallback mechanisms
- Edge cases (empty history, missing summaries, compression failures)
"""

import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.meddpicc_context_manager import MeddpiccContextManager


class TestMeddpiccContextManagerInitialization:
    """Test MeddpiccContextManager initialization."""

    def test_initialization_with_all_custom_parameters(self):
        """Test initialization with all custom parameters."""
        # Arrange & Act
        manager = MeddpiccContextManager(
            max_messages=30,
            keep_recent=6,
            summarize_threshold=0.85,
            model_context_window=100000,
        )

        # Assert
        assert manager is not None
        assert manager.max_messages == 30
        assert manager.keep_recent == 6
        assert manager.summarize_threshold == 0.85
        assert manager.model_context_window == 100000
        assert manager.summarize_threshold_tokens == int(100000 * 0.85)

    def test_initialization_with_defaults_from_settings(self):
        """Test initialization loads defaults from Settings."""
        # Arrange & Act
        manager = MeddpiccContextManager()

        # Assert
        assert manager is not None
        assert manager.max_messages == 20  # Default from Settings
        assert manager.keep_recent == 4  # Default from Settings
        assert manager.summarize_threshold == 0.75  # Default from Settings
        assert manager.model_context_window == 128000  # Default from Settings
        assert manager.summarize_threshold_tokens == int(128000 * 0.75)

    def test_initialization_with_partial_custom_parameters(self):
        """Test initialization with some custom and some default parameters."""
        # Arrange & Act
        manager = MeddpiccContextManager(
            max_messages=25, keep_recent=5, summarize_threshold=None, model_context_window=None
        )

        # Assert
        assert manager.max_messages == 25
        assert manager.keep_recent == 5
        assert manager.summarize_threshold == 0.75  # Default from Settings
        assert manager.model_context_window == 128000  # Default from Settings

    def test_threshold_tokens_calculation(self):
        """Test that summarize_threshold_tokens is correctly calculated."""
        # Arrange & Act
        manager = MeddpiccContextManager(
            summarize_threshold=0.80, model_context_window=100000
        )

        # Assert
        expected_tokens = int(100000 * 0.80)
        assert manager.summarize_threshold_tokens == expected_tokens
        assert manager.summarize_threshold_tokens == 80000


class TestAddMessage:
    """Test add_message method."""

    def test_add_message_to_empty_history(self):
        """Test adding a message to empty conversation history."""
        # Arrange
        manager = MeddpiccContextManager()
        conversation_history = []
        role = "user"
        content = "What is MEDDPICC?"

        # Act
        result = manager.add_message(conversation_history, role, content)

        # Assert
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "What is MEDDPICC?"

    def test_add_message_to_existing_history(self):
        """Test adding a message to existing conversation history."""
        # Arrange
        manager = MeddpiccContextManager()
        conversation_history = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First response"},
        ]
        role = "user"
        content = "Second message"

        # Act
        result = manager.add_message(conversation_history, role, content)

        # Assert
        assert len(result) == 3
        assert result[2]["role"] == "user"
        assert result[2]["content"] == "Second message"

    def test_add_assistant_message(self):
        """Test adding an assistant message."""
        # Arrange
        manager = MeddpiccContextManager()
        conversation_history = [{"role": "user", "content": "User question"}]
        role = "assistant"
        content = "Assistant response with detailed analysis"

        # Act
        result = manager.add_message(conversation_history, role, content)

        # Assert
        assert len(result) == 2
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "Assistant response with detailed analysis"

    def test_add_message_with_none_history(self):
        """Test adding message when history is None."""
        # Arrange
        manager = MeddpiccContextManager()
        conversation_history = None
        role = "user"
        content = "New conversation"

        # Act
        result = manager.add_message(conversation_history, role, content)

        # Assert
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "New conversation"

    def test_add_message_preserves_existing_messages(self):
        """Test that adding message preserves all existing messages."""
        # Arrange
        manager = MeddpiccContextManager()
        conversation_history = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Message 2"},
        ]
        original_length = len(conversation_history)

        # Act
        result = manager.add_message(conversation_history, "assistant", "Response 2")

        # Assert
        assert len(result) == original_length + 1
        assert result[0]["content"] == "Message 1"
        assert result[1]["content"] == "Response 1"
        assert result[2]["content"] == "Message 2"
        assert result[3]["content"] == "Response 2"


class TestShouldCompress:
    """Test should_compress method."""

    def test_should_compress_when_exceeds_max_messages(self):
        """Test compression needed when message count exceeds max_messages."""
        # Arrange
        manager = MeddpiccContextManager(max_messages=5)
        conversation_history = [
            {"role": "user", "content": f"Message {i}"} for i in range(6)
        ]

        # Act
        result = manager.should_compress(conversation_history)

        # Assert
        assert result is True

    def test_should_not_compress_when_below_max_messages(self):
        """Test compression not needed when below max_messages."""
        # Arrange
        manager = MeddpiccContextManager(max_messages=10)
        conversation_history = [
            {"role": "user", "content": f"Message {i}"} for i in range(5)
        ]

        # Act
        result = manager.should_compress(conversation_history)

        # Assert
        assert result is False

    def test_should_compress_when_exceeds_token_threshold(self):
        """Test compression needed when estimated tokens exceed threshold."""
        # Arrange
        manager = MeddpiccContextManager(
            max_messages=100,
            summarize_threshold=0.75,
            model_context_window=1000,  # 750 token threshold
        )
        # Create messages that total > 750 tokens (estimated at 4 chars per token = 3000+ chars)
        long_content = "x" * 800  # 800 chars per message
        conversation_history = [
            {"role": "user", "content": long_content} for i in range(4)
        ]  # 3200 chars total = ~800 tokens

        # Act
        result = manager.should_compress(conversation_history)

        # Assert
        assert result is True

    def test_should_compress_includes_summary_in_token_count(self):
        """Test that existing summary is included in token estimation."""
        # Arrange
        manager = MeddpiccContextManager(
            max_messages=100,
            summarize_threshold=0.75,
            model_context_window=1000,  # 750 token threshold
        )
        conversation_history = [
            {"role": "user", "content": "x" * 400} for i in range(2)
        ]  # 800 chars = ~200 tokens
        conversation_summary = "x" * 2400  # 2400 chars = ~600 tokens, total ~800 tokens

        # Act
        result = manager.should_compress(conversation_history, conversation_summary)

        # Assert
        assert result is True

    def test_should_not_compress_when_below_thresholds(self):
        """Test no compression when both message count and tokens are below thresholds."""
        # Arrange
        manager = MeddpiccContextManager(
            max_messages=20, summarize_threshold=0.75, model_context_window=10000
        )
        conversation_history = [
            {"role": "user", "content": f"Short message {i}"} for i in range(5)
        ]

        # Act
        result = manager.should_compress(conversation_history)

        # Assert
        assert result is False

    def test_should_compress_at_exact_max_messages_boundary(self):
        """Test compression at exact max_messages boundary."""
        # Arrange
        manager = MeddpiccContextManager(max_messages=10)
        conversation_history = [
            {"role": "user", "content": f"Message {i}"} for i in range(10)
        ]

        # Act
        result = manager.should_compress(conversation_history)

        # Assert
        assert result is False  # Should compress when > max_messages, not at boundary

    def test_should_compress_with_empty_messages(self):
        """Test compression check with messages that have empty content."""
        # Arrange
        manager = MeddpiccContextManager(max_messages=5)
        conversation_history = [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": ""},
        ]

        # Act
        result = manager.should_compress(conversation_history)

        # Assert
        assert result is False


class TestCompressHistory:
    """Test compress_history method."""

    @pytest.mark.asyncio
    async def test_compress_history_when_below_keep_recent(self):
        """Test no compression when history is below keep_recent threshold."""
        # Arrange
        manager = MeddpiccContextManager(keep_recent=5)
        conversation_history = [
            {"role": "user", "content": f"Message {i}"} for i in range(3)
        ]

        # Act
        compressed_history, summary = await manager.compress_history(
            conversation_history
        )

        # Assert
        assert compressed_history == conversation_history
        assert summary == ""

    @pytest.mark.asyncio
    async def test_compress_history_keeps_recent_messages(self):
        """Test that compression keeps recent messages."""
        # Arrange
        manager = MeddpiccContextManager(keep_recent=2)
        conversation_history = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Message 2"},
            {"role": "assistant", "content": "Response 2"},
            {"role": "user", "content": "Message 3"},
        ]

        # Mock LLM response
        mock_response = Mock()
        mock_response.content = "Summary of older messages"

        with patch("services.meddpicc_context_manager.ChatOpenAI") as mock_llm_class:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_llm_class.return_value = mock_llm

            # Act
            compressed_history, summary = await manager.compress_history(
                conversation_history
            )

            # Assert
            assert len(compressed_history) == 2
            assert compressed_history[0]["content"] == "Response 2"
            assert compressed_history[1]["content"] == "Message 3"
            assert summary == "Summary of older messages"

    @pytest.mark.asyncio
    async def test_compress_history_with_existing_summary(self):
        """Test compression with existing summary."""
        # Arrange
        manager = MeddpiccContextManager(keep_recent=2)
        conversation_history = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Message 2"},
            {"role": "assistant", "content": "Response 2"},
        ]
        existing_summary = "Previous conversation summary"

        # Mock LLM response
        mock_response = Mock()
        mock_response.content = "Updated summary with new messages"

        with patch("services.meddpicc_context_manager.ChatOpenAI") as mock_llm_class:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_llm_class.return_value = mock_llm

            # Act
            compressed_history, summary = await manager.compress_history(
                conversation_history, existing_summary
            )

            # Assert
            assert len(compressed_history) == 2
            assert summary == "Updated summary with new messages"
            # Verify prompt included previous summary
            call_args = mock_llm.ainvoke.call_args[0][0]
            assert "Previous Summary:" in call_args
            assert "Previous conversation summary" in call_args

    @pytest.mark.asyncio
    async def test_compress_history_summarization_prompt_structure(self):
        """Test that summarization prompt has correct structure."""
        # Arrange
        manager = MeddpiccContextManager(keep_recent=1)
        conversation_history = [
            {"role": "user", "content": "What is MEDDPICC?"},
            {"role": "assistant", "content": "MEDDPICC is a sales methodology"},
            {"role": "user", "content": "Tell me more"},
        ]

        # Mock LLM
        mock_response = Mock()
        mock_response.content = "Summary"

        with patch("services.meddpicc_context_manager.ChatOpenAI") as mock_llm_class:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_llm_class.return_value = mock_llm

            # Act
            await manager.compress_history(conversation_history)

            # Assert - with keep_recent=1, first 2 messages are summarized
            call_args = mock_llm.ainvoke.call_args[0][0]
            assert "MEDDPICC sales coaching conversation" in call_args
            assert "User: What is MEDDPICC?" in call_args
            assert "Assistant: MEDDPICC is a sales methodology" in call_args
            assert "Summary:" in call_args

    @pytest.mark.asyncio
    async def test_compress_history_handles_llm_failure(self):
        """Test fallback when LLM compression fails."""
        # Arrange
        manager = MeddpiccContextManager(keep_recent=2)
        conversation_history = [
            {"role": "user", "content": f"Message {i}"} for i in range(6)
        ]

        # Mock LLM to raise exception
        with patch("services.meddpicc_context_manager.ChatOpenAI") as mock_llm_class:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(side_effect=Exception("API Error"))
            mock_llm_class.return_value = mock_llm

            # Act
            compressed_history, summary = await manager.compress_history(
                conversation_history
            )

            # Assert - fallback keeps more recent messages
            assert len(compressed_history) == 4  # keep_recent * 2
            assert "[Older messages: 4 interactions about sales analysis]" in summary

    @pytest.mark.asyncio
    async def test_compress_history_fallback_with_existing_summary(self):
        """Test fallback preserves existing summary."""
        # Arrange
        manager = MeddpiccContextManager(keep_recent=2)
        conversation_history = [
            {"role": "user", "content": f"Message {i}"} for i in range(6)
        ]
        existing_summary = "Existing summary content"

        # Mock LLM to raise exception
        with patch("services.meddpicc_context_manager.ChatOpenAI") as mock_llm_class:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(side_effect=Exception("API Error"))
            mock_llm_class.return_value = mock_llm

            # Act
            compressed_history, summary = await manager.compress_history(
                conversation_history, existing_summary
            )

            # Assert
            assert "Existing summary content" in summary
            assert "[Older messages:" in summary

    @pytest.mark.asyncio
    async def test_compress_history_uses_gpt4o_mini(self):
        """Test that compression uses gpt-4o-mini model."""
        # Arrange
        manager = MeddpiccContextManager(keep_recent=1)
        conversation_history = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
        ]

        # Mock LLM
        mock_response = Mock()
        mock_response.content = "Summary"

        with patch("services.meddpicc_context_manager.ChatOpenAI") as mock_llm_class:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_llm_class.return_value = mock_llm

            # Act
            await manager.compress_history(conversation_history)

            # Assert - verify ChatOpenAI called with correct model
            mock_llm_class.assert_called_once()
            call_kwargs = mock_llm_class.call_args[1]
            assert call_kwargs["model"] == "gpt-4o-mini"
            assert call_kwargs["temperature"] == 0.3


class TestBuildContextPrompt:
    """Test build_context_prompt method."""

    def test_build_prompt_analysis_mode_no_context(self):
        """Test building prompt in analysis mode with no context."""
        # Arrange
        manager = MeddpiccContextManager()
        query = "Analyze this sales opportunity"
        conversation_history = []
        conversation_summary = None

        # Act
        result = manager.build_context_prompt(
            query, conversation_history, conversation_summary, mode="analysis"
        )

        # Assert
        assert result == query

    def test_build_prompt_analysis_mode_with_summary(self):
        """Test building prompt in analysis mode with summary."""
        # Arrange
        manager = MeddpiccContextManager()
        query = "What are the next steps?"
        conversation_history = []
        conversation_summary = "Previous discussion about MEDDPICC framework"

        # Act
        result = manager.build_context_prompt(
            query, conversation_history, conversation_summary, mode="analysis"
        )

        # Assert
        assert "<Previous Conversation Summary>" in result
        assert "Previous discussion about MEDDPICC framework" in result
        assert "</Previous Conversation Summary>" in result
        assert "<Current Sales Information>" in result
        assert "What are the next steps?" in result
        assert "</Current Sales Information>" in result

    def test_build_prompt_analysis_mode_with_recent_history(self):
        """Test building prompt in analysis mode with recent conversation history."""
        # Arrange
        manager = MeddpiccContextManager()
        query = "What metrics matter?"
        conversation_history = [
            {"role": "user", "content": "Tell me about MEDDPICC"},
            {"role": "assistant", "content": "MEDDPICC is a framework"},
            {"role": "user", "content": "What metrics matter?"},  # Current query
        ]

        # Act
        result = manager.build_context_prompt(
            query, conversation_history, conversation_summary=None, mode="analysis"
        )

        # Assert
        assert "<Recent Conversation>" in result
        assert "User: Tell me about MEDDPICC" in result
        assert "Assistant: MEDDPICC is a framework" in result
        assert "</Recent Conversation>" in result
        assert "<Current Sales Information>" in result

    def test_build_prompt_followup_mode_with_context(self):
        """Test building prompt in followup mode with context."""
        # Arrange
        manager = MeddpiccContextManager()
        query = "Can you clarify the metrics?"
        conversation_history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
            {"role": "user", "content": "Can you clarify the metrics?"},
        ]
        conversation_summary = "Discussion about sales process"

        # Act
        result = manager.build_context_prompt(
            query, conversation_history, conversation_summary, mode="followup"
        )

        # Assert
        assert "<Previous Conversation Summary>" in result
        assert "Discussion about sales process" in result
        assert "<Recent Conversation>" in result
        assert "<Current Question>" in result
        assert "Can you clarify the metrics?" in result
        assert "</Current Question>" in result

    def test_build_prompt_qa_mode_ignores_context(self):
        """Test that Q&A mode returns query without historical context."""
        # Arrange
        manager = MeddpiccContextManager()
        query = "What does MEDDPICC stand for?"
        conversation_history = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"},
        ]
        conversation_summary = "Previous summary"

        # Act
        result = manager.build_context_prompt(
            query, conversation_history, conversation_summary, mode="qa"
        )

        # Assert
        assert result == query
        assert "<Previous Conversation Summary>" not in result
        assert "<Recent Conversation>" not in result

    def test_build_prompt_truncates_long_messages(self):
        """Test that long messages are truncated in recent history."""
        # Arrange
        manager = MeddpiccContextManager()
        # Create distinguishable content with numbered segments
        long_content = "".join([f"segment{i:03d}_" for i in range(50)])  # 600 chars
        query = "Current question"
        conversation_history = [
            {"role": "user", "content": long_content},
            {"role": "assistant", "content": "Short response"},
            {"role": "user", "content": "Current question"},
        ]

        # Act
        result = manager.build_context_prompt(
            query, conversation_history, conversation_summary=None, mode="analysis"
        )

        # Assert
        assert "<Recent Conversation>" in result
        assert "..." in result  # Truncation indicator
        # First part should be in result (first 300 chars)
        assert "segment000_" in result
        assert "segment020_" in result
        # Later segments (beyond 300 chars) should not appear
        assert "segment040_" not in result
        assert "segment049_" not in result

    def test_build_prompt_limits_recent_history_to_5_messages(self):
        """Test that only last 5 messages are included in recent history."""
        # Arrange
        manager = MeddpiccContextManager()
        query = "Current question"
        conversation_history = [
            {"role": "user", "content": f"Message {i}"} for i in range(12)
        ]  # 12 messages total

        # Act
        result = manager.build_context_prompt(
            query, conversation_history, conversation_summary=None, mode="analysis"
        )

        # Assert
        assert "<Recent Conversation>" in result
        # Should only include messages 6-10 (last 5, excluding current query)
        assert "Message 6" in result
        assert "Message 10" in result
        assert "Message 0" not in result
        assert "Message 5" not in result

    def test_build_prompt_handles_missing_content_field(self):
        """Test handling of messages with missing content field."""
        # Arrange
        manager = MeddpiccContextManager()
        query = "Current question"
        conversation_history = [
            {"role": "user"},  # Missing content
            {"role": "assistant", "content": "Response"},
            {"role": "user", "content": "Current question"},
        ]

        # Act
        result = manager.build_context_prompt(
            query, conversation_history, conversation_summary=None, mode="analysis"
        )

        # Assert - should not crash, should handle gracefully
        assert "<Recent Conversation>" in result
        assert "Response" in result


class TestManageContext:
    """Test manage_context method (complete workflow)."""

    @pytest.mark.asyncio
    async def test_manage_context_simple_flow(self):
        """Test complete context management without compression."""
        # Arrange
        manager = MeddpiccContextManager(max_messages=10)
        query = "Tell me about MEDDPICC"
        conversation_history = []
        conversation_summary = None

        # Act
        result = await manager.manage_context(
            query, conversation_history, conversation_summary
        )

        # Assert
        assert "conversation_history" in result
        assert "conversation_summary" in result
        assert "enhanced_query" in result
        assert len(result["conversation_history"]) == 1
        assert result["conversation_history"][0]["content"] == query
        assert result["enhanced_query"] == query

    @pytest.mark.asyncio
    async def test_manage_context_with_compression_triggered(self):
        """Test context management when compression is triggered."""
        # Arrange
        manager = MeddpiccContextManager(max_messages=3, keep_recent=1)
        query = "New question"
        conversation_history = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Message 2"},
        ]
        conversation_summary = None

        # Mock LLM for compression
        mock_response = Mock()
        mock_response.content = "Compressed summary"

        with patch("services.meddpicc_context_manager.ChatOpenAI") as mock_llm_class:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_llm_class.return_value = mock_llm

            # Act
            result = await manager.manage_context(
                query, conversation_history, conversation_summary
            )

            # Assert
            assert len(result["conversation_history"]) == 1  # Only recent message
            assert result["conversation_summary"] == "Compressed summary"
            assert "<Previous Conversation Summary>" in result["enhanced_query"]

    @pytest.mark.asyncio
    async def test_manage_context_with_none_history(self):
        """Test context management with None conversation history."""
        # Arrange
        manager = MeddpiccContextManager()
        query = "First message"
        conversation_history = None
        conversation_summary = None

        # Act
        result = await manager.manage_context(
            query, conversation_history, conversation_summary
        )

        # Assert
        assert len(result["conversation_history"]) == 1
        assert result["conversation_history"][0]["content"] == "First message"
        assert result["conversation_summary"] == ""

    @pytest.mark.asyncio
    async def test_manage_context_with_assistant_role(self):
        """Test context management with assistant role message."""
        # Arrange
        manager = MeddpiccContextManager()
        query = "Assistant response"
        conversation_history = [{"role": "user", "content": "User question"}]
        conversation_summary = None

        # Act
        result = await manager.manage_context(
            query, conversation_history, conversation_summary, role="assistant"
        )

        # Assert
        assert len(result["conversation_history"]) == 2
        assert result["conversation_history"][1]["role"] == "assistant"
        assert result["conversation_history"][1]["content"] == "Assistant response"

    @pytest.mark.asyncio
    async def test_manage_context_builds_analysis_mode_prompt(self):
        """Test that manage_context uses analysis mode for prompt building."""
        # Arrange
        manager = MeddpiccContextManager()
        query = "Analyze opportunity"
        conversation_history = [
            {"role": "user", "content": "Previous context"},
            {"role": "assistant", "content": "Previous response"},
        ]
        conversation_summary = "Summary of earlier discussion"

        # Act
        result = await manager.manage_context(
            query, conversation_history, conversation_summary
        )

        # Assert
        assert "<Previous Conversation Summary>" in result["enhanced_query"]
        assert "<Current Sales Information>" in result["enhanced_query"]
        assert "Analyze opportunity" in result["enhanced_query"]

    @pytest.mark.asyncio
    async def test_manage_context_end_to_end_multi_turn(self):
        """Test complete multi-turn conversation flow."""
        # Arrange
        manager = MeddpiccContextManager(max_messages=10, keep_recent=2)

        # Turn 1 - initial query
        result1 = await manager.manage_context(
            "What is MEDDPICC?", None, None
        )

        # Assert turn 1
        assert len(result1["conversation_history"]) == 1
        assert result1["conversation_history"][0]["content"] == "What is MEDDPICC?"
        assert result1["conversation_summary"] == ""

        # Turn 2 - add assistant response manually and send next query
        history_after_turn1 = result1["conversation_history"].copy()
        history_after_turn1.append({"role": "assistant", "content": "MEDDPICC is a framework"})

        result2 = await manager.manage_context(
            "Tell me about metrics", history_after_turn1, result1["conversation_summary"]
        )

        # Assert turn 2
        assert len(result2["conversation_history"]) == 3
        assert result2["conversation_history"][-1]["content"] == "Tell me about metrics"

        # Turn 3 - add another assistant response and send next query
        history_after_turn2 = result2["conversation_history"].copy()
        history_after_turn2.append({"role": "assistant", "content": "Metrics are important"})

        result3 = await manager.manage_context(
            "What about decision criteria?", history_after_turn2, result2["conversation_summary"]
        )

        # Assert turn 3 - should have 5 messages (no compression yet)
        assert len(result3["conversation_history"]) == 5

    @pytest.mark.asyncio
    async def test_manage_context_preserves_summary_when_no_compression(self):
        """Test that existing summary is preserved when compression is not triggered."""
        # Arrange
        manager = MeddpiccContextManager(max_messages=10)
        query = "Follow-up question"
        conversation_history = [{"role": "user", "content": "Initial message"}]
        conversation_summary = "Existing summary content"

        # Act
        result = await manager.manage_context(
            query, conversation_history, conversation_summary
        )

        # Assert
        assert result["conversation_summary"] == "Existing summary content"


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_add_message_with_empty_content(self):
        """Test adding message with empty content."""
        # Arrange
        manager = MeddpiccContextManager()
        conversation_history = []

        # Act
        result = manager.add_message(conversation_history, "user", "")

        # Assert
        assert len(result) == 1
        assert result[0]["content"] == ""

    def test_should_compress_with_empty_history(self):
        """Test compression check with empty history."""
        # Arrange
        manager = MeddpiccContextManager()
        conversation_history = []

        # Act
        result = manager.should_compress(conversation_history)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_compress_history_with_empty_history(self):
        """Test compression with empty history."""
        # Arrange
        manager = MeddpiccContextManager()
        conversation_history = []

        # Act
        compressed_history, summary = await manager.compress_history(
            conversation_history
        )

        # Assert
        assert compressed_history == []
        assert summary == ""

    def test_build_prompt_with_empty_query(self):
        """Test building prompt with empty query."""
        # Arrange
        manager = MeddpiccContextManager()
        query = ""
        conversation_history = []

        # Act
        result = manager.build_context_prompt(
            query, conversation_history, None, mode="analysis"
        )

        # Assert
        assert result == ""

    def test_build_prompt_with_single_message_history(self):
        """Test building prompt when history only has current message."""
        # Arrange
        manager = MeddpiccContextManager()
        query = "Only message"
        conversation_history = [{"role": "user", "content": "Only message"}]

        # Act
        result = manager.build_context_prompt(
            query, conversation_history, None, mode="analysis"
        )

        # Assert
        assert result == query
        assert "<Recent Conversation>" not in result

    @pytest.mark.asyncio
    async def test_manage_context_with_empty_query(self):
        """Test context management with empty query."""
        # Arrange
        manager = MeddpiccContextManager()
        query = ""
        conversation_history = None
        conversation_summary = None

        # Act
        result = await manager.manage_context(
            query, conversation_history, conversation_summary
        )

        # Assert
        assert len(result["conversation_history"]) == 1
        assert result["conversation_history"][0]["content"] == ""
        assert result["enhanced_query"] == ""
