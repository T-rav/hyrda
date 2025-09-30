"""
Utility functions for embedding operations
"""


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    separators: list[str] | None = None,
) -> list[str]:
    """
    Split text into overlapping chunks for embedding

    Args:
        text: Text to chunk
        chunk_size: Maximum size of each chunk
        chunk_overlap: Number of characters to overlap between chunks
        separators: List of separators to try (in order of preference)

    Returns:
        List of text chunks
    """
    # Clean text by normalizing line endings and removing excessive whitespace
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = " ".join(text.split())  # Normalize whitespace

    if separators is None:
        separators = ["\n\n", "\n", ". ", " ", ""]

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            # Last chunk
            chunks.append(text[start:])
            break

        # Try to find a good break point
        best_end = end
        for separator in separators:
            if separator == "":
                break

            # Look for separator within the overlap region
            search_start = max(end - chunk_overlap, start)
            separator_pos = text.rfind(separator, search_start, end)

            if separator_pos > start:
                best_end = separator_pos + len(separator)
                break

        chunks.append(text[start:best_end])

        # Calculate next start position with overlap
        start = best_end - chunk_overlap
        start = max(start, best_end)  # Ensure we always make progress

    return [chunk.strip() for chunk in chunks if chunk.strip()]
