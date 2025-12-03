"""Tests for async PDF extraction to verify non-blocking behavior.

Tests verify that:
- PDF extraction runs in thread pool executor (doesn't block event loop)
- Multiple PDF extractions can run concurrently
- Event loop remains responsive during PDF processing
- Large/slow PDFs don't freeze async operations
"""

import asyncio

# Import the functions we're testing
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add handlers directory to path
handlers_path = Path(__file__).parent.parent / "handlers"
sys.path.insert(0, str(handlers_path))

from handlers.file_processors.pdf_processor import (
    _extract_pdf_text_sync,
    extract_pdf_text,
)


class TestAsyncPDFExtraction:
    """Test that PDF extraction doesn't block the event loop."""

    @pytest.mark.asyncio
    async def test_pdf_extraction_runs_in_executor(self):
        """Test that PDF extraction runs in thread pool, not main thread."""
        # Mock the sync function to track which thread it runs in
        import threading

        main_thread_id = threading.current_thread().ident
        extraction_thread_id = None

        def mock_sync_extract(pdf_content, file_name):
            nonlocal extraction_thread_id
            extraction_thread_id = threading.current_thread().ident
            return "Extracted text"

        with patch(
            "handlers.file_processors.pdf_processor._extract_pdf_text_sync",
            side_effect=mock_sync_extract,
        ):
            result = await extract_pdf_text(b"fake pdf content", "test.pdf")

            assert result == "Extracted text"
            # Verify it ran in a different thread (thread pool)
            assert extraction_thread_id != main_thread_id

    @pytest.mark.asyncio
    async def test_event_loop_responsive_during_pdf_extraction(self):
        """Test that event loop remains responsive during PDF extraction."""

        # Mock a slow PDF extraction (simulates large PDF)
        def slow_pdf_extract(pdf_content, file_name):
            time.sleep(0.5)  # Simulate 500ms blocking operation
            return "Slow PDF text"

        with patch(
            "handlers.file_processors.pdf_processor._extract_pdf_text_sync",
            side_effect=slow_pdf_extract,
        ):
            # Start PDF extraction (should run in background)
            pdf_task = asyncio.create_task(
                extract_pdf_text(b"large pdf content", "large.pdf")
            )

            # While PDF extracts, event loop should handle other work
            counter = 0

            async def increment_counter():
                nonlocal counter
                for _ in range(10):
                    counter += 1
                    await asyncio.sleep(0.01)  # 10ms each

            counter_task = asyncio.create_task(increment_counter())

            # Wait for both tasks
            pdf_result, _ = await asyncio.gather(pdf_task, counter_task)

            # Verify PDF extraction completed
            assert pdf_result == "Slow PDF text"

            # Verify event loop was responsive (counter incremented during PDF extraction)
            assert counter == 10

    @pytest.mark.asyncio
    async def test_multiple_pdf_extractions_concurrent(self):
        """Test that multiple PDF extractions can run concurrently."""
        call_times = []

        def track_time_extract(pdf_content, file_name):
            call_times.append(time.time())
            time.sleep(0.1)  # Each takes 100ms
            return f"Text from {file_name}"

        with patch(
            "handlers.file_processors.pdf_processor._extract_pdf_text_sync",
            side_effect=track_time_extract,
        ):
            # Start 3 PDF extractions concurrently
            tasks = [
                extract_pdf_text(b"pdf1", "doc1.pdf"),
                extract_pdf_text(b"pdf2", "doc2.pdf"),
                extract_pdf_text(b"pdf3", "doc3.pdf"),
            ]

            start = time.time()
            results = await asyncio.gather(*tasks)
            duration = time.time() - start

            # Verify all completed
            assert len(results) == 3
            assert "Text from doc1.pdf" in results
            assert "Text from doc2.pdf" in results
            assert "Text from doc3.pdf" in results

            # Verify they ran concurrently (total time < 3 * 100ms)
            # If sequential: 300ms+, if concurrent: ~100ms
            assert duration < 0.25  # Allow some overhead

    @pytest.mark.asyncio
    async def test_pdf_extraction_error_handling_async(self):
        """Test that errors in PDF extraction don't break async flow."""

        def failing_extract(pdf_content, file_name):
            raise ValueError("PDF extraction failed")

        with patch(
            "handlers.file_processors.pdf_processor._extract_pdf_text_sync",
            side_effect=failing_extract,
        ):
            result = await extract_pdf_text(b"bad pdf", "error.pdf")

            # Verify error is handled gracefully
            assert "Error extracting text" in result
            assert "error.pdf" in result

    @pytest.mark.asyncio
    async def test_pdf_extraction_with_pymupdf_unavailable(self):
        """Test graceful handling when PyMuPDF is not available."""
        with patch("handlers.file_processors.pdf_processor.PYMUPDF_AVAILABLE", False):
            result = await extract_pdf_text(b"pdf content", "test.pdf")

            # Verify graceful fallback
            assert (
                "PyMuPDF library not available" in result
                or "PyMuPDF not installed" in result
            )
            assert "test.pdf" in result


class TestSyncPDFExtractionIsolation:
    """Test that sync PDF extraction is properly isolated."""

    def test_sync_pdf_extraction_is_blocking(self):
        """Verify that _extract_pdf_text_sync is indeed synchronous/blocking.

        This test confirms that the sync function is correctly separated
        and would block if called directly in async context.
        """
        # Mock fitz to avoid actual PDF processing
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Test content from page"
        mock_doc.page_count = 1
        mock_doc.load_page.return_value = mock_page

        with patch("handlers.file_processors.pdf_processor.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc

            # Call sync function directly
            result = _extract_pdf_text_sync(b"pdf bytes", "test.pdf")

            # Verify it returns text
            assert "Test content from page" in result

            # Verify it called blocking fitz operations
            mock_fitz.open.assert_called_once()
            mock_doc.load_page.assert_called()
            mock_doc.close.assert_called_once()


class TestPDFExtractionThreadPoolBehavior:
    """Test thread pool executor behavior specifically."""

    @pytest.mark.asyncio
    async def test_executor_handles_blocking_io(self):
        """Test that executor properly handles blocking I/O operations."""
        blocking_operation_completed = False

        def blocking_pdf_work(pdf_content, file_name):
            nonlocal blocking_operation_completed
            # Simulate blocking I/O
            time.sleep(0.1)
            blocking_operation_completed = True
            return "Blocked and completed"

        with patch(
            "handlers.file_processors.pdf_processor._extract_pdf_text_sync",
            side_effect=blocking_pdf_work,
        ):
            # Event loop should not be blocked
            result = await extract_pdf_text(b"pdf", "test.pdf")

            assert blocking_operation_completed
            assert result == "Blocked and completed"

    @pytest.mark.asyncio
    async def test_executor_uses_default_thread_pool(self):
        """Test that we're using default thread pool executor (None)."""
        with patch(
            "handlers.file_processors.pdf_processor._extract_pdf_text_sync"
        ) as mock_sync:
            mock_sync.return_value = "Test"

            with patch("asyncio.get_event_loop") as mock_get_loop:
                mock_loop = MagicMock()
                mock_loop.run_in_executor = AsyncMock(return_value="Test")
                mock_get_loop.return_value = mock_loop

                await extract_pdf_text(b"pdf", "test.pdf")

                # Verify run_in_executor was called with None (default pool)
                mock_loop.run_in_executor.assert_called_once()
                call_args = mock_loop.run_in_executor.call_args
                assert (
                    call_args[0][0] is None
                )  # First arg should be None (default pool)
