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

from models import RetrievalMethod, RetrievalResult
from services.rerankers import Reranker

logger = logging.getLogger(__name__)


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
                    metadata=r.get("metadata", {}),
                    chunk_id=r["id"],
                    document_id=r.get(
                        "document_id", r["id"]
                    ),  # Fallback to chunk_id if no document_id
                    source=RetrievalMethod.DENSE,
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
                    metadata=r.get("metadata", {}),
                    chunk_id=r["id"],
                    document_id=r.get(
                        "document_id", r["id"]
                    ),  # Fallback to chunk_id if no document_id
                    source=RetrievalMethod.SPARSE,
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
        # Create lookup for dense results by chunk_id
        dense_lookup = {
            result.chunk_id: (i + 1, result) for i, result in enumerate(dense_results)
        }
        sparse_lookup = {
            result.chunk_id: (i + 1, result) for i, result in enumerate(sparse_results)
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

            # Determine source based on where the document appears
            if appears_in_dense and appears_in_sparse:
                source_type = RetrievalMethod.HYBRID  # Appears in both - true hybrid
            elif appears_in_sparse:
                source_type = RetrievalMethod.SPARSE  # Sparse/Elasticsearch only
            else:
                source_type = RetrievalMethod.DENSE  # Dense/Pinecone only

            # Create a new RetrievalResult with the updated source
            # since the original is frozen
            fused_doc = RetrievalResult(
                content=doc.content,
                similarity=doc.similarity,  # Will be updated later in the final loop
                chunk_id=doc.chunk_id,
                document_id=doc.document_id,
                source=source_type,
                rank=doc.rank,
                rerank_score=doc.rerank_score,
                metadata=doc.metadata,
                retrieved_at=doc.retrieved_at,
            )

            fused_scores[doc_id] = rrf_score
            fused_docs[doc_id] = fused_doc

        # Sort by RRF score (higher is better)
        sorted_ids = sorted(
            fused_scores.keys(), key=lambda x: fused_scores[x], reverse=True
        )

        # Create final fused results with scaled RRF scores
        fused_results = []
        max_rrf_score = max(fused_scores.values()) if fused_scores else 1.0

        for i, doc_id in enumerate(sorted_ids):
            original_doc = fused_docs[doc_id]
            # Scale RRF scores to meaningful similarity range (0.3-0.95)
            # Normalize against max score, then scale with a power curve for good spread
            normalized_score = fused_scores[doc_id] / max_rrf_score
            scaled_score = (
                normalized_score**0.8
            )  # Gentle power curve for better distribution

            # Create new RetrievalResult with updated similarity and rank
            # since the original is frozen
            fused_doc = RetrievalResult(
                content=original_doc.content,
                similarity=0.3 + (scaled_score * 0.65),  # Scale to 0.3-0.95 range
                chunk_id=original_doc.chunk_id,
                document_id=original_doc.document_id,
                source=original_doc.source,
                rank=i + 1,
                rerank_score=original_doc.rerank_score,
                metadata=original_doc.metadata,
                retrieved_at=original_doc.retrieved_at,
            )
            fused_results.append(fused_doc)

        logger.info(
            f"RRF fused {len(dense_results)} dense + {len(sparse_results)} sparse → {len(fused_results)} results"
        )
        return fused_results

    async def close(self):
        """Clean up resources"""
        await self.dense_store.close()
        await self.sparse_store.close()
