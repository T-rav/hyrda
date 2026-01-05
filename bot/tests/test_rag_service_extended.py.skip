"""
Extended tests for RAG Service - Error handling and edge cases.

These tests focus on untested code paths to increase coverage from 53% to 85%+.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from bot.tests.test_rag_service import (
    DocumentTestDataFactory,
    RAGServiceMockFactory,
    SettingsFactory,
)


class TestRAGServiceExtended:
    """Extended test cases for RAG service - error handling and edge cases"""

    @pytest.fixture
    def settings(self):
        """Create settings for testing"""
        return SettingsFactory.create_complete_rag_settings()

    @pytest.fixture
    def rag_service(self, settings):
        """Create RAG service for testing"""
        return RAGServiceMockFactory.create_service_with_mocks(settings)

    # ===========================================
    # Document Ingestion Error Handling
    # ===========================================

    @pytest.mark.asyncio
    async def test_ingest_documents_with_empty_content(self, rag_service):
        """Test ingestion skips documents with empty content"""
        # Arrange
        documents = [
            {"content": "", "metadata": {"file_name": "empty.txt"}},
            {"content": "   ", "metadata": {"file_name": "whitespace.txt"}},
            {"content": "Valid content", "metadata": {"file_name": "valid.txt"}},
        ]
        rag_service.embedding_provider.get_embedding = AsyncMock(
            return_value=[0.1, 0.2, 0.3]
        )
        rag_service.vector_store.add_documents = AsyncMock()

        # Act
        success_count, error_count = await rag_service.ingest_documents(documents)

        # Assert
        assert error_count == 2  # Two empty documents
        assert success_count == 1  # One valid document

    @pytest.mark.asyncio
    async def test_ingest_documents_embedding_failure(self, rag_service):
        """Test ingestion handles embedding generation failures"""
        # Arrange
        documents = [
            {"content": "Document 1", "metadata": {"file_name": "doc1.txt"}},
            {"content": "Document 2", "metadata": {"file_name": "doc2.txt"}},
        ]
        # First call succeeds, second fails
        rag_service.embedding_provider.get_embedding = AsyncMock(
            side_effect=[
                [0.1, 0.2, 0.3],  # Success
                Exception("API rate limit"),  # Failure
            ]
        )
        rag_service.vector_store.add_documents = AsyncMock()

        # Act
        success_count, error_count = await rag_service.ingest_documents(documents)

        # Assert
        assert success_count == 1
        assert error_count == 1

    @pytest.mark.asyncio
    async def test_ingest_documents_batch_processing_error(self, rag_service):
        """Test ingestion handles batch processing errors"""
        # Arrange
        documents = DocumentTestDataFactory.create_simple_documents(count=3)
        rag_service.embedding_provider.get_embedding = AsyncMock(
            return_value=[0.1, 0.2, 0.3]
        )
        # Vector store fails
        rag_service.vector_store.add_documents = AsyncMock(
            side_effect=Exception("Database connection lost")
        )

        # Act
        success_count, error_count = await rag_service.ingest_documents(documents)

        # Assert
        assert success_count == 0
        assert error_count == 3

    @pytest.mark.asyncio
    async def test_ingest_documents_without_vector_store(self, settings):
        """Test ingestion fails gracefully without vector store"""
        # Arrange
        rag_service = RAGServiceMockFactory.create_service_with_mocks(settings)
        rag_service.vector_store = None
        documents = DocumentTestDataFactory.create_simple_documents(count=1)

        # Act & Assert
        with pytest.raises(RuntimeError, match="Vector store not initialized"):
            await rag_service.ingest_documents(documents)

    # ===========================================
    # Conversation Context Management
    # ===========================================

    @pytest.mark.asyncio
    async def test_manage_conversation_context_with_summary(self, rag_service):
        """Test conversation context management stores summaries"""
        # Arrange
        conversation_history = [
            {"role": "user", "content": f"Message {i}"} for i in range(10)
        ]
        system_message = "You are a helpful assistant"
        session_id = "test-session-123"

        # Mock conversation cache
        mock_cache = AsyncMock()
        mock_cache.get_summary = AsyncMock(return_value=None)
        mock_cache.store_summary = AsyncMock()

        # Mock conversation manager to return summary
        rag_service.conversation_manager.manage_context = AsyncMock(
            return_value=(
                "You are a helpful assistant\n\n**Previous Conversation Summary:**\nUser discussed topics X, Y, Z.",
                [{"role": "user", "content": "Message 9"}],  # Compressed to 1 message
            )
        )

        # Act
        (
            managed_system,
            managed_history,
        ) = await rag_service._manage_conversation_context(
            conversation_history, system_message, session_id, mock_cache
        )

        # Assert
        assert "**Previous Conversation Summary:**" in managed_system
        assert len(managed_history) < len(conversation_history)
        mock_cache.store_summary.assert_called_once()
        # Verify summary was stored with correct parameters
        call_args = mock_cache.store_summary.call_args
        assert call_args[1]["thread_ts"] == session_id
        assert call_args[1]["message_count"] == 1
        assert call_args[1]["compressed_from"] == 10

    @pytest.mark.asyncio
    async def test_manage_conversation_context_without_cache(self, rag_service):
        """Test conversation context management without cache"""
        # Arrange
        conversation_history = [{"role": "user", "content": "Message"}]
        system_message = "System prompt"

        rag_service.conversation_manager.manage_context = AsyncMock(
            return_value=(system_message, conversation_history)
        )

        # Act
        (
            managed_system,
            managed_history,
        ) = await rag_service._manage_conversation_context(
            conversation_history, system_message, None, None
        )

        # Assert
        assert managed_system == system_message
        assert managed_history == conversation_history

    # ===========================================
    # Retrieval and Logging
    # ===========================================

    @pytest.mark.asyncio
    async def test_retrieve_and_log_context_with_metrics(self, rag_service):
        """Test context retrieval logs metrics correctly"""
        # Arrange
        query = "test query"
        context_chunks = [
            {
                "content": "Test content",
                "similarity": 0.85,
                "metadata": {
                    "file_name": "test.pdf",
                    "file_type": "pdf",
                    "source": "vector_db",
                },
            }
        ]
        rag_service.retrieval_service.retrieve_context = AsyncMock(
            return_value=context_chunks
        )

        # Mock metrics service
        with patch("services.metrics_service.get_metrics_service") as mock_metrics:
            mock_metrics_instance = Mock()
            mock_metrics.return_value = mock_metrics_instance
            mock_metrics_instance.record_rag_query_result = Mock()
            mock_metrics_instance.record_document_usage = Mock()

            # Act
            result = await rag_service._retrieve_and_log_context(
                query, [], user_id="U123"
            )

            # Assert
            assert result == context_chunks
            mock_metrics_instance.record_rag_query_result.assert_called_once()
            mock_metrics_instance.record_document_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_and_log_context_no_results(self, rag_service):
        """Test context retrieval logs miss when no results found"""
        # Arrange
        query = "test query"
        rag_service.retrieval_service.retrieve_context = AsyncMock(return_value=[])

        # Mock metrics service
        with patch("services.metrics_service.get_metrics_service") as mock_metrics:
            mock_metrics_instance = Mock()
            mock_metrics.return_value = mock_metrics_instance
            mock_metrics_instance.record_rag_query_result = Mock()

            # Act
            result = await rag_service._retrieve_and_log_context(
                query, [], user_id="U123"
            )

            # Assert
            assert result == []
            # Verify miss was logged
            call_args = mock_metrics_instance.record_rag_query_result.call_args
            assert call_args[1]["result_type"] == "miss"

    @pytest.mark.asyncio
    async def test_log_retrieval_metrics_with_langfuse(self, rag_service):
        """Test retrieval metrics are logged to Langfuse"""
        # Arrange
        query = "test query"
        context_chunks = [
            {
                "content": "Content 1",
                "similarity": 0.9,
                "metadata": {"file_name": "doc1.pdf", "file_type": "pdf"},
            },
            {
                "content": "Content 2",
                "similarity": 0.8,
                "metadata": {"file_name": "doc2.pdf", "file_type": "pdf"},
            },
        ]

        # Mock Langfuse service
        with patch("bot.services.rag_service.get_langfuse_service") as mock_langfuse:
            mock_langfuse_instance = Mock()
            mock_langfuse.return_value = mock_langfuse_instance
            mock_langfuse_instance.trace_retrieval = Mock()

            # Act
            await rag_service._log_retrieval_metrics(query, context_chunks)

            # Assert
            mock_langfuse_instance.trace_retrieval.assert_called_once()
            call_args = mock_langfuse_instance.trace_retrieval.call_args
            assert call_args[1]["query"] == query
            assert len(call_args[1]["results"]) == 2

    # ===========================================
    # Document Context Management
    # ===========================================

    @pytest.mark.asyncio
    async def test_add_document_to_context(self, rag_service):
        """Test uploaded document is added to context with correct structure"""
        # Arrange
        document_content = "This is a test document with some content"
        document_filename = "test.pdf"
        existing_context = [
            {
                "content": "Existing chunk",
                "similarity": 0.7,
                "metadata": {"file_name": "existing.pdf"},
            }
        ]

        # Mock chunk_text
        with patch("services.embedding.chunk_text") as mock_chunk:
            mock_chunk.return_value = ["Chunk 1", "Chunk 2"]

            # Act
            result = rag_service._add_document_to_context(
                document_content, document_filename, existing_context
            )

            # Assert
            assert len(result) == 3  # 2 new chunks + 1 existing
            # Document chunks should be first (highest priority)
            assert result[0]["metadata"]["source"] == "uploaded_document"
            assert result[0]["similarity"] == 1.0
            assert result[1]["metadata"]["source"] == "uploaded_document"
            assert result[1]["similarity"] == 1.0
            # Existing context should be after
            assert result[2]["metadata"]["file_name"] == "existing.pdf"

    @pytest.mark.asyncio
    async def test_add_document_to_context_no_filename(self, rag_service):
        """Test uploaded document without filename gets default name"""
        # Arrange
        with patch("services.embedding.chunk_text") as mock_chunk:
            mock_chunk.return_value = ["Test chunk"]

            # Act
            result = rag_service._add_document_to_context("Content", None, [])

            # Assert
            assert result[0]["metadata"]["file_name"] == "uploaded_document"

    # ===========================================
    # Web Search Tool Configuration
    # ===========================================

    @pytest.mark.asyncio
    async def test_get_web_search_tools_with_rag_enabled(self, rag_service):
        """Test web search tools are available when RAG is enabled"""
        # Arrange
        with patch("bot.services.rag_service.get_tavily_client") as mock_tavily:
            mock_tavily.return_value = Mock()  # Tavily available

            with patch("services.search_clients.get_tool_definitions") as mock_tools:
                mock_tools.return_value = [
                    {"type": "function", "function": {"name": "web_search"}}
                ]

                # Act
                tools = rag_service._get_web_search_tools(use_rag=True)

                # Assert
                assert tools is not None
                assert len(tools) == 1
                mock_tools.assert_called_once_with(include_deep_research=False)

    @pytest.mark.asyncio
    async def test_get_web_search_tools_with_rag_disabled(self, rag_service):
        """Test web search tools are disabled when RAG is disabled"""
        # Arrange
        with patch("bot.services.rag_service.get_tavily_client") as mock_tavily:
            mock_tavily.return_value = Mock()  # Tavily available

            # Act
            tools = rag_service._get_web_search_tools(use_rag=False)

            # Assert
            assert tools is None

    @pytest.mark.asyncio
    async def test_get_web_search_tools_no_tavily_client(self, rag_service):
        """Test web search tools return None when Tavily not available"""
        # Arrange
        with patch("bot.services.rag_service.get_tavily_client") as mock_tavily:
            mock_tavily.return_value = None  # No Tavily client

            # Act
            tools = rag_service._get_web_search_tools(use_rag=True)

            # Assert
            assert tools is None

    # ===========================================
    # Response Generation Edge Cases
    # ===========================================

    @pytest.mark.asyncio
    async def test_generate_response_empty_llm_response(self, rag_service):
        """Test generate_response handles empty LLM response"""
        # Arrange
        rag_service.retrieval_service.retrieve_context = AsyncMock(return_value=[])
        rag_service.context_builder.build_rag_prompt = Mock(
            return_value=("system", [{"role": "user", "content": "query"}])
        )
        rag_service.llm_provider.get_response = AsyncMock(return_value="")
        rag_service.conversation_manager.manage_context = AsyncMock(
            return_value=(None, [])
        )

        # Act
        response = await rag_service.generate_response("query", [])

        # Assert
        assert response == "I'm sorry, I couldn't generate a response right now."

    @pytest.mark.asyncio
    async def test_generate_response_llm_error(self, rag_service):
        """Test generate_response handles LLM errors gracefully"""
        # Arrange
        rag_service.retrieval_service.retrieve_context = AsyncMock(return_value=[])
        rag_service.context_builder.build_rag_prompt = Mock(
            return_value=("system", [{"role": "user", "content": "query"}])
        )
        rag_service.llm_provider.get_response = AsyncMock(
            side_effect=Exception("API error")
        )
        rag_service.conversation_manager.manage_context = AsyncMock(
            return_value=(None, [])
        )

        # Act
        response = await rag_service.generate_response("query", [])

        # Assert
        assert "error" in response.lower()

    @pytest.mark.asyncio
    async def test_generate_response_with_dict_response(self, rag_service):
        """Test generate_response extracts content from dict response"""
        # Arrange
        rag_service.retrieval_service.retrieve_context = AsyncMock(return_value=[])
        rag_service.context_builder.build_rag_prompt = Mock(
            return_value=("system", [{"role": "user", "content": "query"}])
        )
        rag_service.llm_provider.get_response = AsyncMock(
            return_value={"content": "Response from dict", "metadata": "extra"}
        )
        rag_service.conversation_manager.manage_context = AsyncMock(
            return_value=(None, [])
        )

        # Act
        response = await rag_service.generate_response("query", [], use_rag=False)

        # Assert
        assert response == "Response from dict"

    # ===========================================
    # Tool Execution Tests
    # ===========================================

    @pytest.mark.asyncio
    async def test_execute_web_search_success(self, rag_service):
        """Test successful web search execution"""
        # Arrange
        tool_args = {"query": "test query", "max_results": 5}
        tool_id = "tool-123"

        mock_tavily = Mock()
        mock_tavily.search = AsyncMock(
            return_value=[
                {
                    "title": "Result 1",
                    "url": "https://example.com/1",
                    "snippet": "Snippet 1",
                },
                {
                    "title": "Result 2",
                    "url": "https://example.com/2",
                    "snippet": "Snippet 2",
                },
            ]
        )

        with patch(
            "bot.services.rag_service.get_tavily_client", return_value=mock_tavily
        ):
            # Act
            result = await rag_service._execute_web_search(
                tool_args, tool_id, "session-123", "user-456"
            )

            # Assert
            assert result["tool_call_id"] == tool_id
            assert result["role"] == "tool"
            assert result["name"] == "web_search"
            assert "Result 1" in result["content"]
            assert "Result 2" in result["content"]

    @pytest.mark.asyncio
    async def test_execute_url_scrape_success(self, rag_service):
        """Test successful URL scraping"""
        # Arrange
        tool_args = {"url": "https://example.com"}
        tool_id = "tool-456"

        mock_tavily = Mock()
        mock_tavily.scrape_url = AsyncMock(
            return_value={
                "success": True,
                "content": "Scraped content from the webpage",
                "title": "Example Page",
            }
        )

        with patch(
            "bot.services.rag_service.get_tavily_client", return_value=mock_tavily
        ):
            # Act
            result = await rag_service._execute_url_scrape(
                tool_args, tool_id, "session-123", "user-456"
            )

            # Assert
            assert result["tool_call_id"] == tool_id
            assert result["name"] == "scrape_url"
            assert "Example Page" in result["content"]
            assert "Scraped content" in result["content"]

    @pytest.mark.asyncio
    async def test_execute_url_scrape_failure(self, rag_service):
        """Test URL scraping handles failures"""
        # Arrange
        tool_args = {"url": "https://example.com"}
        tool_id = "tool-789"

        mock_tavily = Mock()
        mock_tavily.scrape_url = AsyncMock(
            return_value={"success": False, "error": "Page not found"}
        )

        with patch(
            "bot.services.rag_service.get_tavily_client", return_value=mock_tavily
        ):
            # Act
            result = await rag_service._execute_url_scrape(
                tool_args, tool_id, "session-123", "user-456"
            )

            # Assert
            assert "Failed to scrape URL" in result["content"]
            assert "Page not found" in result["content"]

    @pytest.mark.asyncio
    async def test_execute_deep_research_success(self, rag_service):
        """Test successful deep research execution"""
        # Arrange
        tool_args = {"query": "research topic"}
        tool_id = "tool-research-1"

        mock_perplexity = Mock()
        mock_perplexity.deep_research = AsyncMock(
            return_value={
                "success": True,
                "answer": "Detailed research answer",
                "sources": [
                    {"url": "https://source1.com", "title": "Source 1"},
                    {"url": "https://source2.com", "title": "Source 2"},
                ],
            }
        )

        with patch(
            "bot.services.rag_service.get_perplexity_client",
            return_value=mock_perplexity,
        ):
            # Act
            result = await rag_service._execute_deep_research(
                tool_args, tool_id, "session-123", "user-456"
            )

            # Assert
            assert result["tool_call_id"] == tool_id
            assert result["name"] == "deep_research"
            assert "Detailed research answer" in result["content"]
            assert "Source 1" in result["content"]

    @pytest.mark.asyncio
    async def test_execute_deep_research_no_client(self, rag_service):
        """Test deep research handles missing Perplexity client"""
        # Arrange
        tool_args = {"query": "research topic"}
        tool_id = "tool-research-2"

        with patch("bot.services.rag_service.get_perplexity_client", return_value=None):
            # Act
            result = await rag_service._execute_deep_research(
                tool_args, tool_id, "session-123", "user-456"
            )

            # Assert
            assert "not available" in result["content"]
            assert "not configured" in result["content"]

    @pytest.mark.asyncio
    async def test_execute_deep_research_failure(self, rag_service):
        """Test deep research handles API failures"""
        # Arrange
        tool_args = {"query": "research topic"}
        tool_id = "tool-research-3"

        mock_perplexity = Mock()
        mock_perplexity.deep_research = AsyncMock(
            return_value={"success": False, "error": "API rate limit exceeded"}
        )

        with patch(
            "bot.services.rag_service.get_perplexity_client",
            return_value=mock_perplexity,
        ):
            # Act
            result = await rag_service._execute_deep_research(
                tool_args, tool_id, "session-123", "user-456"
            )

            # Assert
            assert "Failed to perform deep research" in result["content"]
            assert "rate limit" in result["content"]

    # ===========================================
    # Tool Call Handling
    # ===========================================

    @pytest.mark.asyncio
    async def test_handle_tool_calls_no_tavily_client(self, rag_service):
        """Test tool call handling when Tavily client is unavailable"""
        # Arrange
        tool_call_response = {
            "content": "Initial response",
            "tool_calls": [
                {
                    "id": "call-1",
                    "function": {"name": "web_search", "arguments": {"query": "test"}},
                }
            ],
        }

        with patch("bot.services.rag_service.get_tavily_client", return_value=None):
            # Act
            result = await rag_service._handle_tool_calls(
                tool_call_response, [], None, None, None, None
            )

            # Assert
            assert result == "Initial response"

    @pytest.mark.asyncio
    async def test_handle_tool_calls_unknown_tool(self, rag_service):
        """Test tool call handling with unknown tool name"""
        # Arrange
        tool_call_response = {
            "content": "Initial response",
            "tool_calls": [
                {
                    "id": "call-1",
                    "function": {"name": "unknown_tool", "arguments": {}},
                }
            ],
        }

        mock_tavily = Mock()
        rag_service.llm_provider.get_response = AsyncMock(
            return_value="Final response after unknown tool"
        )

        with patch(
            "bot.services.rag_service.get_tavily_client", return_value=mock_tavily
        ):
            # Act
            result = await rag_service._handle_tool_calls(
                tool_call_response, [], "system", "session-1", "user-1", []
            )

            # Assert
            assert result == "Final response after unknown tool"
            rag_service.llm_provider.get_response.assert_called()

    @pytest.mark.asyncio
    async def test_handle_tool_calls_execution_error(self, rag_service):
        """Test tool call handling when tool execution raises exception"""
        # Arrange
        tool_call_response = {
            "content": "Initial response",
            "tool_calls": [
                {
                    "id": "call-1",
                    "function": {"name": "web_search", "arguments": {"query": "test"}},
                }
            ],
        }

        mock_tavily = Mock()
        mock_tavily.search = AsyncMock(side_effect=Exception("Network error"))

        rag_service.llm_provider.get_response = AsyncMock(
            return_value="Response after error handling"
        )

        with patch(
            "bot.services.rag_service.get_tavily_client", return_value=mock_tavily
        ):
            # Act
            result = await rag_service._handle_tool_calls(
                tool_call_response, [], "system", "session-1", "user-1", []
            )

            # Assert
            assert result == "Response after error handling"
            # LLM should still be called with error message
            rag_service.llm_provider.get_response.assert_called()

    @pytest.mark.asyncio
    async def test_handle_tool_calls_multiple_tools(self, rag_service):
        """Test handling multiple tool calls in sequence"""
        # Arrange
        tool_call_response = {
            "content": "Initial response",
            "tool_calls": [
                {
                    "id": "call-1",
                    "function": {"name": "web_search", "arguments": {"query": "test1"}},
                },
                {
                    "id": "call-2",
                    "function": {
                        "name": "scrape_url",
                        "arguments": {"url": "https://example.com"},
                    },
                },
            ],
        }

        mock_tavily = Mock()
        mock_tavily.search = AsyncMock(
            return_value=[
                {"title": "Result", "url": "https://test.com", "snippet": "Test"}
            ]
        )
        mock_tavily.scrape_url = AsyncMock(
            return_value={"success": True, "content": "Scraped", "title": "Page"}
        )

        rag_service.llm_provider.get_response = AsyncMock(
            return_value="Final response with all tools"
        )

        with patch(
            "bot.services.rag_service.get_tavily_client", return_value=mock_tavily
        ):
            # Act
            result = await rag_service._handle_tool_calls(
                tool_call_response, [], "system", "session-1", "user-1", []
            )

            # Assert
            assert result == "Final response with all tools"
            mock_tavily.search.assert_called_once()
            mock_tavily.scrape_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_prepare_tool_messages(self, rag_service):
        """Test preparation of messages with tool calls and results"""
        # Arrange
        tool_call_response = {
            "content": "Calling tools",
            "tool_calls": [
                {
                    "id": "call-1",
                    "function": {
                        "name": "web_search",
                        "arguments": {"query": "test"},  # Dict format
                    },
                }
            ],
        }
        messages = [{"role": "user", "content": "Search for something"}]
        tool_results = [
            {
                "tool_call_id": "call-1",
                "role": "tool",
                "name": "web_search",
                "content": "Search results",
            }
        ]

        # Act
        result = rag_service._prepare_tool_messages(
            tool_call_response, messages, tool_results
        )

        # Assert
        assert len(result) == 3  # Original message + assistant + tool result
        assert result[1]["role"] == "assistant"
        assert (
            result[1]["tool_calls"][0]["function"]["arguments"] == '{"query": "test"}'
        )
        assert result[2]["role"] == "tool"

    # ===========================================
    # System Status Tests
    # ===========================================

    @pytest.mark.asyncio
    async def test_get_system_status_vector_store_healthy(self, rag_service):
        """Test system status reports healthy vector store"""
        # Arrange
        rag_service.vector_store.search = AsyncMock(return_value=[])

        # Act
        status = await rag_service.get_system_status()

        # Assert
        assert status["vector_enabled"] is True
        assert status["vector_store_status"] == "healthy"
        assert "services" in status

    @pytest.mark.asyncio
    async def test_get_system_status_vector_store_error(self, rag_service):
        """Test system status reports vector store errors"""
        # Arrange
        rag_service.vector_store.search = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        # Act
        status = await rag_service.get_system_status()

        # Assert
        assert status["vector_enabled"] is True
        assert "error" in status["vector_store_status"]
        assert "Connection refused" in status["vector_store_status"]

    # ===========================================
    # Citation Integration Tests
    # ===========================================

    @pytest.mark.asyncio
    async def test_generate_response_with_citations(self, rag_service):
        """Test citations are added when RAG is used"""
        # Arrange
        context_chunks = [
            {
                "content": "Context from document",
                "similarity": 0.9,
                "metadata": {"file_name": "source.pdf"},
            }
        ]
        rag_service.retrieval_service.retrieve_context = AsyncMock(
            return_value=context_chunks
        )
        rag_service.context_builder.build_rag_prompt = Mock(
            return_value=("system", [{"role": "user", "content": "query"}])
        )
        rag_service.llm_provider.get_response = AsyncMock(
            return_value="Response based on context"
        )
        rag_service.citation_service.add_source_citations = Mock(
            return_value="Response based on context\n\nSources:\n- source.pdf"
        )
        rag_service.conversation_manager.manage_context = AsyncMock(
            return_value=(None, [])
        )

        # Act
        response = await rag_service.generate_response("query", [], use_rag=True)

        # Assert
        assert "Sources:" in response
        rag_service.citation_service.add_source_citations.assert_called_once_with(
            "Response based on context", context_chunks
        )

    @pytest.mark.asyncio
    async def test_generate_response_no_citations_when_rag_disabled(self, rag_service):
        """Test citations are not added when RAG is disabled"""
        # Arrange
        rag_service.context_builder.build_rag_prompt = Mock(
            return_value=("system", [{"role": "user", "content": "query"}])
        )
        rag_service.llm_provider.get_response = AsyncMock(
            return_value="Direct response without context"
        )
        rag_service.conversation_manager.manage_context = AsyncMock(
            return_value=(None, [])
        )

        # Mock citation service
        rag_service.citation_service = Mock()
        rag_service.citation_service.add_source_citations = Mock()

        # Act
        response = await rag_service.generate_response("query", [], use_rag=False)

        # Assert
        assert response == "Direct response without context"
        rag_service.citation_service.add_source_citations.assert_not_called()

    # ===========================================
    # End-to-End Integration Tests
    # ===========================================

    @pytest.mark.asyncio
    async def test_generate_response_with_tool_calls_end_to_end(self, rag_service):
        """Test generate_response handles tool calls end-to-end"""
        # Arrange
        rag_service.retrieval_service.retrieve_context = AsyncMock(return_value=[])
        rag_service.context_builder.build_rag_prompt = Mock(
            return_value=(
                "system",
                [{"role": "user", "content": "search for something"}],
            )
        )
        rag_service.conversation_manager.manage_context = AsyncMock(
            return_value=(None, [])
        )

        # First call returns tool calls, second call returns final response
        rag_service.llm_provider.get_response = AsyncMock(
            side_effect=[
                {
                    "content": "I'll search for that",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "function": {
                                "name": "web_search",
                                "arguments": {"query": "test"},
                            },
                        }
                    ],
                },
                "Here are the search results I found",
            ]
        )

        mock_tavily = Mock()
        mock_tavily.search = AsyncMock(
            return_value=[
                {"title": "Result", "url": "https://test.com", "snippet": "Info"}
            ]
        )

        with (
            patch(
                "bot.services.rag_service.get_tavily_client", return_value=mock_tavily
            ),
            patch(
                "services.search_clients.get_tool_definitions",
                return_value=[{"type": "function"}],
            ),
        ):
            # Act
            response = await rag_service.generate_response(
                "search for something",
                [],
                use_rag=True,
            )

            # Assert
            assert response == "Here are the search results I found"
            assert rag_service.llm_provider.get_response.call_count == 2
