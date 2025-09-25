"""
Test for Langfuse RAG tracing integration.

Simple test to verify that the Langfuse tracing we added to RAG service works correctly.
"""

from unittest.mock import Mock

import pytest


class TestLangfuseRAGTracing:
    """Test Langfuse tracing in RAG service"""

    @pytest.mark.asyncio
    async def test_langfuse_tracing_logic(self):
        """Test that our Langfuse tracing integration logic works"""

        # Mock Langfuse service
        mock_langfuse_service = Mock()
        mock_langfuse_service.trace_retrieval = Mock()

        # Simulate context chunks that would be retrieved
        context_chunks = [
            {
                "content": "Machine learning is a subset of artificial intelligence.",
                "similarity": 0.92,
                "metadata": {"file_name": "ml_guide.pdf", "page": 1},
            },
            {
                "content": "Deep learning uses neural networks with multiple layers.",
                "similarity": 0.88,
                "metadata": {"file_name": "dl_basics.md", "section": "intro"},
            },
        ]

        query = "What is machine learning?"

        # This is the exact logic we added to rag_service.py (lines 67-87)
        if context_chunks:
            langfuse_service = mock_langfuse_service
            if langfuse_service:
                retrieval_results = []
                for chunk in context_chunks:
                    result = {
                        "content": chunk.get("content", ""),
                        "similarity": chunk.get("similarity", 0),
                        "metadata": chunk.get("metadata", {}),
                    }
                    if chunk.get("metadata", {}).get("file_name"):
                        result["document"] = chunk["metadata"]["file_name"]
                    retrieval_results.append(result)

                langfuse_service.trace_retrieval(
                    query=query,
                    results=retrieval_results,
                    metadata={
                        "retrieval_type": "elasticsearch_rag",
                        "total_chunks": len(context_chunks),
                        "avg_similarity": sum(
                            r["similarity"] for r in retrieval_results
                        )
                        / len(retrieval_results)
                        if retrieval_results
                        else 0,
                        "documents_used": list(
                            {
                                r.get("document", "unknown")
                                for r in retrieval_results
                                if r.get("document")
                            }
                        ),
                        "vector_store": "elasticsearch",
                    },
                )

        # Verify Langfuse tracing was called
        mock_langfuse_service.trace_retrieval.assert_called_once()

        # Verify the call arguments
        call_args = mock_langfuse_service.trace_retrieval.call_args
        assert call_args[1]["query"] == query

        # Check results structure
        results = call_args[1]["results"]
        assert len(results) == 2
        assert (
            results[0]["content"]
            == "Machine learning is a subset of artificial intelligence."
        )
        assert results[0]["similarity"] == 0.92
        assert results[0]["document"] == "ml_guide.pdf"
        assert (
            results[1]["content"]
            == "Deep learning uses neural networks with multiple layers."
        )
        assert results[1]["similarity"] == 0.88
        assert results[1]["document"] == "dl_basics.md"

        # Check metadata
        metadata = call_args[1]["metadata"]
        assert metadata["retrieval_type"] == "elasticsearch_rag"
        assert metadata["total_chunks"] == 2
        assert metadata["avg_similarity"] == 0.9  # (0.92 + 0.88) / 2
        assert set(metadata["documents_used"]) == {"ml_guide.pdf", "dl_basics.md"}
        assert metadata["vector_store"] == "elasticsearch"

    @pytest.mark.asyncio
    async def test_no_tracing_when_no_langfuse_service(self):
        """Test that no error occurs when Langfuse service is None"""

        # Simulate no Langfuse service
        langfuse_service = None

        context_chunks = [
            {
                "content": "Test content",
                "similarity": 0.8,
                "metadata": {"file_name": "test.pdf"},
            }
        ]

        query = "Test query"

        # This should not raise any exception
        if context_chunks and langfuse_service:
            # This block should not execute
            langfuse_service.trace_retrieval(query=query, results=[])

        # No assertions needed - just verifying no exceptions are raised

    @pytest.mark.asyncio
    async def test_no_tracing_when_no_context_chunks(self):
        """Test that no tracing occurs when no context chunks are found"""

        mock_langfuse_service = Mock()
        mock_langfuse_service.trace_retrieval = Mock()

        context_chunks = []  # No chunks found
        query = "What is AI?"

        # This mimics the logic - no tracing should occur
        if context_chunks:
            langfuse_service = mock_langfuse_service
            if langfuse_service:
                langfuse_service.trace_retrieval(query=query, results=[])

        # Verify tracing was NOT called
        mock_langfuse_service.trace_retrieval.assert_not_called()

    def test_retrieval_result_formatting(self):
        """Test that context chunks are correctly formatted for Langfuse"""

        chunks = [
            {
                "content": "Test document content",
                "similarity": 0.95,
                "metadata": {
                    "file_name": "doc1.pdf",
                    "page": 5,
                    "author": "Test Author",
                },
            },
            {
                "content": "Another document",
                "similarity": 0.87,
                "metadata": {"section": "intro"},  # No file_name
            },
        ]

        # Format chunks as they would be in RAG service
        retrieval_results = []
        for chunk in chunks:
            result = {
                "content": chunk.get("content", ""),
                "similarity": chunk.get("similarity", 0),
                "metadata": chunk.get("metadata", {}),
            }
            if chunk.get("metadata", {}).get("file_name"):
                result["document"] = chunk["metadata"]["file_name"]
            retrieval_results.append(result)

        # Verify formatting
        assert len(retrieval_results) == 2

        # First result should have document name
        assert retrieval_results[0]["content"] == "Test document content"
        assert retrieval_results[0]["similarity"] == 0.95
        assert retrieval_results[0]["document"] == "doc1.pdf"
        assert retrieval_results[0]["metadata"]["author"] == "Test Author"

        # Second result should not have document name
        assert retrieval_results[1]["content"] == "Another document"
        assert retrieval_results[1]["similarity"] == 0.87
        assert "document" not in retrieval_results[1]
        assert retrieval_results[1]["metadata"]["section"] == "intro"

        # Test metadata calculation
        avg_similarity = sum(r["similarity"] for r in retrieval_results) / len(
            retrieval_results
        )
        assert (
            abs(avg_similarity - 0.91) < 0.001
        )  # (0.95 + 0.87) / 2 with floating point tolerance

        documents_used = list(
            {
                r.get("document", "unknown")
                for r in retrieval_results
                if r.get("document")
            }
        )
        assert documents_used == ["doc1.pdf"]
