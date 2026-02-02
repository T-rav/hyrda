"""PDF document processing for bot message handlers."""

import logging

from handlers.constants import CHUNK_OVERLAP_CHARS, MAX_EMBEDDING_CHARS

try:
    import fitz  # PyMuPDF  # type: ignore[reportMissingImports]

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False  # type: ignore[reportConstantRedefinition]

logger = logging.getLogger(__name__)


def _extract_pdf_text_sync(pdf_content: bytes, file_name: str) -> str:
    """Synchronous PDF extraction (runs in thread pool)."""
    from services.embedding import chunk_text

    pdf_document = fitz.open(stream=pdf_content, filetype="pdf")
    text_content = ""

    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        page_text = page.get_text()  # type: ignore[attr-defined]
        if page_text.strip():
            text_content += f"\n\n--- Page {page_num + 1} ---\n{page_text}"

    pdf_document.close()

    if text_content.strip():
        full_text = text_content.strip()

        if len(full_text) > MAX_EMBEDDING_CHARS:
            logger.info(
                f"PDF content is {len(full_text)} chars, chunking for embedding compatibility"
            )
            chunks = chunk_text(
                full_text,
                chunk_size=MAX_EMBEDDING_CHARS,
                chunk_overlap=CHUNK_OVERLAP_CHARS,
            )
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
    """Extract text from PDF using PyMuPDF without blocking the event loop."""
    if not PYMUPDF_AVAILABLE:
        logger.warning("PyMuPDF not available - cannot extract PDF text")
        return f"[PDF file: {file_name} - PyMuPDF not installed]"

    try:
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, _extract_pdf_text_sync, pdf_content, file_name
        )
    except Exception as e:
        logger.error(f"Error extracting text from PDF {file_name}: {e}")
        return f"[PDF file: {file_name} - Error extracting text: {str(e)}]"
