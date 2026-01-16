"""Tests for services/contextual_retrieval_service.py"""

from unittest.mock import AsyncMock, Mock

import pytest

from services.contextual_retrieval_service import ContextualRetrievalService


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    mock = Mock()
    mock.get_response = AsyncMock(return_value="Test context for chunk")
    return mock


@pytest.fixture
def service(mock_llm_service):
    """Create ContextualRetrievalService instance."""
    return ContextualRetrievalService(mock_llm_service)


@pytest.mark.asyncio
async def test_add_context_to_chunks_empty_list(service):
    """Test adding context to empty chunks list."""
    result = await service.add_context_to_chunks([], {"file_name": "test.pdf"})

    assert result == []


@pytest.mark.asyncio
async def test_add_context_to_chunks_single_chunk(service, mock_llm_service):
    """Test adding context to a single chunk."""
    chunks = ["This is a test chunk"]
    metadata = {"file_name": "test.pdf"}

    mock_llm_service.get_response.return_value = "Context: Test document"

    result = await service.add_context_to_chunks(chunks, metadata)

    assert len(result) == 1
    assert "Context: Test document" in result[0]
    assert "This is a test chunk" in result[0]


@pytest.mark.asyncio
async def test_add_context_to_chunks_multiple_chunks(service, mock_llm_service):
    """Test adding context to multiple chunks."""
    chunks = ["Chunk 1", "Chunk 2", "Chunk 3"]
    metadata = {"file_name": "test.pdf"}

    mock_llm_service.get_response.return_value = "Context added"

    result = await service.add_context_to_chunks(chunks, metadata, batch_size=2)

    assert len(result) == 3
    for chunk in result:
        assert "Context added" in chunk or chunk in chunks


@pytest.mark.asyncio
async def test_add_context_to_chunks_handles_errors(service, mock_llm_service):
    """Test that errors in context generation don't break the pipeline."""
    chunks = ["Chunk 1", "Chunk 2"]
    metadata = {"file_name": "test.pdf"}

    # First call succeeds, second call fails
    mock_llm_service.get_response.side_effect = [
        "Context for chunk 1",
        Exception("API error"),
    ]

    result = await service.add_context_to_chunks(chunks, metadata)

    # Should return both chunks, second one without context
    assert len(result) == 2
    assert "Context for chunk 1" in result[0]
    # Second chunk should be original (fallback on error)
    assert result[1] == "Chunk 2"


@pytest.mark.asyncio
async def test_add_context_to_chunks_batch_processing(service, mock_llm_service):
    """Test that chunks are processed in batches."""
    chunks = [f"Chunk {i}" for i in range(15)]
    metadata = {"file_name": "test.pdf"}

    mock_llm_service.get_response.return_value = "Context"

    result = await service.add_context_to_chunks(chunks, metadata, batch_size=5)

    # All chunks should be processed
    assert len(result) == 15


@pytest.mark.asyncio
async def test_process_chunk_batch(service, mock_llm_service):
    """Test processing a batch of chunks."""
    chunk_batch = ["Chunk A", "Chunk B"]
    metadata = {"file_name": "test.pdf"}

    mock_llm_service.get_response.return_value = "Generated context"

    result = await service._process_chunk_batch(chunk_batch, metadata)

    assert len(result) == 2
    for chunk in result:
        assert "Generated context" in chunk


@pytest.mark.asyncio
async def test_generate_chunk_context(service, mock_llm_service):
    """Test generating context for a single chunk."""
    chunk = "This is test content about AI"
    metadata = {
        "file_name": "ai_guide.pdf",
        "doc_type": "documentation",
    }

    mock_llm_service.get_response.return_value = "Context: AI documentation chapter"

    result = await service._generate_chunk_context(chunk, metadata)

    assert result == "Context: AI documentation chapter"
    mock_llm_service.get_response.assert_called_once()


@pytest.mark.asyncio
async def test_generate_chunk_context_with_minimal_metadata(service, mock_llm_service):
    """Test generating context with minimal metadata."""
    chunk = "Content"
    metadata = {}  # Empty metadata

    mock_llm_service.get_response.return_value = "Generic context"

    result = await service._generate_chunk_context(chunk, metadata)

    assert result == "Generic context"


@pytest.mark.asyncio
async def test_add_context_empty_context_returned(service, mock_llm_service):
    """Test handling when LLM returns empty context."""
    chunks = ["Test chunk"]
    metadata = {"file_name": "test.pdf"}

    # Return empty string as context
    mock_llm_service.get_response.return_value = ""

    result = await service.add_context_to_chunks(chunks, metadata)

    # Should still include the original chunk
    assert len(result) == 1
    assert result[0] == "Test chunk"


@pytest.mark.asyncio
async def test_add_context_preserves_chunk_order(service, mock_llm_service):
    """Test that chunk order is preserved after adding context."""
    chunks = ["First", "Second", "Third"]
    metadata = {"file_name": "test.pdf"}

    # Return different context for each
    mock_llm_service.get_response.side_effect = ["Context 1", "Context 2", "Context 3"]

    result = await service.add_context_to_chunks(chunks, metadata)

    assert "First" in result[0]
    assert "Second" in result[1]
    assert "Third" in result[2]
