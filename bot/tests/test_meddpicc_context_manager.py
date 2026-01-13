"""
Tests for MEDDPICC context manager.

Comprehensive unit tests covering conversation history management,
semantic compression, and context building.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.meddpicc_context_manager import MeddpiccContextManager


# TDD Factory Patterns for MEDDPICC Context Manager Testing
class SettingsFactory:
    """Factory for creating mock settings"""

    @staticmethod
    def create_conversation_settings(
        max_messages: int = 20,
        keep_recent: int = 4,
        summarize_threshold: float = 0.75,
        model_context_window: int = 128000,
    ) -> MagicMock:
        """Create conversation settings mock"""
        settings = MagicMock()
        conversation = MagicMock()
        conversation.max_messages = max_messages
        conversation.keep_recent = keep_recent
        conversation.summarize_threshold = summarize_threshold
        conversation.model_context_window = model_context_window
        settings.conversation = conversation
        return settings


class LLMFactory:
    """Factory for creating LLM mocks"""

    @staticmethod
    def create_mock_llm(response_content: str = "Test summary") -> AsyncMock:
        """Create mock LLM with specific response"""
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = response_content
        mock_llm.ainvoke.return_value = mock_response
        return mock_llm


class ConversationFactory:
    """Factory for creating conversation history fixtures"""

    @staticmethod
    def create_empty_history() -> list[dict[str, str]]:
        """Create empty conversation history"""
        return []

    @staticmethod
    def create_simple_history(count: int = 3) -> list[dict[str, str]]:
        """Create simple conversation history with N messages"""
        history = []
        for i in range(count):
            role = "user" if i % 2 == 0 else "assistant"
            history.append({"role": role, "content": f"Message {i + 1}"})
        return history

    @staticmethod
    def create_large_history(count: int = 25) -> list[dict[str, str]]:
        """Create large conversation history exceeding max_messages"""
        history = []
        for i in range(count):
            role = "user" if i % 2 == 0 else "assistant"
            content = f"This is a longer message {i + 1} with more content to simulate real conversations."
            history.append({"role": role, "content": content})
        return history

    @staticmethod
    def create_token_heavy_history() -> list[dict[str, str]]:
        """Create conversation with heavy token usage"""
        history = []
        long_content = "This is a very long message. " * 500  # ~3000+ chars
        for i in range(10):
            role = "user" if i % 2 == 0 else "assistant"
            history.append({"role": role, "content": long_content})
        return history


class TestMeddpiccContextManagerInitialization:
    """Tests for context manager initialization"""

    def test_initialization_with_explicit_params(self):
        """Test initialization with explicit parameters"""
        # Arrange
        max_messages = 15
        keep_recent = 3
        summarize_threshold = 0.80
        model_context_window = 100000

        # Act
        manager = MeddpiccContextManager(
            max_messages=max_messages,
            keep_recent=keep_recent,
            summarize_threshold=summarize_threshold,
            model_context_window=model_context_window,
        )

        # Assert
        assert manager.max_messages == max_messages
        assert manager.keep_recent == keep_recent
        assert manager.summarize_threshold == summarize_threshold
        assert manager.model_context_window == model_context_window
        assert manager.summarize_threshold_tokens == int(
            model_context_window * summarize_threshold
        )

    def test_initialization_with_settings_fallback(self):
        """Test initialization falls back to settings when params not provided"""
        # Arrange
        mock_settings = SettingsFactory.create_conversation_settings(
            max_messages=25, keep_recent=5, summarize_threshold=0.70
        )

        # Act
        # Patch Settings in the config.settings module where it's imported from
        with patch("config.settings.Settings") as mock_settings_cls:
            mock_settings_cls.return_value = mock_settings
            # Also patch in meddpicc_context_manager since it imports Settings
            with patch(
                "services.meddpicc_context_manager.Settings"
            ) as mock_mgr_settings:
                mock_mgr_settings.return_value = mock_settings
                manager = MeddpiccContextManager()

        # Assert
        assert manager.max_messages == 25
        assert manager.keep_recent == 5
        assert manager.summarize_threshold == 0.70
        assert manager.model_context_window == 128000

    def test_threshold_tokens_calculation(self):
        """Test that threshold tokens are calculated correctly"""
        # Arrange & Act
        manager = MeddpiccContextManager(
            max_messages=20,
            keep_recent=4,
            summarize_threshold=0.75,
            model_context_window=128000,
        )

        # Assert
        expected_tokens = int(128000 * 0.75)
        assert manager.summarize_threshold_tokens == expected_tokens
        assert manager.summarize_threshold_tokens == 96000


class TestAddMessage:
    """Tests for adding messages to conversation history"""

    @pytest.fixture
    def manager(self):
        """Create context manager instance"""
        return MeddpiccContextManager(
            max_messages=20,
            keep_recent=4,
            summarize_threshold=0.75,
            model_context_window=128000,
        )

    def test_add_message_to_empty_history(self, manager):
        """Test adding message to empty history"""
        # Arrange
        history = ConversationFactory.create_empty_history()
        role = "user"
        content = "Hello, I need help with MEDDPICC"

        # Act
        updated_history = manager.add_message(history, role, content)

        # Assert
        assert len(updated_history) == 1
        assert updated_history[0]["role"] == role
        assert updated_history[0]["content"] == content

    def test_add_message_to_existing_history(self, manager):
        """Test adding message to existing history"""
        # Arrange
        history = ConversationFactory.create_simple_history(3)
        role = "assistant"
        content = "I can help with that"

        # Act
        updated_history = manager.add_message(history, role, content)

        # Assert
        assert len(updated_history) == 4
        assert updated_history[-1]["role"] == role
        assert updated_history[-1]["content"] == content

    def test_add_message_with_none_history(self, manager):
        """Test adding message when history is None"""
        # Arrange
        role = "user"
        content = "Test message"

        # Act
        updated_history = manager.add_message(None, role, content)

        # Assert
        assert len(updated_history) == 1
        assert updated_history[0]["role"] == role
        assert updated_history[0]["content"] == content

    def test_add_multiple_messages_sequentially(self, manager):
        """Test adding multiple messages in sequence"""
        # Arrange
        history = ConversationFactory.create_empty_history()

        # Act
        history = manager.add_message(history, "user", "Message 1")
        history = manager.add_message(history, "assistant", "Response 1")
        history = manager.add_message(history, "user", "Message 2")

        # Assert
        assert len(history) == 3
        assert history[0]["content"] == "Message 1"
        assert history[1]["content"] == "Response 1"
        assert history[2]["content"] == "Message 2"


class TestShouldCompress:
    """Tests for compression decision logic"""

    @pytest.fixture
    def manager(self):
        """Create context manager with known thresholds"""
        return MeddpiccContextManager(
            max_messages=10,
            keep_recent=3,
            summarize_threshold=0.75,
            model_context_window=1000,  # Small window for easier testing
        )

    def test_should_not_compress_small_history(self, manager):
        """Test that small history doesn't trigger compression"""
        # Arrange
        history = ConversationFactory.create_simple_history(5)

        # Act
        result = manager.should_compress(history)

        # Assert
        assert result is False

    def test_should_compress_when_exceeds_max_messages(self, manager):
        """Test compression triggers when message count exceeds max"""
        # Arrange
        history = ConversationFactory.create_large_history(15)  # > max_messages=10

        # Act
        result = manager.should_compress(history)

        # Assert
        assert result is True

    def test_should_compress_when_exceeds_token_threshold(self, manager):
        """Test compression triggers when token count exceeds threshold"""
        # Arrange
        # Create messages that exceed token threshold (750 tokens for 75% of 1000)
        history = []
        for _i in range(5):
            # 4000 chars = ~1000 tokens, well over threshold
            content = "x" * 4000
            history.append({"role": "user", "content": content})

        # Act
        result = manager.should_compress(history)

        # Assert
        assert result is True

    def test_should_compress_with_existing_summary(self, manager):
        """Test compression considers existing summary in token count"""
        # Arrange
        history = ConversationFactory.create_simple_history(5)
        existing_summary = "x" * 4000  # Large summary pushing over threshold

        # Act
        result = manager.should_compress(history, existing_summary)

        # Assert
        assert result is True

    def test_should_not_compress_at_boundary(self, manager):
        """Test no compression when exactly at max messages"""
        # Arrange
        history = ConversationFactory.create_simple_history(10)  # Exactly max_messages

        # Act
        result = manager.should_compress(history)

        # Assert
        # Should compress when > max_messages, not when ==
        assert result is False


class TestCompressHistory:
    """Tests for semantic compression of conversation history"""

    @pytest.fixture
    def manager(self):
        """Create context manager instance"""
        return MeddpiccContextManager(
            max_messages=20,
            keep_recent=4,
            summarize_threshold=0.75,
            model_context_window=128000,
        )

    @pytest.mark.asyncio
    async def test_compress_history_with_llm_success(self, manager):
        """Test successful compression using LLM"""
        # Arrange
        history = ConversationFactory.create_large_history(10)
        expected_summary = "Summary of sales discussion about company X"
        mock_llm = LLMFactory.create_mock_llm(expected_summary)

        # Act
        with patch("services.meddpicc_context_manager.Settings") as mock_settings_cls:
            mock_settings = MagicMock()
            mock_settings.llm.api_key = "test-key"
            mock_settings_cls.return_value = mock_settings

            with patch("services.meddpicc_context_manager.ChatOpenAI") as mock_chat:
                mock_chat.return_value = mock_llm
                compressed_history, summary = await manager.compress_history(history)

        # Assert
        assert len(compressed_history) == manager.keep_recent
        assert summary == expected_summary
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_compress_history_keeps_recent_messages(self, manager):
        """Test that compression keeps the most recent messages"""
        # Arrange
        history = ConversationFactory.create_large_history(10)
        last_messages = history[-4:]  # Last 4 messages (keep_recent=4)
        mock_llm = LLMFactory.create_mock_llm("Summary")

        # Act
        with patch("services.meddpicc_context_manager.Settings") as mock_settings_cls:
            mock_settings = MagicMock()
            mock_settings.llm.api_key = "test-key"
            mock_settings_cls.return_value = mock_settings

            with patch("services.meddpicc_context_manager.ChatOpenAI") as mock_chat:
                mock_chat.return_value = mock_llm
                compressed_history, _ = await manager.compress_history(history)

        # Assert
        assert compressed_history == last_messages

    @pytest.mark.asyncio
    async def test_compress_history_with_existing_summary(self, manager):
        """Test compression builds upon existing summary"""
        # Arrange
        history = ConversationFactory.create_large_history(10)
        existing_summary = "Previous summary about deal qualification"
        mock_llm = LLMFactory.create_mock_llm("Updated summary")

        # Act
        with patch("services.meddpicc_context_manager.Settings") as mock_settings_cls:
            mock_settings = MagicMock()
            mock_settings.llm.api_key = "test-key"
            mock_settings_cls.return_value = mock_settings

            with patch("services.meddpicc_context_manager.ChatOpenAI") as mock_chat:
                mock_chat.return_value = mock_llm
                _, summary = await manager.compress_history(history, existing_summary)

        # Assert
        assert summary == "Updated summary"
        # Verify existing summary was included in prompt
        call_args = mock_llm.ainvoke.call_args[0][0]
        assert "Previous Summary:" in call_args
        assert existing_summary in call_args

    @pytest.mark.asyncio
    async def test_compress_history_when_below_threshold(self, manager):
        """Test no compression when history is below keep_recent threshold"""
        # Arrange
        history = ConversationFactory.create_simple_history(3)  # < keep_recent=4

        # Act
        compressed_history, summary = await manager.compress_history(history)

        # Assert
        assert compressed_history == history
        assert summary == ""

    @pytest.mark.asyncio
    async def test_compress_history_with_existing_summary_below_threshold(
        self, manager
    ):
        """Test existing summary preserved when no compression needed"""
        # Arrange
        history = ConversationFactory.create_simple_history(3)
        existing_summary = "Existing summary"

        # Act
        compressed_history, summary = await manager.compress_history(
            history, existing_summary
        )

        # Assert
        assert compressed_history == history
        assert summary == existing_summary

    @pytest.mark.asyncio
    async def test_compress_history_llm_failure_fallback(self, manager):
        """Test fallback behavior when LLM compression fails"""
        # Arrange
        history = ConversationFactory.create_large_history(20)
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("LLM API failed")

        # Act
        with patch("services.meddpicc_context_manager.Settings") as mock_settings_cls:
            mock_settings = MagicMock()
            mock_settings.llm.api_key = "test-key"
            mock_settings_cls.return_value = mock_settings

            with patch("services.meddpicc_context_manager.ChatOpenAI") as mock_chat:
                mock_chat.return_value = mock_llm
                compressed_history, summary = await manager.compress_history(history)

        # Assert - fallback keeps more recent messages (keep_recent * 2)
        assert len(compressed_history) == manager.keep_recent * 2
        assert "[Older messages:" in summary
        assert "interactions about sales analysis]" in summary

    @pytest.mark.asyncio
    async def test_compress_history_prompt_structure(self, manager):
        """Test that compression prompt has correct structure"""
        # Arrange
        history = ConversationFactory.create_large_history(10)
        mock_llm = LLMFactory.create_mock_llm("Summary")

        # Act
        with patch("services.meddpicc_context_manager.Settings") as mock_settings_cls:
            mock_settings = MagicMock()
            mock_settings.llm.api_key = "test-key"
            mock_settings_cls.return_value = mock_settings

            with patch("services.meddpicc_context_manager.ChatOpenAI") as mock_chat:
                mock_chat.return_value = mock_llm
                await manager.compress_history(history)

        # Assert
        call_args = mock_llm.ainvoke.call_args[0][0]
        assert "MEDDPICC sales coaching conversation" in call_args
        assert "Messages to Summarize:" in call_args
        assert "Summary:" in call_args


class TestBuildContextPrompt:
    """Tests for building contextual prompts"""

    @pytest.fixture
    def manager(self):
        """Create context manager instance"""
        return MeddpiccContextManager(
            max_messages=20,
            keep_recent=4,
            summarize_threshold=0.75,
            model_context_window=128000,
        )

    def test_build_context_analysis_mode_no_context(self, manager):
        """Test building prompt in analysis mode without context"""
        # Arrange
        query = "Analyze this deal"
        history = []

        # Act
        prompt = manager.build_context_prompt(query, history, mode="analysis")

        # Assert
        assert prompt == query
        assert "<Previous Conversation Summary>" not in prompt
        assert "<Recent Conversation>" not in prompt

    def test_build_context_analysis_mode_with_summary(self, manager):
        """Test building prompt with conversation summary"""
        # Arrange
        query = "Analyze this deal"
        history = ConversationFactory.create_simple_history(3)
        summary = "Previous discussion about company metrics"

        # Act
        prompt = manager.build_context_prompt(
            query, history, conversation_summary=summary, mode="analysis"
        )

        # Assert
        assert "<Previous Conversation Summary>" in prompt
        assert summary in prompt
        assert "<Current Sales Information>" in prompt
        assert query in prompt

    def test_build_context_analysis_mode_with_history(self, manager):
        """Test building prompt with recent conversation history"""
        # Arrange
        query = "What about their competition?"
        history = [
            {"role": "user", "content": "Tell me about company X"},
            {"role": "assistant", "content": "Company X is in tech sector"},
            {"role": "user", "content": query},
        ]

        # Act
        prompt = manager.build_context_prompt(query, history, mode="analysis")

        # Assert
        assert "<Recent Conversation>" in prompt
        assert "Tell me about company X" in prompt
        assert "Company X is in tech sector" in prompt
        assert "<Current Sales Information>" in prompt
        assert query in prompt

    def test_build_context_followup_mode(self, manager):
        """Test building prompt in followup mode"""
        # Arrange
        query = "What did we discuss about metrics?"
        history = ConversationFactory.create_simple_history(5)
        summary = "Previous MEDDPICC analysis"

        # Act
        prompt = manager.build_context_prompt(
            query, history, conversation_summary=summary, mode="followup"
        )

        # Assert
        assert "<Previous Conversation Summary>" in prompt
        assert summary in prompt
        assert "<Current Question>" in prompt
        assert query in prompt

    def test_build_context_followup_mode_no_context(self, manager):
        """Test building prompt in followup mode without context"""
        # Arrange
        query = "What is MEDDPICC?"
        history = []

        # Act
        prompt = manager.build_context_prompt(query, history, mode="followup")

        # Assert
        assert prompt == query
        assert "<Previous Conversation Summary>" not in prompt
        assert "<Current Question>" not in prompt

    def test_build_context_qa_mode(self, manager):
        """Test building prompt in Q&A mode (no context needed)"""
        # Arrange
        query = "What is MEDDPICC?"
        history = ConversationFactory.create_simple_history(5)
        summary = "Previous conversation"

        # Act
        prompt = manager.build_context_prompt(
            query, history, conversation_summary=summary, mode="qa"
        )

        # Assert
        assert prompt == query
        assert "<Previous Conversation Summary>" not in prompt
        assert "<Recent Conversation>" not in prompt

    def test_build_context_limits_recent_history(self, manager):
        """Test that only last 5 messages are included in context"""
        # Arrange
        query = "Current query"
        history = []
        for i in range(10):
            history.append({"role": "user", "content": f"Message {i}"})
        history.append({"role": "user", "content": query})

        # Act
        prompt = manager.build_context_prompt(query, history, mode="analysis")

        # Assert
        assert "<Recent Conversation>" in prompt
        # Should only include messages 5-9 (last 5 before current query)
        assert "Message 5" in prompt or "Message 6" in prompt
        assert "Message 0" not in prompt
        assert "Message 1" not in prompt

    def test_build_context_truncates_long_messages(self, manager):
        """Test that very long messages are truncated"""
        # Arrange
        query = "Current query"
        long_content = "x" * 500  # 500 characters
        history = [
            {"role": "user", "content": long_content},
            {"role": "user", "content": query},
        ]

        # Act
        prompt = manager.build_context_prompt(query, history, mode="analysis")

        # Assert
        assert "<Recent Conversation>" in prompt
        # Should truncate at 300 chars with ellipsis
        assert "..." in prompt

    def test_build_context_excludes_current_query_from_history(self, manager):
        """Test that current query is not duplicated in history section"""
        # Arrange
        query = "This is the current query"
        history = [
            {"role": "user", "content": "Previous message"},
            {"role": "user", "content": query},  # Current query as last message
        ]

        # Act
        prompt = manager.build_context_prompt(query, history, mode="analysis")

        # Assert
        # Query should appear in <Current Sales Information> but not in <Recent Conversation>
        assert prompt.count(query) == 1
        assert "<Recent Conversation>" in prompt
        assert "Previous message" in prompt


class TestManageContext:
    """Tests for the main context management method"""

    @pytest.fixture
    def manager(self):
        """Create context manager instance"""
        return MeddpiccContextManager(
            max_messages=10,  # Small for easier testing
            keep_recent=3,
            summarize_threshold=0.75,
            model_context_window=1000,
        )

    @pytest.mark.asyncio
    async def test_manage_context_first_message(self, manager):
        """Test managing context for first message in conversation"""
        # Arrange
        query = "Help me qualify this deal"

        # Act
        result = await manager.manage_context(query, None, None)

        # Assert
        assert "conversation_history" in result
        assert "conversation_summary" in result
        assert "enhanced_query" in result
        assert len(result["conversation_history"]) == 1
        assert result["conversation_history"][0]["content"] == query
        assert result["conversation_summary"] == ""
        assert result["enhanced_query"] == query

    @pytest.mark.asyncio
    async def test_manage_context_without_compression(self, manager):
        """Test managing context when compression not needed"""
        # Arrange
        query = "What about metrics?"
        existing_history = ConversationFactory.create_simple_history(3)

        # Act
        result = await manager.manage_context(query, existing_history, None)

        # Assert
        assert len(result["conversation_history"]) == 4  # 3 + new query
        assert result["conversation_history"][-1]["content"] == query
        assert result["conversation_summary"] == ""
        assert query in result["enhanced_query"]

    @pytest.mark.asyncio
    async def test_manage_context_with_compression(self, manager):
        """Test managing context when compression is triggered"""
        # Arrange
        query = "Latest update"
        # Create history that exceeds max_messages
        existing_history = ConversationFactory.create_large_history(12)
        mock_llm = LLMFactory.create_mock_llm("Compressed summary")

        # Act
        with patch("services.meddpicc_context_manager.Settings") as mock_settings_cls:
            mock_settings = MagicMock()
            mock_settings.llm.api_key = "test-key"
            mock_settings_cls.return_value = mock_settings

            with patch("services.meddpicc_context_manager.ChatOpenAI") as mock_chat:
                mock_chat.return_value = mock_llm
                result = await manager.manage_context(query, existing_history, None)

        # Assert
        # History should be compressed to keep_recent messages
        assert len(result["conversation_history"]) == manager.keep_recent
        assert result["conversation_summary"] == "Compressed summary"
        assert query in result["enhanced_query"]
        assert "<Previous Conversation Summary>" in result["enhanced_query"]

    @pytest.mark.asyncio
    async def test_manage_context_preserves_existing_summary(self, manager):
        """Test that existing summary is preserved and built upon"""
        # Arrange
        query = "New question"
        existing_history = ConversationFactory.create_large_history(12)
        existing_summary = "Previous summary of deal"
        mock_llm = LLMFactory.create_mock_llm("Updated summary")

        # Act
        with patch("services.meddpicc_context_manager.Settings") as mock_settings_cls:
            mock_settings = MagicMock()
            mock_settings.llm.api_key = "test-key"
            mock_settings_cls.return_value = mock_settings

            with patch("services.meddpicc_context_manager.ChatOpenAI") as mock_chat:
                mock_chat.return_value = mock_llm
                result = await manager.manage_context(
                    query, existing_history, existing_summary
                )

        # Assert
        assert result["conversation_summary"] == "Updated summary"

    @pytest.mark.asyncio
    async def test_manage_context_with_custom_role(self, manager):
        """Test managing context with custom message role"""
        # Arrange
        query = "This is a system message"
        existing_history = ConversationFactory.create_simple_history(2)

        # Act
        result = await manager.manage_context(
            query, existing_history, None, role="assistant"
        )

        # Assert
        assert result["conversation_history"][-1]["role"] == "assistant"
        assert result["conversation_history"][-1]["content"] == query

    @pytest.mark.asyncio
    async def test_manage_context_returns_all_required_fields(self, manager):
        """Test that manage_context returns all required fields"""
        # Arrange
        query = "Test query"

        # Act
        result = await manager.manage_context(query, None, None)

        # Assert
        assert isinstance(result, dict)
        assert "conversation_history" in result
        assert "conversation_summary" in result
        assert "enhanced_query" in result
        assert isinstance(result["conversation_history"], list)
        assert isinstance(result["conversation_summary"], str)
        assert isinstance(result["enhanced_query"], str)


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    @pytest.fixture
    def manager(self):
        """Create context manager instance"""
        return MeddpiccContextManager(
            max_messages=20,
            keep_recent=4,
            summarize_threshold=0.75,
            model_context_window=128000,
        )

    def test_add_message_with_empty_content(self, manager):
        """Test adding message with empty content"""
        # Arrange
        history = []

        # Act
        updated_history = manager.add_message(history, "user", "")

        # Assert
        assert len(updated_history) == 1
        assert updated_history[0]["content"] == ""

    def test_should_compress_with_empty_history(self, manager):
        """Test compression check with empty history"""
        # Arrange
        history = []

        # Act
        result = manager.should_compress(history)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_compress_history_with_empty_messages(self, manager):
        """Test compression with messages containing empty content"""
        # Arrange
        history = [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": ""},
            {"role": "user", "content": ""},
            {"role": "assistant", "content": ""},
            {"role": "user", "content": "Valid message"},
        ]
        mock_llm = LLMFactory.create_mock_llm("Summary")

        # Act
        with patch("services.meddpicc_context_manager.Settings") as mock_settings_cls:
            mock_settings = MagicMock()
            mock_settings.llm.api_key = "test-key"
            mock_settings_cls.return_value = mock_settings

            with patch("services.meddpicc_context_manager.ChatOpenAI") as mock_chat:
                mock_chat.return_value = mock_llm
                compressed_history, summary = await manager.compress_history(history)

        # Assert
        assert len(compressed_history) == manager.keep_recent

    def test_build_context_with_missing_content_field(self, manager):
        """Test building context when messages have missing 'content' field"""
        # Arrange
        query = "Test query"
        history = [
            {"role": "user"},  # Missing content
            {"role": "assistant", "content": "Valid message"},
            {"role": "user", "content": query},
        ]

        # Act
        prompt = manager.build_context_prompt(query, history, mode="analysis")

        # Assert
        # Should handle missing content gracefully
        assert "Valid message" in prompt
        assert "<Recent Conversation>" in prompt

    @pytest.mark.asyncio
    async def test_manage_context_with_none_summary(self, manager):
        """Test manage_context explicitly handles None summary"""
        # Arrange
        query = "Test query"
        history = ConversationFactory.create_simple_history(2)

        # Act
        result = await manager.manage_context(query, history, None)

        # Assert
        assert result["conversation_summary"] == ""
        assert isinstance(result["conversation_summary"], str)
