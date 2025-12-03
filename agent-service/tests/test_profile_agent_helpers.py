"""Unit tests for ProfileAgent helper methods.

Tests the refactored helper methods extracted from the giant run() method.
Ensures each helper method works correctly in isolation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.profile_agent import ProfileAgent


class TestProfileAgentHelpers:
    """Test suite for ProfileAgent helper methods."""

    @pytest.fixture
    def agent(self):
        """Create ProfileAgent instance for testing."""
        return ProfileAgent()

    @pytest.fixture
    def mock_context(self):
        """Create mock context for testing."""
        return {
            "user_id": "U123",
            "channel": "C123",
            "thread_ts": "1234.56",
            "thinking_ts": "1234.57",
            "llm_service": AsyncMock(),
            "slack_service": AsyncMock(),
            "conversation_cache": AsyncMock(),
        }

    # Tests for _validate_and_get_services
    def test_validate_and_get_services_success(self, agent, mock_context):
        """Test successful service extraction from context."""
        # Act
        result = agent._validate_and_get_services(mock_context)

        # Assert
        assert result is not None
        llm_service, slack_service, channel = result
        assert llm_service == mock_context["llm_service"]
        assert slack_service == mock_context["slack_service"]
        assert channel == mock_context["channel"]

    def test_validate_and_get_services_invalid_context(self, agent):
        """Test validation fails with invalid context."""
        # Arrange
        invalid_context = {}

        # Act
        result = agent._validate_and_get_services(invalid_context)

        # Assert
        assert result is None

    def test_validate_and_get_services_missing_llm(self, agent, mock_context):
        """Test validation fails when LLM service is missing."""
        # Arrange
        mock_context["llm_service"] = None

        # Act
        result = agent._validate_and_get_services(mock_context)

        # Assert
        assert result is None

    # Tests for _detect_profile_info
    @pytest.mark.asyncio
    async def test_detect_profile_info_with_focus(self, agent):
        """Test profile detection with focus area."""
        # Arrange
        mock_llm = AsyncMock()
        query = "Tell me about Tesla's AI capabilities"

        # Mock the detection functions
        from agents.profiler.utils import detect_profile_type, extract_focus_area

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "agents.profile_agent.detect_profile_type",
                AsyncMock(return_value="company"),
            )
            mp.setattr(
                "agents.profile_agent.extract_focus_area",
                AsyncMock(return_value="AI capabilities"),
            )

            # Act
            profile_type, focus_area = await agent._detect_profile_info(query, mock_llm)

            # Assert
            assert profile_type == "company"
            assert focus_area == "AI capabilities"

    # Tests for _setup_progress_message
    @pytest.mark.asyncio
    async def test_setup_progress_message_success(self, agent):
        """Test progress message setup with valid Slack service."""
        # Arrange
        mock_slack = AsyncMock()
        mock_slack.send_message.return_value = {"ts": "1234.58"}
        mock_slack.delete_thinking_indicator = AsyncMock()

        # Act
        result = await agent._setup_progress_message(
            mock_slack, "C123", "company", "1234.56", "1234.57"
        )

        # Assert
        assert result == "1234.58"
        mock_slack.delete_thinking_indicator.assert_called_once_with("C123", "1234.57")
        mock_slack.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_progress_message_no_slack_service(self, agent):
        """Test progress message returns None without Slack service."""
        # Act
        result = await agent._setup_progress_message(
            None, "C123", "company", "1234.56", "1234.57"
        )

        # Assert
        assert result is None

    # Tests for _initialize_research_service
    @pytest.mark.asyncio
    async def test_initialize_research_service_success(self, agent):
        """Test research service initialization."""
        # Arrange
        mock_service = AsyncMock()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "agents.profile_agent.get_internal_deep_research_service",
                AsyncMock(return_value=mock_service),
            )

            # Act
            result = await agent._initialize_research_service()

            # Assert
            assert result == mock_service

    # Tests for _prepare_graph_config
    def test_prepare_graph_config(self, agent):
        """Test graph configuration preparation."""
        # Arrange
        mock_llm = MagicMock()
        mock_research = MagicMock()
        thread_ts = "1234.56"
        user_id = "U123"

        # Act
        config = agent._prepare_graph_config(
            mock_llm, mock_research, thread_ts, user_id
        )

        # Assert
        assert "configurable" in config
        assert config["configurable"]["thread_id"] == thread_ts
        assert config["configurable"]["llm_service"] == mock_llm
        assert config["configurable"]["internal_deep_research"] == mock_research

    # Tests for _create_input_state
    def test_create_input_state_with_focus(self, agent):
        """Test input state creation with focus area."""
        # Arrange
        query = "Tell me about Tesla"
        profile_type = "company"
        focus_area = "AI capabilities"

        # Act
        state = agent._create_input_state(query, profile_type, focus_area)

        # Assert
        assert state["query"] == query
        assert state["profile_type"] == profile_type
        assert state["focus_area"] == focus_area
        assert len(state["messages"]) == 1

    def test_create_input_state_without_focus(self, agent):
        """Test input state creation without focus area."""
        # Arrange
        query = "Tell me about Tesla"
        profile_type = "company"

        # Act
        state = agent._create_input_state(query, profile_type, None)

        # Assert
        assert state["query"] == query
        assert state["profile_type"] == profile_type
        assert state["focus_area"] is None

    # Tests for _get_node_messages
    def test_get_node_messages(self, agent):
        """Test node messages configuration."""
        # Act
        messages = agent._get_node_messages()

        # Assert
        assert "clarify_with_user" in messages
        assert "write_research_brief" in messages
        assert "research_supervisor" in messages
        assert "final_report_generation" in messages
        assert "quality_control" in messages
        for node in messages.values():
            assert "start" in node
            assert "complete" in node

    # Tests for _get_node_order
    def test_get_node_order(self, agent):
        """Test node order list."""
        # Act
        order = agent._get_node_order()

        # Assert
        assert len(order) == 5
        assert order[0] == "clarify_with_user"
        assert order[-1] == "quality_control"

    # Tests for _generate_pdf_title
    @pytest.mark.asyncio
    async def test_generate_pdf_title_success(self, agent):
        """Test PDF title generation with successful entity extraction."""
        # Arrange
        query = "tell me about Tesla"

        with pytest.MonkeyPatch.context() as mp:
            # Mock Settings to avoid requiring environment variables
            mock_settings = MagicMock()
            mock_settings.llm.api_key = "test-api-key"
            mp.setattr("agents.profile_agent.Settings", lambda: mock_settings)

            # Mock ChatOpenAI
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = '{"entity": "Tesla"}'
            mock_llm.ainvoke.return_value = mock_response
            mp.setattr("agents.profile_agent.ChatOpenAI", lambda **kwargs: mock_llm)

            # Act
            title = await agent._generate_pdf_title(query)

            # Assert
            assert "Tesla" in title
            assert "Profile" in title

    @pytest.mark.asyncio
    async def test_generate_pdf_title_fallback(self, agent):
        """Test PDF title generation with fallback on error."""
        # Arrange
        query = "tell me about something"

        with pytest.MonkeyPatch.context() as mp:
            # Mock Settings to avoid requiring environment variables
            mock_settings = MagicMock()
            mock_settings.llm.api_key = "test-api-key"
            mp.setattr("agents.profile_agent.Settings", lambda: mock_settings)

            # Mock ChatOpenAI with error
            mock_llm = AsyncMock()
            mock_llm.ainvoke.side_effect = Exception("API error")
            mp.setattr("agents.profile_agent.ChatOpenAI", lambda **kwargs: mock_llm)

            # Act
            title = await agent._generate_pdf_title(query)

            # Assert
            assert title == "Profile"

    # Tests for _upload_pdf_to_slack
    @pytest.mark.asyncio
    async def test_upload_pdf_to_slack_success(self, agent):
        """Test successful PDF upload to Slack."""
        # Arrange
        mock_slack = AsyncMock()
        mock_slack.upload_file.return_value = {"ok": True}
        pdf_bytes = b"fake pdf content"

        # Act
        result = await agent._upload_pdf_to_slack(
            mock_slack,
            "C123",
            pdf_bytes,
            "Tesla - Profile",
            "company",
            "Tesla",
            "Executive summary here",
            "1234.56",
        )

        # Assert
        assert result is True
        mock_slack.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_pdf_to_slack_no_service(self, agent):
        """Test PDF upload returns False without Slack service."""
        # Act
        result = await agent._upload_pdf_to_slack(
            None, "C123", b"pdf", "Title", "company", "Query", None, None
        )

        # Assert
        assert result is False

    # Tests for _cache_report
    @pytest.mark.asyncio
    async def test_cache_report_success(self, agent):
        """Test successful report caching."""
        # Arrange
        mock_cache = AsyncMock()
        mock_cache.store_document_content = AsyncMock()
        mock_cache.set_thread_type = AsyncMock()

        # Act
        await agent._cache_report(
            "Report content", "company", "Tesla query", "1234.56", mock_cache
        )

        # Assert
        mock_cache.store_document_content.assert_called_once()
        mock_cache.set_thread_type.assert_called_once_with("1234.56", "profile")

    @pytest.mark.asyncio
    async def test_cache_report_no_cache_service(self, agent):
        """Test cache report handles missing cache service gracefully."""
        # Act - Should not raise exception
        await agent._cache_report(
            "Report content", "company", "Tesla query", None, None
        )

        # Assert - No exception raised

    # Tests for _determine_next_node
    def test_determine_next_node_quality_failure(self, agent):
        """Test next node determination after quality failure."""
        # Arrange
        node_order = agent._get_node_order()

        # Act
        next_node = agent._determine_next_node(
            "quality_control", True, {"revision_count": 1}, node_order
        )

        # Assert
        assert next_node == "final_report_generation"

    def test_determine_next_node_normal_flow(self, agent):
        """Test next node determination in normal flow."""
        # Arrange
        node_order = agent._get_node_order()

        # Act
        next_node = agent._determine_next_node(
            "write_research_brief", False, {}, node_order
        )

        # Assert
        assert next_node == "research_supervisor"

    def test_determine_next_node_last_node(self, agent):
        """Test next node determination at end of workflow."""
        # Arrange
        node_order = agent._get_node_order()

        # Act
        next_node = agent._determine_next_node(
            "quality_control", False, {}, node_order
        )

        # Assert
        assert next_node is None
