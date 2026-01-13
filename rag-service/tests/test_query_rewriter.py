"""
Comprehensive tests for query rewriter service.

Tests adaptive query rewriting strategies: HyDE, semantic expansion,
document search, intent classification, and user context integration.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.query_rewriter import AdaptiveQueryRewriter


class TestAdaptiveQueryRewriterInitialization:
    """Test query rewriter initialization."""

    def test_query_rewriter_can_be_imported(self):
        """Test that AdaptiveQueryRewriter can be imported."""
        assert AdaptiveQueryRewriter is not None

    def test_query_rewriter_initialization_enabled(self):
        """Test basic query rewriter initialization with rewriting enabled."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm, enable_rewriting=True)

        assert rewriter.llm_service == mock_llm
        assert rewriter.enable_rewriting is True

    def test_query_rewriter_initialization_disabled(self):
        """Test query rewriter initialization with rewriting disabled."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm, enable_rewriting=False)

        assert rewriter.llm_service == mock_llm
        assert rewriter.enable_rewriting is False

    def test_query_rewriter_has_semantic_synonyms(self):
        """Test that semantic synonyms are defined."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        assert "project" in rewriter.SEMANTIC_SYNONYMS
        assert "client" in rewriter.SEMANTIC_SYNONYMS
        assert "engineer" in rewriter.SEMANTIC_SYNONYMS
        assert "allocation" in rewriter.SEMANTIC_SYNONYMS


class TestRewriteQueryDisabled:
    """Test query rewriting when disabled."""

    @pytest.mark.asyncio
    async def test_rewrite_query_disabled_returns_original(self):
        """Test that disabled rewriter returns original query."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm, enable_rewriting=False)

        result = await rewriter.rewrite_query("test query")

        assert result["query"] == "test query"
        assert result["original_query"] == "test query"
        assert result["strategy"] == "disabled"
        assert result["filters"] == {}
        assert result["intent"] == {}

    @pytest.mark.asyncio
    async def test_rewrite_query_disabled_with_history(self):
        """Test disabled rewriter with conversation history."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm, enable_rewriting=False)

        history = [{"role": "user", "content": "Previous question"}]
        result = await rewriter.rewrite_query("test query", conversation_history=history)

        assert result["query"] == "test query"
        assert result["strategy"] == "disabled"


class TestFormatHistory:
    """Test conversation history formatting."""

    def test_format_history_empty(self):
        """Test formatting empty history."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        result = rewriter._format_history([])

        assert result == "(No recent context)"

    def test_format_history_single_message(self):
        """Test formatting single message."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        history = [{"role": "user", "content": "Hello"}]
        result = rewriter._format_history(history)

        assert "user: Hello" in result

    def test_format_history_multiple_messages(self):
        """Test formatting multiple messages."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        history = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First response"},
            {"role": "user", "content": "Second message"},
        ]
        result = rewriter._format_history(history)

        assert "user: First message" in result
        assert "assistant: First response" in result
        assert "user: Second message" in result

    def test_format_history_truncates_long_messages(self):
        """Test that long messages are truncated."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        long_content = "a" * 300
        history = [{"role": "user", "content": long_content}]
        result = rewriter._format_history(history)

        # Should be truncated to 200 characters
        assert len(result) < 250  # user: + truncated content

    def test_format_history_last_three_messages(self):
        """Test that only last 3 messages are included."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        history = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Message 2"},
            {"role": "assistant", "content": "Response 2"},
            {"role": "user", "content": "Message 3"},
        ]
        result = rewriter._format_history(history)

        # Should only include last 3
        assert "Message 1" not in result
        assert "Response 1" not in result
        assert "Message 2" in result
        assert "Response 2" in result
        assert "Message 3" in result


class TestGetStats:
    """Test getting query rewriter statistics."""

    def test_get_stats_enabled(self):
        """Test getting stats when rewriting is enabled."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm, enable_rewriting=True)

        stats = rewriter.get_stats()

        assert stats["enabled"] is True
        assert "hyde" in stats["strategies"]
        assert "semantic" in stats["strategies"]
        assert "expansion" in stats["strategies"]
        assert "passthrough" in stats["strategies"]
        assert "project" in stats["synonym_categories"]
        assert "client" in stats["synonym_categories"]

    def test_get_stats_disabled(self):
        """Test getting stats when rewriting is disabled."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm, enable_rewriting=False)

        stats = rewriter.get_stats()

        assert stats["enabled"] is False
        assert len(stats["strategies"]) == 4
        assert len(stats["synonym_categories"]) == 4


class TestClassifyIntent:
    """Test query intent classification."""

    @pytest.mark.asyncio
    async def test_classify_intent_team_allocation(self):
        """Test classifying team allocation query."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(
            return_value='{"type": "team_allocation", "entities": ["Ticketmaster"], "time_range": {"start": null, "end": null}, "confidence": 0.95}'
        )
        rewriter = AdaptiveQueryRewriter(mock_llm)

        intent = await rewriter._classify_intent(
            "who worked on Ticketmaster projects?", [], None
        )

        assert intent["type"] == "team_allocation"
        assert "Ticketmaster" in intent["entities"]
        assert intent["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_classify_intent_project_info(self):
        """Test classifying project information query."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(
            return_value='{"type": "project_info", "entities": ["Project X"], "time_range": {"start": null, "end": null}, "confidence": 0.85}'
        )
        rewriter = AdaptiveQueryRewriter(mock_llm)

        intent = await rewriter._classify_intent("what is the status of Project X?", [], None)

        assert intent["type"] == "project_info"
        assert "Project X" in intent["entities"]

    @pytest.mark.asyncio
    async def test_classify_intent_document_search(self):
        """Test classifying document search query."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(
            return_value='{"type": "document_search", "entities": ["API", "architecture"], "time_range": {"start": null, "end": null}, "confidence": 0.9}'
        )
        rewriter = AdaptiveQueryRewriter(mock_llm)

        intent = await rewriter._classify_intent(
            "show me the architecture diagram for the API", [], None
        )

        assert intent["type"] == "document_search"
        assert "API" in intent["entities"] or "architecture" in intent["entities"]

    @pytest.mark.asyncio
    async def test_classify_intent_with_conversation_history(self):
        """Test intent classification with conversation context."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(
            return_value='{"type": "team_allocation", "entities": ["RecoveryOne", "3Step"], "time_range": {"start": null, "end": null}, "confidence": 0.9}'
        )
        rewriter = AdaptiveQueryRewriter(mock_llm)

        history = [
            {"role": "user", "content": "RecoveryOne and 3Step projects used React"},
            {"role": "assistant", "content": "Yes, both projects used React."},
        ]

        intent = await rewriter._classify_intent("which people worked on them?", history, None)

        assert intent["type"] == "team_allocation"
        # Should resolve "them" to actual entities
        mock_llm.get_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_classify_intent_with_user_context(self):
        """Test intent classification with user context for 'me/I' queries."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(
            return_value='{"type": "team_allocation", "entities": [], "time_range": {"start": null, "end": null}, "confidence": 0.85}'
        )
        rewriter = AdaptiveQueryRewriter(mock_llm)

        user_context = {
            "real_name": "John Doe",
            "email_address": "john@example.com",
        }

        await rewriter._classify_intent("what projects am I on?", [], user_context)

        # Should include user context in prompt
        call_args = mock_llm.get_response.call_args
        prompt_content = call_args[1]["messages"][0]["content"]
        assert "John Doe" in prompt_content
        assert "john@example.com" in prompt_content

    @pytest.mark.asyncio
    async def test_classify_intent_llm_returns_none(self):
        """Test intent classification when LLM returns None."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(return_value=None)
        rewriter = AdaptiveQueryRewriter(mock_llm)

        intent = await rewriter._classify_intent("test query", [], None)

        assert intent["type"] == "general"
        assert intent["confidence"] == 0.3
        assert intent["entities"] == []

    @pytest.mark.asyncio
    async def test_classify_intent_invalid_json(self):
        """Test intent classification with invalid JSON response."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(return_value="This is not JSON")
        rewriter = AdaptiveQueryRewriter(mock_llm)

        intent = await rewriter._classify_intent("test query", [], None)

        assert intent["type"] == "general"
        assert intent["confidence"] == 0.5
        assert intent["entities"] == []


class TestHydeRewrite:
    """Test HyDE (Hypothetical Document Embeddings) rewriting."""

    @pytest.mark.asyncio
    async def test_hyde_rewrite_basic(self):
        """Test basic HyDE rewriting for team allocation."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(
            return_value="Employee: John Smith\nEmail: john@company.com\nStatus: Allocated"
        )
        rewriter = AdaptiveQueryRewriter(mock_llm)

        intent = {
            "type": "team_allocation",
            "entities": ["Project X"],
            "confidence": 0.9,
        }

        result = await rewriter._hyde_rewrite("who worked on Project X?", intent, None)

        assert result["strategy"] == "hyde"
        assert "Employee:" in result["query"]
        assert result["filters"] == {"record_type": "employee"}

    @pytest.mark.asyncio
    async def test_hyde_rewrite_with_user_context(self):
        """Test HyDE rewriting with user context for 'me' queries."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(
            return_value="Employee: Jane Doe\nEmail: jane@company.com\nStatus: Allocated"
        )
        rewriter = AdaptiveQueryRewriter(mock_llm)

        user_context = {
            "real_name": "Jane Doe",
            "email_address": "jane@company.com",
        }

        intent = {
            "type": "team_allocation",
            "entities": [],
            "confidence": 0.85,
        }

        await rewriter._hyde_rewrite("what projects am I on?", intent, user_context)

        # Should generate hypothetical doc for specific user
        call_args = mock_llm.get_response.call_args
        prompt_content = call_args[1]["messages"][0]["content"]
        assert "Jane Doe" in prompt_content
        assert "jane@company.com" in prompt_content

    @pytest.mark.asyncio
    async def test_hyde_rewrite_llm_returns_none(self):
        """Test HyDE rewriting when LLM returns None."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(return_value=None)
        rewriter = AdaptiveQueryRewriter(mock_llm)

        intent = {
            "type": "team_allocation",
            "entities": ["Project X"],
            "confidence": 0.9,
        }

        result = await rewriter._hyde_rewrite("who worked on Project X?", intent, None)

        assert result["strategy"] == "passthrough"
        assert result["query"] == "who worked on Project X?"
        assert result["filters"] == {}


class TestSemanticRewrite:
    """Test semantic expansion rewriting."""

    @pytest.mark.asyncio
    async def test_semantic_rewrite_project_query(self):
        """Test semantic rewriting for project information query."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        intent = {
            "type": "project_info",
            "entities": ["Project X"],
            "confidence": 0.85,
        }

        result = await rewriter._semantic_rewrite("tell me about the project", intent)

        assert result["strategy"] == "semantic"
        assert "Project X" in result["query"]
        assert result["filters"] == {"record_type": "project"}
        # Should include project synonyms
        assert "project" in result["query"] or "initiative" in result["query"]

    @pytest.mark.asyncio
    async def test_semantic_rewrite_client_query(self):
        """Test semantic rewriting for client information query."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        intent = {
            "type": "client_info",
            "entities": ["Acme Corp"],
            "confidence": 0.9,
        }

        result = await rewriter._semantic_rewrite("tell me about the client", intent)

        assert result["strategy"] == "semantic"
        assert "Acme Corp" in result["query"]
        assert result["filters"] == {"record_type": "client"}
        # Should include client synonyms
        assert "client" in result["query"] or "customer" in result["query"]

    @pytest.mark.asyncio
    async def test_semantic_rewrite_with_time_range(self):
        """Test semantic rewriting with time range filters."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        intent = {
            "type": "project_info",
            "entities": ["Project X"],
            "time_range": {"start": "2023-01-01", "end": "2023-12-31"},
            "confidence": 0.9,
        }

        result = await rewriter._semantic_rewrite("projects in 2023", intent)

        assert result["strategy"] == "semantic"
        assert result["filters"]["start_date"] == "2023-01-01"
        assert result["filters"]["end_date"] == "2023-12-31"

    @pytest.mark.asyncio
    async def test_semantic_rewrite_multiple_synonym_categories(self):
        """Test semantic rewriting with multiple synonym categories."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        intent = {
            "type": "project_info",
            "entities": ["Project X"],
            "confidence": 0.85,
        }

        result = await rewriter._semantic_rewrite(
            "which engineers worked on the project?", intent
        )

        assert result["strategy"] == "semantic"
        # Should expand both "engineer" and "project"
        query_lower = result["query"].lower()
        assert "engineer" in query_lower or "developer" in query_lower
        assert "project" in query_lower or "initiative" in query_lower


class TestExpandQuery:
    """Test document search query expansion."""

    @pytest.mark.asyncio
    async def test_expand_query_basic(self):
        """Test basic document search expansion."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        intent = {
            "type": "document_search",
            "entities": ["API", "architecture"],
            "confidence": 0.9,
        }

        result = await rewriter._expand_query("show me the API diagram", intent)

        assert result["strategy"] == "expansion"
        assert "API" in result["query"]
        assert "architecture" in result["query"]
        assert result["filters"] == {"source": "google_drive"}
        # Should include document-related terms
        assert any(
            term in result["query"]
            for term in ["document", "file", "report", "documentation"]
        )

    @pytest.mark.asyncio
    async def test_expand_query_with_entities(self):
        """Test query expansion with multiple entities."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        intent = {
            "type": "document_search",
            "entities": ["design", "specifications", "requirements"],
            "confidence": 0.85,
        }

        result = await rewriter._expand_query("find design docs", intent)

        assert result["strategy"] == "expansion"
        assert "design" in result["query"]
        assert "specifications" in result["query"]
        assert "requirements" in result["query"]


class TestLightweightRewrite:
    """Test lightweight passthrough rewriting."""

    @pytest.mark.asyncio
    async def test_lightweight_rewrite_general_query(self):
        """Test lightweight rewrite for general query."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        intent = {
            "type": "general",
            "entities": [],
            "confidence": 0.5,
        }

        result = await rewriter._lightweight_rewrite("what is Python?", intent)

        assert result["strategy"] == "passthrough"
        assert result["query"] == "what is Python?"
        assert result["filters"] == {}

    @pytest.mark.asyncio
    async def test_lightweight_rewrite_preserves_query(self):
        """Test that lightweight rewrite preserves original query."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        intent = {"type": "general", "entities": [], "confidence": 0.3}
        original_query = "explain how async/await works"

        result = await rewriter._lightweight_rewrite(original_query, intent)

        assert result["query"] == original_query


class TestRewriteQueryIntegration:
    """Test full query rewriting workflow."""

    @pytest.mark.asyncio
    async def test_rewrite_query_team_allocation_high_confidence(self):
        """Test rewriting team allocation query with high confidence."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock()

        # First call: intent classification
        mock_llm.get_response.side_effect = [
            '{"type": "team_allocation", "entities": ["Project X"], "time_range": {"start": null, "end": null}, "confidence": 0.95}',
            "Employee: John Smith\nEmail: john@company.com\nStatus: Allocated",
        ]

        rewriter = AdaptiveQueryRewriter(mock_llm)
        result = await rewriter.rewrite_query("who worked on Project X?")

        assert result["original_query"] == "who worked on Project X?"
        assert result["strategy"] == "hyde"
        assert "Employee:" in result["query"]
        assert result["filters"] == {"record_type": "employee"}
        assert result["intent"]["type"] == "team_allocation"

    @pytest.mark.asyncio
    async def test_rewrite_query_team_allocation_low_confidence(self):
        """Test team allocation query with low confidence falls back to lightweight."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(
            return_value='{"type": "team_allocation", "entities": [], "time_range": {"start": null, "end": null}, "confidence": 0.6}'
        )

        rewriter = AdaptiveQueryRewriter(mock_llm)
        result = await rewriter.rewrite_query("who is working?")

        assert result["strategy"] == "passthrough"
        assert result["query"] == "who is working?"

    @pytest.mark.asyncio
    async def test_rewrite_query_project_info(self):
        """Test rewriting project information query."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(
            return_value='{"type": "project_info", "entities": ["Project Y"], "time_range": {"start": null, "end": null}, "confidence": 0.85}'
        )

        rewriter = AdaptiveQueryRewriter(mock_llm)
        result = await rewriter.rewrite_query("tell me about the project status")

        assert result["strategy"] == "semantic"
        assert "Project Y" in result["query"]
        assert result["filters"]["record_type"] == "project"

    @pytest.mark.asyncio
    async def test_rewrite_query_document_search(self):
        """Test rewriting document search query."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(
            return_value='{"type": "document_search", "entities": ["design"], "time_range": {"start": null, "end": null}, "confidence": 0.9}'
        )

        rewriter = AdaptiveQueryRewriter(mock_llm)
        result = await rewriter.rewrite_query("find design documents")

        assert result["strategy"] == "expansion"
        assert "design" in result["query"]
        assert result["filters"]["source"] == "google_drive"

    @pytest.mark.asyncio
    async def test_rewrite_query_general(self):
        """Test rewriting general query."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(
            return_value='{"type": "general", "entities": [], "time_range": {"start": null, "end": null}, "confidence": 0.7}'
        )

        rewriter = AdaptiveQueryRewriter(mock_llm)
        result = await rewriter.rewrite_query("what is machine learning?")

        assert result["strategy"] == "passthrough"
        assert result["query"] == "what is machine learning?"

    @pytest.mark.asyncio
    async def test_rewrite_query_with_conversation_history(self):
        """Test rewriting with conversation context."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock()

        mock_llm.get_response.side_effect = [
            '{"type": "team_allocation", "entities": ["ProjectA"], "time_range": {"start": null, "end": null}, "confidence": 0.9}',
            "Employee: Alice\nEmail: alice@company.com\nStatus: Allocated",
        ]

        rewriter = AdaptiveQueryRewriter(mock_llm)
        history = [
            {"role": "user", "content": "Tell me about ProjectA"},
            {"role": "assistant", "content": "ProjectA is an active project."},
        ]

        result = await rewriter.rewrite_query(
            "who worked on it?", conversation_history=history
        )

        assert result["strategy"] == "hyde"
        # Should use conversation context to understand "it" refers to ProjectA

    @pytest.mark.asyncio
    async def test_rewrite_query_with_user_id(self):
        """Test rewriting with user ID context (when user service doesn't exist)."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock()

        mock_llm.get_response.side_effect = [
            '{"type": "team_allocation", "entities": [], "time_range": {"start": null, "end": null}, "confidence": 0.85}',
            "Employee: Bob\nEmail: bob@company.com\nStatus: Allocated",
        ]

        rewriter = AdaptiveQueryRewriter(mock_llm)

        # User service doesn't exist in rag-service, so it will fail gracefully
        result = await rewriter.rewrite_query("what projects am I on?", user_id="U123")

        # Should still complete with HyDE strategy (without user context)
        assert result["strategy"] == "hyde"
        assert "Employee:" in result["query"]

    @pytest.mark.asyncio
    async def test_rewrite_query_error_fallback(self):
        """Test error handling with fallback to original query."""
        mock_llm = Mock()
        mock_llm.get_response = AsyncMock(side_effect=Exception("LLM API error"))

        rewriter = AdaptiveQueryRewriter(mock_llm)
        result = await rewriter.rewrite_query("test query")

        assert result["query"] == "test query"
        assert result["original_query"] == "test query"
        assert result["strategy"] == "error_fallback"
        assert result["filters"] == {}
        assert result["intent"] == {}


class TestGetUserContext:
    """Test user context retrieval."""

    def test_get_user_context_returns_none_when_service_unavailable(self):
        """Test user context returns None when user service doesn't exist."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        # User service doesn't exist in rag-service, should return None gracefully
        result = rewriter._get_user_context("U123")

        assert result is None

    def test_get_user_context_with_mocked_service(self):
        """Test user context retrieval with mocked user service."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        # Create a mock module and inject it
        mock_service_instance = Mock()
        mock_service_instance.get_user_info.return_value = {
            "real_name": "Jane Doe",
            "display_name": "jdoe",
            "email_address": "jane@company.com",
        }

        # Patch the import to return our mock
        mock_module = Mock()
        mock_module.get_user_service.return_value = mock_service_instance

        with patch.dict("sys.modules", {"services.user_service": mock_module}):
            result = rewriter._get_user_context("U123")

            assert result is not None
            assert result["real_name"] == "Jane Doe"
            assert result["email_address"] == "jane@company.com"

    def test_get_user_context_no_user_info(self):
        """Test user context when user not found."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        mock_service_instance = Mock()
        mock_service_instance.get_user_info.return_value = None

        mock_module = Mock()
        mock_module.get_user_service.return_value = mock_service_instance

        with patch.dict("sys.modules", {"services.user_service": mock_module}):
            result = rewriter._get_user_context("U123")

            assert result is None

    def test_get_user_context_service_raises_exception(self):
        """Test user context when service raises an exception."""
        mock_llm = Mock()
        rewriter = AdaptiveQueryRewriter(mock_llm)

        mock_service_instance = Mock()
        mock_service_instance.get_user_info.side_effect = Exception("Service error")

        mock_module = Mock()
        mock_module.get_user_service.return_value = mock_service_instance

        with patch.dict("sys.modules", {"services.user_service": mock_module}):
            result = rewriter._get_user_context("U123")

            assert result is None
