"""Tests for query rewriting - focusing on preventing regression of LLM method calls."""

import json
from unittest.mock import AsyncMock

import pytest

from services.query_rewriter import AdaptiveQueryRewriter


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service."""
    service = AsyncMock()
    service.get_response = AsyncMock()
    return service


@pytest.fixture
def query_rewriter(mock_llm_service):
    """Create an AdaptiveQueryRewriter instance with mocked dependencies."""
    return AdaptiveQueryRewriter(llm_service=mock_llm_service)


class TestLLMServiceMethodCalls:
    """Tests to prevent regression of LLM service method call bugs."""

    @pytest.mark.asyncio
    async def test_rewrite_query_calls_get_response_not_generate_response(
        self, query_rewriter, mock_llm_service
    ):
        """
        REGRESSION TEST: Verify query rewriter calls get_response() method.

        This test prevents the bug where query_rewriter called generate_response()
        which doesn't exist on the LLM provider, causing AttributeError.
        """
        # Mock intent classification response
        mock_intent_response = json.dumps(
            {
                "type": "general",
                "entities": [],
                "time_range": {"start": None, "end": None},
                "confidence": 0.5,
            }
        )
        mock_llm_service.get_response.return_value = mock_intent_response

        conversation_history = []

        # Execute query rewriting
        await query_rewriter.rewrite_query("test query", conversation_history)

        # CRITICAL ASSERTION: get_response was called, not generate_response
        mock_llm_service.get_response.assert_called()
        assert mock_llm_service.get_response.call_count >= 1

        # Verify mock doesn't have generate_response method (it shouldn't)
        assert not hasattr(mock_llm_service, "generate_response")

    @pytest.mark.asyncio
    async def test_get_response_called_with_correct_signature(
        self, query_rewriter, mock_llm_service
    ):
        """
        REGRESSION TEST: Verify get_response is called with correct parameters.

        Ensures the call signature matches what LLM providers expect:
        get_response(messages=[{"role": "...", "content": "..."}])
        """
        mock_intent_response = json.dumps(
            {
                "type": "employee_search",
                "entities": ["React"],
                "time_range": {"start": None, "end": None},
                "confidence": 0.8,
            }
        )
        mock_llm_service.get_response.return_value = mock_intent_response

        await query_rewriter.rewrite_query("who has react experience?", [])

        # Verify the call signature
        call_args = mock_llm_service.get_response.call_args
        assert call_args is not None
        assert "messages" in call_args.kwargs
        assert isinstance(call_args.kwargs["messages"], list)
        assert len(call_args.kwargs["messages"]) > 0

        # Verify message structure
        first_message = call_args.kwargs["messages"][0]
        assert "role" in first_message
        assert "content" in first_message
        assert isinstance(first_message["role"], str)
        assert isinstance(first_message["content"], str)

    @pytest.mark.asyncio
    async def test_classify_intent_with_conversation_history(
        self, query_rewriter, mock_llm_service
    ):
        """
        Test that conversation history is properly formatted when passed to LLM.

        Verifies that conversation history (list of message dicts) is correctly
        included in the prompt for intent classification.
        """
        mock_intent_response = json.dumps(
            {
                "type": "team_allocation",
                "entities": ["RecoveryOne", "3Step"],
                "time_range": {"start": None, "end": None},
                "confidence": 0.9,
            }
        )
        mock_llm_service.get_response.return_value = mock_intent_response

        conversation_history = [
            {"role": "user", "content": "who had react experience?"},
            {
                "role": "assistant",
                "content": "RecoveryOne and 3Step projects used React",
            },
        ]

        await query_rewriter.rewrite_query(
            "which people worked on them?", conversation_history
        )

        # Verify get_response was called
        assert mock_llm_service.get_response.called

    @pytest.mark.asyncio
    async def test_error_handling_returns_original_query(
        self, query_rewriter, mock_llm_service
    ):
        """Test that errors fall back to original query gracefully."""
        # Make LLM service raise an exception
        mock_llm_service.get_response.side_effect = Exception(
            "Simulated LLM service error"
        )

        result = await query_rewriter.rewrite_query("test query", [])

        # Should fall back to original query on error
        assert result["query"] == "test query"
        assert result["strategy"] in ["error_fallback", "passthrough"]

    @pytest.mark.asyncio
    async def test_empty_conversation_history(self, query_rewriter, mock_llm_service):
        """Test handling of empty conversation history."""
        mock_intent_response = json.dumps(
            {
                "type": "general",
                "entities": [],
                "time_range": {"start": None, "end": None},
                "confidence": 0.5,
            }
        )
        mock_llm_service.get_response.return_value = mock_intent_response

        result = await query_rewriter.rewrite_query("test query", [])

        # Should handle empty history gracefully
        assert result["query"] is not None
        assert result["strategy"] is not None
        assert mock_llm_service.get_response.called


class TestIntentClassification:
    """Tests for intent classification."""

    @pytest.mark.asyncio
    async def test_classify_intent_employee_search(
        self, query_rewriter, mock_llm_service
    ):
        """Test classifying an employee search query."""
        mock_response = json.dumps(
            {
                "type": "employee_search",
                "entities": ["React"],
                "time_range": {"start": None, "end": None},
                "confidence": 0.95,
            }
        )
        mock_llm_service.get_response.return_value = mock_response

        result = await query_rewriter._classify_intent(
            "who has react experience?", conversation_history=[]
        )

        assert result["type"] == "employee_search"
        assert "React" in result["entities"]

    @pytest.mark.asyncio
    async def test_classify_intent_with_time_range(
        self, query_rewriter, mock_llm_service
    ):
        """Test intent classification with time range extraction."""
        mock_response = json.dumps(
            {
                "type": "team_allocation",
                "entities": ["Project X"],
                "time_range": {"start": "2023-01-01", "end": "2023-12-31"},
                "confidence": 0.9,
            }
        )
        mock_llm_service.get_response.return_value = mock_response

        result = await query_rewriter._classify_intent(
            "who worked on Project X in 2023?", conversation_history=[]
        )

        assert result["type"] == "team_allocation"
        assert result["time_range"]["start"] == "2023-01-01"
        assert result["time_range"]["end"] == "2023-12-31"

    @pytest.mark.asyncio
    async def test_classify_intent_invalid_json_returns_general(
        self, query_rewriter, mock_llm_service
    ):
        """Test handling of invalid JSON response from LLM."""
        mock_llm_service.get_response.return_value = "not valid json"

        result = await query_rewriter._classify_intent(
            "test query", conversation_history=[]
        )

        # Should return general intent on parse error (not 'unknown')
        assert result["type"] == "general"
        assert result["confidence"] == 0.5  # Default confidence for general type


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_query(self, query_rewriter, mock_llm_service):
        """Test handling of empty query."""
        result = await query_rewriter.rewrite_query("", conversation_history=[])

        # Should return original empty query
        assert result["query"] == ""

    @pytest.mark.asyncio
    async def test_very_long_conversation_history(
        self, query_rewriter, mock_llm_service
    ):
        """Test handling of very long conversation history."""
        # Create a very long history
        long_history = []
        for i in range(1000):
            long_history.append({"role": "user", "content": f"message {i}"})
            long_history.append({"role": "assistant", "content": f"response {i}"})

        mock_intent_response = json.dumps(
            {
                "type": "general",
                "entities": [],
                "time_range": {"start": None, "end": None},
                "confidence": 0.5,
            }
        )
        mock_llm_service.get_response.return_value = mock_intent_response

        result = await query_rewriter.rewrite_query("test query", long_history)

        # Should handle gracefully
        assert result["query"] is not None
        assert result["strategy"] is not None

    @pytest.mark.asyncio
    async def test_special_characters_in_query(self, query_rewriter, mock_llm_service):
        """Test handling of special characters in query."""
        mock_intent_response = json.dumps(
            {
                "type": "general",
                "entities": [],
                "time_range": {"start": None, "end": None},
                "confidence": 0.5,
            }
        )
        mock_llm_service.get_response.return_value = mock_intent_response

        special_query = "who worked on C++ & Java (2023)?"
        result = await query_rewriter.rewrite_query(special_query, [])

        # Should preserve or handle special characters appropriately
        assert result["query"] is not None
        assert result["strategy"] is not None
