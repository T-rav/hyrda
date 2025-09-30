"""
SearchResultBuilder for test utilities
"""

from typing import Any


class SearchResultBuilder:
    """Builder for creating search results"""

    def __init__(self):
        self._id = "result-1"
        self._content = "Test content"
        self._similarity = 0.85
        self._metadata = {}

    def with_id(self, result_id: str):
        """Set result ID"""
        self._id = result_id
        return self

    def with_content(self, content: str):
        """Set content"""
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
        """Add title to metadata"""
        self._metadata["title"] = title
        return self

    def with_source(self, source: str):
        """Add source to metadata"""
        self._metadata["source"] = source
        return self

    def build(self) -> dict[str, Any]:
        """Build the search result"""
        return {
            "id": self._id,
            "content": self._content,
            "similarity": self._similarity,
            "metadata": self._metadata,
        }
