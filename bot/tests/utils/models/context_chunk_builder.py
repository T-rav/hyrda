"""
ContextChunkBuilder for test utilities
"""

from typing import Any


class ContextChunkBuilder:
    """Builder for creating context chunks with metadata"""

    def __init__(self):
        self._content = "Default content"
        self._metadata = {}
        self._similarity = 0.85
        self._chunk_id = "chunk-1"
        self._document_id = "doc-1"

    def with_content(self, content: str):
        """Set chunk content"""
        self._content = content
        return self

    def with_similarity(self, similarity: float):
        """Set similarity score"""
        self._similarity = similarity
        return self

    def with_metadata(self, metadata: dict[str, Any]):
        """Set metadata"""
        self._metadata = metadata
        return self

    def with_title(self, title: str):
        """Set title in metadata"""
        self._metadata["title"] = title
        return self

    def with_filename(self, filename: str):
        """Set filename in metadata"""
        self._metadata["filename"] = filename
        return self

    def with_ids(self, chunk_id: str, document_id: str):
        """Set chunk and document IDs"""
        self._chunk_id = chunk_id
        self._document_id = document_id
        return self

    def build(self) -> dict[str, Any]:
        """Build the context chunk"""
        return {
            "id": self._chunk_id,
            "content": self._content,
            "similarity": self._similarity,
            "metadata": self._metadata,
            "document_id": self._document_id,
        }
