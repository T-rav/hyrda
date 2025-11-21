"""
Tests for Internal Search Tool

Tests the LangChain-based internal search tool for company profile research.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.profiler.tools.internal_search import (
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

        # Mock direct Qdrant client
        self.mock_qdrant_client = MagicMock()

        self.tool = InternalSearchTool(
            llm=self.mock_llm,
            embeddings=self.mock_embeddings,
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
        assert self.tool.qdrant_client == self.mock_qdrant_client
        assert self.tool.vector_collection == "test-collection"

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
        # Mock embeddings for direct Qdrant search
        self.mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 1536)

        # Mock qdrant_client to return empty results
        mock_qdrant = MagicMock()
        mock_result = MagicMock()
        mock_result.points = []
        mock_qdrant.query_points.return_value = mock_result

        tool = InternalSearchTool(
            llm=self.mock_llm,
            embeddings=self.mock_embeddings,
            qdrant_client=mock_qdrant,
            vector_collection="test",
        )

        result = await tool._arun("test query")

        assert "no results" in result.lower() or "no relevant" in result.lower()

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
    async def test_metric_record_without_company_name_ignored(self):
        """
        Test that metric/CRM records are ONLY used as relationship evidence
        if the company name appears in the same document.

        This prevents false positives like:
        - Query: "SanMar" → Finds "Samaritan Ministries" CRM records
        - Should NOT mark as existing client
        """
        # Mock query decomposition to return simple queries
        decompose_response = MagicMock()
        decompose_response.content = '["sanmar case studies", "sanmar projects"]'

        # Mock embeddings
        self.mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 1536)

        # Mock Qdrant search to return a document with metric record but DIFFERENT company
        mock_point = MagicMock()
        mock_point.id = "doc1"
        mock_point.score = 0.8
        mock_point.payload = {
            "text": "Project: Samaritan - Phoenix Client: Samaritan Ministries",
            "file_name": "samaritan_project.txt",
            "record_type": "client",  # This is a metric/CRM record
        }

        mock_result = MagicMock()
        mock_result.points = [mock_point]
        self.mock_qdrant_client.query_points.return_value = mock_result

        # Mock synthesis LLM response - should see relationship_evidence: FALSE
        synthesis_response = MagicMock()
        synthesis_response.content = (
            "Relationship status: No prior engagement\n\n"
            "No evidence of work with SanMar found."
        )

        # Set up mock to return different responses for different calls
        self.mock_llm.ainvoke.side_effect = [
            decompose_response,  # Query decomposition
            synthesis_response,  # Final synthesis
        ]

        # Run search for "SanMar"
        result = await self.tool._arun("profile SanMar", effort="low")

        # Should return "No prior engagement" because "sanmar" doesn't appear in the Samaritan doc
        assert (
            "Relationship status: No prior engagement" in result
            or "no prior engagement" in result.lower()
        ), (
            f"Should not identify SanMar as existing client when only Samaritan records found. Got: {result[:500]}"
        )

        # Verify synthesis was called with relationship_evidence: FALSE
        synthesis_call = self.mock_llm.ainvoke.call_args_list[1][0][0]
        assert "relationship_evidence: FALSE" in synthesis_call, (
            "Synthesis should receive relationship_evidence: FALSE for Samaritan records without SanMar mention"
        )

    @pytest.mark.asyncio
    async def test_metric_record_with_company_name_detected(self):
        """
        Test that metric/CRM records ARE used as relationship evidence
        when the company name DOES appear in the document.
        """
        # Mock query decomposition
        decompose_response = MagicMock()
        decompose_response.content = '["acme corp case studies"]'

        # Mock embeddings
        self.mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 1536)

        # Mock Qdrant search to return document with metric record AND matching company name
        mock_point = MagicMock()
        mock_point.id = "doc1"
        mock_point.score = 0.9
        mock_point.payload = {
            "text": "Project: Acme Corp Implementation Client: Acme Corp Practice: Consulting",
            "file_name": "acme_project.txt",
            "record_type": "client",  # Metric/CRM record
        }

        mock_result = MagicMock()
        mock_result.points = [mock_point]
        self.mock_qdrant_client.query_points.return_value = mock_result

        # Mock synthesis response - should see relationship_evidence: TRUE
        synthesis_response = MagicMock()
        synthesis_response.content = (
            "Relationship status: Existing client\n\n"
            "Acme Corp is a client based on project records."
        )

        self.mock_llm.ainvoke.side_effect = [
            decompose_response,
            synthesis_response,
        ]

        # Run search for "Acme Corp"
        result = await self.tool._arun("profile Acme Corp", effort="low")

        # Should identify as existing client because "acme" appears WITH the metric record
        assert (
            "Relationship status: Existing client" in result
            or "existing client" in result.lower()
        ), (
            f"Should identify Acme as existing client when metric record has company name. Got: {result[:500]}"
        )

        # Verify synthesis was called with relationship_evidence: TRUE
        synthesis_call = self.mock_llm.ainvoke.call_args_list[1][0][0]
        assert "relationship_evidence: TRUE" in synthesis_call, (
            "Synthesis should receive relationship_evidence: TRUE when metric record contains company name"
        )

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

        mock_response1 = MagicMock()
        mock_response1.points = [mock_result1]
        mock_response2 = MagicMock()
        mock_response2.points = [mock_result2]
        self.mock_qdrant_client.query_points.side_effect = [
            mock_response1,  # First sub-query results
            mock_response2,  # Second sub-query results
        ]

        result = await self.tool._arun("test query", effort="low")

        # Verify result format
        assert "Internal Knowledge Base Search" in result
        assert "synthesized summary" in result.lower()
        assert "project_a_case_study.pdf" in result or "project_b.pdf" in result

        # Verify all components were called
        assert (
            self.mock_llm.ainvoke.call_count == 2
        )  # decompose + synthesis (no rewriting anymore)
        assert self.mock_qdrant_client.query_points.call_count == 2

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

        mock_response = MagicMock()
        mock_response.points = [duplicate_result]
        self.mock_qdrant_client.query_points.side_effect = [
            mock_response,
            mock_response,
        ]

        result = await self.tool._arun("test query", effort="low")

        # Should only appear once in results
        assert result.count("duplicate.pdf") == 1

    @pytest.mark.asyncio
    async def test_effort_levels(self):
        """Test different effort levels produce different query counts"""
        # Mock embeddings for direct Qdrant search
        self.mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 1536)

        # Mock Qdrant search
        mock_result = MagicMock()
        mock_result.points = []
        self.mock_qdrant_client.query_points.return_value = mock_result

        # Test different effort levels
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
        mock_result = MagicMock()
        mock_result.points = []
        self.mock_qdrant_client.query_points.return_value = mock_result

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
        mock_result = MagicMock()
        mock_result.points = []
        self.mock_qdrant_client.query_points.return_value = mock_result

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
        mock_qdrant_client = MagicMock()

        tool = internal_search_tool(
            llm=mock_llm,
            embeddings=mock_embeddings,
            qdrant_client=mock_qdrant_client,
            vector_collection="test",
        )

        assert isinstance(tool, InternalSearchTool)
        assert tool.llm == mock_llm
        assert tool.embeddings == mock_embeddings
        assert tool.qdrant_client == mock_qdrant_client
        assert tool.vector_collection == "test"

    def test_factory_without_components(self):
        """Test factory creates tool with lazy loading"""
        # Need at minimum the required fields for Pydantic
        tool = internal_search_tool(qdrant_client=MagicMock(), vector_collection="test")

        assert isinstance(tool, InternalSearchTool)
        # LLM and embeddings will be lazy-loaded from environment if needed

    @patch("agents.profiler.tools.internal_search.InternalSearchTool")
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
        mock_qdrant_client = MagicMock()

        tool = InternalSearchTool(
            llm=mock_llm,
            embeddings=mock_embeddings,
            qdrant_client=mock_qdrant_client,
            vector_collection="test",
        )

        # Mock decomposition
        decompose_response = MagicMock()
        decompose_response.content = '["test query"]'

        # Mock synthesis
        synthesis_response = MagicMock()
        synthesis_response.content = "Test synthesis"

        mock_llm.ainvoke.side_effect = [
            decompose_response,
            synthesis_response,
        ]

        # Mock embeddings for direct Qdrant search
        mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 1536)

        # Mock Qdrant results
        mock_result = MagicMock()
        mock_result.points = []
        mock_qdrant_client.query_points.return_value = mock_result

        # Simulate tool invocation via LangChain
        result = await tool.ainvoke({"query": "test", "effort": "low"})

        assert isinstance(result, str)
        assert len(result) > 0

    def test_tool_schema_for_binding(self):
        """Test tool has correct schema for LangChain binding"""
        tool = InternalSearchTool(
            llm=MagicMock(),
            embeddings=MagicMock(),
            qdrant_client=MagicMock(),
            vector_collection="test",
        )

        # Should have proper name and description for tool binding
        assert hasattr(tool, "name")
        assert hasattr(tool, "description")
        assert hasattr(tool, "args_schema")

        # Schema should define query and effort
        schema = tool.args_schema.model_json_schema()
        assert "query" in schema["properties"]
        assert "effort" in schema["properties"]
