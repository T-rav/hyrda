"""
RetrievalResultBuilder for test utilities
"""

from datetime import datetime
from typing import Any

from models import RetrievalResult
from models.retrieval import RetrievalMethod


class RetrievalResultBuilder:
    """Builder for creating retrieval results with fluent API"""

    def __init__(self):
        self._content = "Default content"
        self._similarity = 0.85
        self._chunk_id = "chunk-1"
        self._document_id = "doc-1"
        self._source = RetrievalMethod.DENSE
        self._metadata = {}
        self._rank = None
        self._rerank_score = None

    def with_content(self, content: str):
        """Set content"""
        self._content = content
        return self

    def with_similarity(self, similarity: float):
        """Set similarity score"""
        self._similarity = similarity
        return self

    def with_source(self, source: RetrievalMethod):
        """Set retrieval source"""
        self._source = source
        return self

    def with_ids(self, chunk_id: str, document_id: str):
        """Set IDs"""
        self._chunk_id = chunk_id
        self._document_id = document_id
        return self

    def with_metadata(self, metadata: dict[str, Any]):
        """Set metadata"""
        self._metadata = metadata
        return self

    def with_rank(self, rank: int):
        """Set rank"""
        self._rank = rank
        return self

    def with_rerank_score(self, score: float):
        """Set rerank score"""
        self._rerank_score = score
        return self

    def build(self) -> RetrievalResult:
        """Build the retrieval result"""
        return RetrievalResult(
            content=self._content,
            similarity=self._similarity,
            chunk_id=self._chunk_id,
            document_id=self._document_id,
            source=self._source,
            metadata=self._metadata,
            rank=self._rank,
            rerank_score=self._rerank_score,
            retrieved_at=datetime.now(),
        )
