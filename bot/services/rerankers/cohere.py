"""
Cohere Rerank API implementation
"""

import logging

from models import RetrievalResult
from services.rerankers.base import Reranker

try:
    import cohere
except ImportError:
    cohere = None

logger = logging.getLogger(__name__)


class CohereReranker(Reranker):
    """Cohere Rerank-3 implementation"""

    def __init__(self, api_key: str, model: str = "rerank-english-v3.0"):
        self.api_key = api_key
        self.model = model
        self._client = None

    async def _get_client(self):
        if self._client is None:
            if cohere is None:
                raise ImportError("cohere package is required for reranking")
            self._client = cohere.AsyncClient(api_key=self.api_key)
        return self._client

    async def rerank(
        self, query: str, documents: list[RetrievalResult], top_k: int = 10
    ) -> list[RetrievalResult]:
        """Rerank using Cohere API"""
        try:
            client = await self._get_client()

            # Prepare documents for Cohere
            doc_texts = [doc.content for doc in documents]

            response = await client.rerank(
                model=self.model,
                query=query,
                documents=doc_texts,
                top_k=min(top_k, len(documents)),
                return_documents=False,  # We already have the docs
            )

            # Map reranked results back to our format with normalized scores
            reranked_results = []
            for result in response.results:
                original_doc = documents[result.index]
                # Create new RetrievalResult with updated similarity and rank
                # since the original is frozen
                reranked_doc = RetrievalResult(
                    content=original_doc.content,
                    similarity=min(
                        1.0, max(0.0, result.relevance_score)
                    ),  # Normalize to 0-1
                    chunk_id=original_doc.chunk_id,
                    document_id=original_doc.document_id,
                    source=original_doc.source,
                    rank=len(reranked_results) + 1,
                    rerank_score=result.relevance_score,
                    metadata=original_doc.metadata,
                    retrieved_at=original_doc.retrieved_at,
                )
                reranked_results.append(reranked_doc)

            logger.info(
                f"Reranked {len(doc_texts)} documents to top {len(reranked_results)}"
            )
            return reranked_results

        except Exception as e:
            logger.error(f"Cohere reranking failed: {e}")
            # Fallback to original ranking
            return documents[:top_k]
