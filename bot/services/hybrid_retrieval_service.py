"""
Hybrid Retrieval Service implementing dense + sparse + cross-encoder reranking

Based on the expert recommendations for modern RAG:
- Dense retrieval via Pinecone (topK=100)
- Sparse retrieval via Elasticsearch BM25 (topK=200)
- Reciprocal Rank Fusion (RRF)
- Cross-encoder reranking with Cohere/Voyage
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

try:
    import cohere
except ImportError:
    cohere = None

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Unified result format for all retrieval stages"""

    content: str
    similarity: float
    metadata: dict[str, Any]
    id: str
    source: str  # "dense", "sparse", or "hybrid"
    rank: int | None = None


class Reranker(ABC):
    """Abstract base class for cross-encoder rerankers"""

    @abstractmethod
    async def rerank(
        self, query: str, documents: list[RetrievalResult], top_k: int = 10
    ) -> list[RetrievalResult]:
        """Rerank documents using cross-encoder"""
        pass


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
                # Normalize Cohere relevance score to 0-1 range and ensure valid bounds
                original_doc.similarity = min(1.0, max(0.0, result.relevance_score))
                original_doc.rank = len(reranked_results) + 1
                reranked_results.append(original_doc)

            logger.info(
                f"Reranked {len(doc_texts)} documents to top {len(reranked_results)}"
            )
            return reranked_results

        except Exception as e:
            logger.error(f"Cohere reranking failed: {e}")
            # Fallback to original ranking
            return documents[:top_k]


class HybridRetrievalService:
    """
    Implements hybrid dense + sparse retrieval with cross-encoder reranking

    Architecture:
    1. Dense retrieval (Pinecone) - topK=100
    2. Sparse retrieval (Elasticsearch BM25) - topK=200
    3. Reciprocal Rank Fusion (RRF)
    4. Cross-encoder reranking - top 10
    """

    def __init__(
        self,
        dense_store,  # PineconeVectorStore
        sparse_store,  # ElasticsearchVectorStore (for BM25)
        reranker: Reranker | None = None,
        dense_top_k: int = 100,
        sparse_top_k: int = 200,
        fusion_top_k: int = 50,
        final_top_k: int = 10,
        rrf_k: int = 60,
    ):
        self.dense_store = dense_store
        self.sparse_store = sparse_store
        self.reranker = reranker
        self.dense_top_k = dense_top_k
        self.sparse_top_k = sparse_top_k
        self.fusion_top_k = fusion_top_k
        self.final_top_k = final_top_k
        self.rrf_k = rrf_k

    async def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        top_k: int | None = None,
        similarity_threshold: float = 0.0,
    ) -> list[RetrievalResult]:
        """
        Perform hybrid retrieval with the full pipeline:
        Dense + Sparse → RRF → Cross-encoder reranking
        """
        final_k = top_k or self.final_top_k

        # Step 1: Parallel dense and sparse retrieval
        logger.info(f"Starting hybrid search for query: {query[:50]}...")

        dense_task = self._dense_retrieval(query_embedding)
        sparse_task = self._sparse_retrieval(query)

        dense_results, sparse_results = await asyncio.gather(
            dense_task, sparse_task, return_exceptions=True
        )

        # Handle exceptions
        if isinstance(dense_results, Exception):
            logger.error(f"Dense retrieval failed: {dense_results}")
            dense_results = []
        if isinstance(sparse_results, Exception):
            logger.error(f"Sparse retrieval failed: {sparse_results}")
            sparse_results = []

        logger.info(
            f"Retrieved {len(dense_results)} dense + {len(sparse_results)} sparse results"
        )

        # Step 2: Reciprocal Rank Fusion
        fused_results = self._reciprocal_rank_fusion(dense_results, sparse_results)[
            : self.fusion_top_k
        ]

        logger.info(f"Fused to {len(fused_results)} candidates")

        # Step 3: Cross-encoder reranking (if available)
        if self.reranker and len(fused_results) > 0:
            final_results = await self.reranker.rerank(query, fused_results, final_k)
            logger.info(f"Reranked to final {len(final_results)} results")
        else:
            final_results = fused_results[:final_k]
            logger.info(
                f"No reranker, returning top {len(final_results)} fused results"
            )

        # Apply similarity threshold
        filtered_results = [
            result
            for result in final_results
            if result.similarity >= similarity_threshold
        ]

        logger.info(
            f"Final results after threshold {similarity_threshold}: {len(filtered_results)}"
        )
        return filtered_results

    async def _dense_retrieval(
        self, query_embedding: list[float]
    ) -> list[RetrievalResult]:
        """Dense vector retrieval via Pinecone"""
        try:
            results = await self.dense_store.search(
                query_embedding=query_embedding,
                limit=self.dense_top_k,
                similarity_threshold=0.0,  # No threshold at this stage
            )

            return [
                RetrievalResult(
                    content=r["content"],
                    similarity=r["similarity"],
                    metadata=r["metadata"],
                    id=r["id"],
                    source="dense",
                )
                for r in results
            ]
        except Exception as e:
            logger.error(f"Dense retrieval failed: {e}")
            return []

    async def _sparse_retrieval(self, query: str) -> list[RetrievalResult]:
        """Sparse BM25 retrieval via Elasticsearch"""
        try:
            # Use Elasticsearch's BM25 with field boosting
            results = await self.sparse_store.bm25_search(
                query=query,
                limit=self.sparse_top_k,
                field_boosts={"title": 8.0, "content": 1.0},  # Boost titles 8x
            )

            return [
                RetrievalResult(
                    content=r["content"],
                    similarity=r["similarity"],
                    metadata=r["metadata"],
                    id=r["id"],
                    source="sparse",
                )
                for r in results
            ]
        except Exception as e:
            logger.error(f"Sparse retrieval failed: {e}")
            return []

    def _reciprocal_rank_fusion(
        self,
        dense_results: list[RetrievalResult],
        sparse_results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """
        Reciprocal Rank Fusion as described in the expert's advice

        RRF Score = sum(1 / (k + rank)) for each list where doc appears
        Default k=60 from research
        """
        # Create lookup for dense results by ID
        dense_lookup = {
            result.id: (i + 1, result) for i, result in enumerate(dense_results)
        }
        sparse_lookup = {
            result.id: (i + 1, result) for i, result in enumerate(sparse_results)
        }

        # Get all unique document IDs
        all_ids = set(dense_lookup.keys()) | set(sparse_lookup.keys())

        fused_scores = {}
        fused_docs = {}

        for doc_id in all_ids:
            rrf_score = 0.0
            doc = None
            appears_in_dense = doc_id in dense_lookup
            appears_in_sparse = doc_id in sparse_lookup

            # Add dense contribution
            if appears_in_dense:
                dense_rank, dense_doc = dense_lookup[doc_id]
                rrf_score += 1.0 / (self.rrf_k + dense_rank)
                doc = dense_doc

            # Add sparse contribution
            if appears_in_sparse:
                sparse_rank, sparse_doc = sparse_lookup[doc_id]
                rrf_score += 1.0 / (self.rrf_k + sparse_rank)
                if doc is None:  # Sparse-only result
                    doc = sparse_doc

            # Set source based on where the document appears
            if appears_in_dense and appears_in_sparse:
                doc.source = "hybrid"  # Appears in both - true hybrid
            elif appears_in_sparse:
                doc.source = "elastic"  # Sparse/Elasticsearch only
            else:
                doc.source = "dense"  # Dense/Pinecone only

            fused_scores[doc_id] = rrf_score
            fused_docs[doc_id] = doc

        # Sort by RRF score (higher is better)
        sorted_ids = sorted(
            fused_scores.keys(), key=lambda x: fused_scores[x], reverse=True
        )

        # Create final fused results with RRF scores as similarity
        fused_results = []
        for i, doc_id in enumerate(sorted_ids):
            doc = fused_docs[doc_id]
            doc.similarity = fused_scores[doc_id]  # Use RRF score
            doc.rank = i + 1
            fused_results.append(doc)

        logger.info(
            f"RRF fused {len(dense_results)} dense + {len(sparse_results)} sparse → {len(fused_results)} results"
        )
        return fused_results

    async def close(self):
        """Clean up resources"""
        await self.dense_store.close()
        await self.sparse_store.close()
