"""
Tests for Internal Search Tool

Tests the LangChain-based internal search tool for company profile research.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.company_profile.tools.internal_search import (
    InternalSearchInput,
    InternalSearchTool,
    internal_search_tool,
)


class TestInternalSearchTool:
    """Test internal search tool functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        # Mock LangChain components
        self.mock_llm = AsyncMock()
        self.mock_embeddings = MagicMock()
        self.mock_vector_store = AsyncMock()

        # Mock direct Qdrant client
        self.mock_qdrant_client = MagicMock()

        self.tool = InternalSearchTool(
            llm=self.mock_llm,
            embeddings=self.mock_embeddings,
            vector_store=self.mock_vector_store,
            qdrant_client=self.mock_qdrant_client,
            vector_collection="test-collection",
        )

    def test_tool_initialization(self):
        """Test tool initializes with correct properties"""
        assert self.tool.name == "internal_search_tool"
        assert "internal knowledge base" in self.tool.description.lower()
        assert self.tool.args_schema == InternalSearchInput
        assert self.tool.llm == self.mock_llm
        assert self.tool.embeddings == self.mock_embeddings
        assert self.tool.vector_store == self.mock_vector_store

    def test_tool_input_schema(self):
        """Test tool input schema validation"""
        # Valid input
        valid_input = InternalSearchInput(query="test query", effort="medium")
        assert valid_input.query == "test query"
        assert valid_input.effort == "medium"

        # Default effort
        default_input = InternalSearchInput(query="test")
        assert default_input.effort == "medium"

    @pytest.mark.asyncio
    async def test_search_without_vector_store(self):
        """Test search fails gracefully without vector store"""
        tool = InternalSearchTool(
            llm=self.mock_llm,
            embeddings=self.mock_embeddings,
            vector_store=None,
            qdrant_client=MagicMock(),
            vector_collection="test",
        )

        result = await tool._arun("test query")

        assert "not available" in result.lower()
        assert "vector database" in result.lower()

    @pytest.mark.asyncio
    async def test_query_decomposition(self):
        """Test query decomposition into sub-queries"""
        # Mock LLM response with sub-queries
        mock_response = MagicMock()
        mock_response.content = '["sub-query 1", "sub-query 2", "sub-query 3"]'
        self.mock_llm.ainvoke.return_value = mock_response

        sub_queries = await self.tool._decompose_query("complex query", num_queries=3)

        assert len(sub_queries) == 3
        assert "sub-query 1" in sub_queries
        assert "sub-query 2" in sub_queries
        assert "sub-query 3" in sub_queries
        self.mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_decomposition_invalid_json(self):
        """Test query decomposition falls back on invalid JSON"""
        # Mock LLM response with invalid JSON
        mock_response = MagicMock()
        mock_response.content = "This is not valid JSON"
        self.mock_llm.ainvoke.return_value = mock_response

        original_query = "test query"
        sub_queries = await self.tool._decompose_query(original_query, num_queries=3)

        # Should fallback to original query
        assert len(sub_queries) == 1
        assert sub_queries[0] == original_query

    @pytest.mark.asyncio
    async def test_query_rewriting(self):
        """Test query rewriting for internal knowledge"""
        # Mock LLM response with rewritten query
        mock_response = MagicMock()
        mock_response.content = "What past React projects have we completed and what implementations did we use?"
        self.mock_llm.ainvoke.return_value = mock_response

        rewritten = await self.tool._rewrite_query("React projects", "similar work")

        assert "past" in rewritten.lower()
        assert "react" in rewritten.lower()
        assert len(rewritten) > 0
        self.mock_llm.ainvoke.assert_called_once()

        # Check prompt mentions internal knowledge
        call_args = self.mock_llm.ainvoke.call_args[0][0]
        assert "internal" in call_args.lower()
        assert "past" in call_args.lower()

    @pytest.mark.asyncio
    async def test_query_rewriting_fallback(self):
        """Test query rewriting falls back on error"""
        # Mock LLM to raise exception
        self.mock_llm.ainvoke.side_effect = Exception("LLM error")

        original_query = "test query"
        rewritten = await self.tool._rewrite_query(original_query, "context")

        # Should fallback to original
        assert rewritten == original_query

    @pytest.mark.asyncio
    async def test_full_search_flow(self):
        """Test complete search flow with decomposition and retrieval"""
        # Mock query decomposition
        decompose_response = MagicMock()
        decompose_response.content = '["sub-query 1", "sub-query 2"]'

        # Mock synthesis
        synthesis_response = MagicMock()
        synthesis_response.content = "This is a synthesized summary of findings."

        self.mock_llm.ainvoke.side_effect = [
            decompose_response,
            synthesis_response,
        ]

        # Mock embeddings for _direct_qdrant_search
        self.mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 1536)

        # Mock Qdrant search results
        mock_result1 = MagicMock()
        mock_result1.payload = {
            "text": "Content from project A case study",
            "file_name": "project_a_case_study.pdf",
        }
        mock_result1.score = 0.9

        mock_result2 = MagicMock()
        mock_result2.payload = {
            "text": "Content from project B",
            "file_name": "project_b.pdf",
        }
        mock_result2.score = 0.85

        self.mock_qdrant_client.search.side_effect = [
            [mock_result1],  # First sub-query results
            [mock_result2],  # Second sub-query results
        ]

        result = await self.tool._arun("test query", effort="low")

        # Verify result format
        assert "Internal Knowledge Base Search" in result
        assert "synthesized summary" in result.lower()
        assert "project_a.pdf" in result or "project_b.pdf" in result

        # Verify all components were called
        assert (
            self.mock_llm.ainvoke.call_count == 2
        )  # decompose + synthesis (no rewriting anymore)
        assert self.mock_vector_store.asimilarity_search_with_score.call_count == 2

    @pytest.mark.asyncio
    async def test_deduplication(self):
        """Test that duplicate documents are deduplicated"""
        # Mock query decomposition
        decompose_response = MagicMock()
        decompose_response.content = '["query 1", "query 2"]'

        synthesis_response = MagicMock()
        synthesis_response.content = "Synthesized findings"

        self.mock_llm.ainvoke.side_effect = [
            decompose_response,
            synthesis_response,
        ]

        # Mock embeddings
        self.mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 1536)

        # Same document returned for both queries
        duplicate_result = MagicMock()
        duplicate_result.payload = {
            "text": "Duplicate content here",
            "file_name": "duplicate.pdf",
        }
        duplicate_result.score = 0.9

        self.mock_qdrant_client.search.side_effect = [
            [duplicate_result],
            [duplicate_result],
        ]

        result = await self.tool._arun("test query", effort="low")

        # Should only appear once in results
        assert result.count("duplicate.pdf") == 1

    @pytest.mark.asyncio
    async def test_effort_levels(self):
        """Test different effort levels produce different query counts"""
        # Mock responses
        self.mock_llm.ainvoke.return_value = MagicMock(content="[]")
        self.mock_vector_store.asimilarity_search_with_score.return_value = []

        # Low effort
        for effort, expected_queries in [("low", 2), ("medium", 3), ("high", 5)]:
            self.mock_llm.ainvoke.reset_mock()
            self.mock_llm.ainvoke.return_value = MagicMock(
                content='["q1", "q2", "q3", "q4", "q5"]'[: expected_queries * 8]
            )

            await self.tool._arun(f"test query {effort}", effort=effort)

            # Decomposition should be called with appropriate num_queries
            decompose_call = self.mock_llm.ainvoke.call_args_list[0][0][0]
            assert f"{expected_queries}" in decompose_call

    @pytest.mark.asyncio
    async def test_no_results_handling(self):
        """Test handling when no documents are found"""
        # Mock query decomposition
        decompose_response = MagicMock()
        decompose_response.content = '["query 1"]'

        rewrite_response = MagicMock()
        rewrite_response.content = "Rewritten query"

        self.mock_llm.ainvoke.side_effect = [decompose_response, rewrite_response]

        # Mock embeddings
        self.mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 1536)

        # No results from Qdrant
        self.mock_qdrant_client.search.return_value = []

        result = await self.tool._arun("test query")

        assert "No relevant information found" in result

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling during search with graceful degradation"""
        # Mock to raise exception during decomposition
        self.mock_llm.ainvoke.side_effect = Exception("LLM failure")

        # Mock embeddings
        self.mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 1536)

        # Mock Qdrant to return no results
        self.mock_qdrant_client.search.return_value = []

        result = await self.tool._arun("test query")

        # Tool should gracefully degrade and continue with original query
        # Since no results, should return "no relevant information" message
        assert (
            "no relevant information" in result.lower()
            or "not available" in result.lower()
        )

    def test_sync_run_not_supported(self):
        """Test that sync run returns appropriate message"""
        result = self.tool._run("test query")

        assert "async" in result.lower()
        assert "ainvoke" in result.lower()


class TestInternalSearchToolFactory:
    """Test factory function"""

    def test_factory_with_components(self):
        """Test factory creates tool with provided components"""
        mock_llm = MagicMock()
        mock_embeddings = MagicMock()
        mock_vector_store = MagicMock()

        tool = internal_search_tool(
            llm=mock_llm, embeddings=mock_embeddings, vector_store=mock_vector_store
        )

        assert isinstance(tool, InternalSearchTool)
        assert tool.llm == mock_llm
        assert tool.embeddings == mock_embeddings
        assert tool.vector_store == mock_vector_store

    def test_factory_without_components(self):
        """Test factory creates tool with lazy loading"""
        tool = internal_search_tool()

        assert isinstance(tool, InternalSearchTool)
        # Components will be None until lazy-loaded
        # (which requires environment variables)

    @patch("agents.company_profile.tools.internal_search.InternalSearchTool")
    def test_factory_error_handling(self, mock_tool_class):
        """Test factory handles errors gracefully"""
        mock_tool_class.side_effect = Exception("Initialization failed")

        result = internal_search_tool()

        assert result is None


class TestInternalSearchToolIntegration:
    """Integration tests with researcher node"""

    @pytest.mark.asyncio
    async def test_tool_in_langchain_workflow(self):
        """Test tool works with LangChain tool binding"""

        # Create tool with mocks
        mock_llm = AsyncMock()
        mock_embeddings = MagicMock()
        mock_vector_store = AsyncMock()

        tool = InternalSearchTool(
            llm=mock_llm, embeddings=mock_embeddings, vector_store=mock_vector_store
        )

        # Mock decomposition
        decompose_response = MagicMock()
        decompose_response.content = '["test query"]'

        # Mock rewriting
        rewrite_response = MagicMock()
        rewrite_response.content = "Rewritten test query"

        # Mock synthesis
        synthesis_response = MagicMock()
        synthesis_response.content = "Test synthesis"

        mock_llm.ainvoke.side_effect = [
            decompose_response,
            rewrite_response,
            synthesis_response,
        ]

        # Mock vector results
        mock_vector_store.asimilarity_search_with_score.return_value = []

        # Simulate tool invocation via LangChain
        result = await tool.ainvoke({"query": "test", "effort": "low"})

        assert isinstance(result, str)
        assert len(result) > 0

    def test_tool_schema_for_binding(self):
        """Test tool has correct schema for LangChain binding"""
        tool = InternalSearchTool(
            llm=MagicMock(), embeddings=MagicMock(), vector_store=MagicMock()
        )

        # Should have proper name and description for tool binding
        assert hasattr(tool, "name")
        assert hasattr(tool, "description")
        assert hasattr(tool, "args_schema")

        # Schema should define query and effort
        schema = tool.args_schema.model_json_schema()
        assert "query" in schema["properties"]
        assert "effort" in schema["properties"]
