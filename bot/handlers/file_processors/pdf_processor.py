"""PDF document processing for bot message handlers.

Handles PDF text extraction with async support to avoid blocking the event loop.
"""

import logging

try:
    import fitz  # PyMuPDF  # type: ignore[reportMissingImports]

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False  # type: ignore[reportConstantRedefinition]

logger = logging.getLogger(__name__)


def _extract_pdf_text_sync(pdf_content: bytes, file_name: str) -> str:
    """Synchronous PDF extraction (called via run_in_executor to avoid blocking).

    This function performs blocking I/O operations and should only be called
    from extract_pdf_text() which runs it in a thread pool executor.

    Args:
        pdf_content: PDF file content as bytes
        file_name: Name of the PDF file for logging

    Returns:
        Extracted text content from the PDF
    """
    from services.embedding import chunk_text

    # Open PDF from bytes - BLOCKING I/O
    pdf_document = fitz.open(stream=pdf_content, filetype="pdf")
    text_content = ""

    # Iterate through pages - BLOCKING I/O
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        page_text = page.get_text()  # type: ignore[attr-defined]
        if page_text.strip():
            text_content += f"\n\n--- Page {page_num + 1} ---\n{page_text}"

    pdf_document.close()

    if text_content.strip():
        full_text = text_content.strip()

        # If content is too long, chunk it to prevent embedding failures
        # Conservative limit: 6000 chars ≈ 1500 tokens (well under 8192 limit)
        if len(full_text) > 6000:
            logger.info(
                f"PDF content is {len(full_text)} chars, chunking for embedding compatibility"
            )
            chunks = chunk_text(full_text, chunk_size=6000, chunk_overlap=200)
            # Return first chunk with indicator
            chunked_content = chunks[0]
            if len(chunks) > 1:
                chunked_content += (
                    f"\n\n[Note: This is chunk 1 of {len(chunks)} from {file_name}]"
                )
            return chunked_content
        else:
            return full_text
    else:
        return f"[PDF file: {file_name} - No extractable text content found]"


async def extract_pdf_text(pdf_content: bytes, file_name: str) -> str:
    """Extract text from PDF using PyMuPDF without blocking the event loop.

    Runs the blocking PDF extraction in a thread pool executor to prevent
    large PDFs from freezing the async message handler.

    Args:
        pdf_content: PDF file content as bytes
        file_name: Name of the PDF file

    Returns:
        Extracted text content
    """
    if not PYMUPDF_AVAILABLE:
        logger.warning("PyMuPDF not available - cannot extract PDF text")
        return f"[PDF file: {file_name} - PyMuPDF not installed]"

    try:
        # Run blocking PDF extraction in thread pool to avoid blocking event loop
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, _extract_pdf_text_sync, pdf_content, file_name
        )
    except Exception as e:
        logger.error(f"Error extracting text from PDF {file_name}: {e}")
        return f"[PDF file: {file_name} - Error extracting text: {str(e)}]"
