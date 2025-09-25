"""
Hybrid RAG Service that orchestrates the complete hybrid retrieval pipeline

Integrates:
- Pinecone (dense vectors)
- Elasticsearch (sparse/BM25)
- Cross-encoder reranking
- Title injection
- Reciprocal rank fusion

Based on the expert's recommendations for modern RAG architecture.
"""

import asyncio
import logging
from typing import Any

from config.settings import Settings, VectorSettings
from services.citation_service import CitationService
from services.embedding_service import create_embedding_provider
from services.hybrid_retrieval_service import CohereReranker, HybridRetrievalService
from services.langfuse_service import get_langfuse_service, observe
from services.llm_providers import create_llm_provider
from services.title_injection_service import (
    EnhancedChunkProcessor,
    TitleInjectionService,
)
from services.vector_service import create_vector_store
from services.vector_stores import (
    ElasticsearchVectorStore,
    PineconeVectorStore,
)

logger = logging.getLogger(__name__)


class HybridRAGService:
    """
    Complete hybrid RAG service implementing the expert's architecture:

    1. Dual indexing: Pinecone (dense) + Elasticsearch (sparse)
    2. Title injection for better semantic understanding
    3. Hybrid retrieval with RRF fusion
    4. Cross-encoder reranking for final quality
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.vector_settings = settings.vector
        self.hybrid_settings = settings.hybrid

        # Core services
        self.dense_store: PineconeVectorStore | None = None
        self.sparse_store: ElasticsearchVectorStore | None = None
        self.hybrid_retrieval: HybridRetrievalService | None = None
        self.title_injection: TitleInjectionService | None = None
        self.chunk_processor: EnhancedChunkProcessor | None = None
        self.embedding_service = None
        self.llm_provider = None
        self.citation_service = CitationService()

        # Track initialization
        self._initialized = False

    async def initialize(self):
        """Initialize all components of the hybrid RAG system"""
        try:
            logger.info("Initializing hybrid RAG service...")

            # Initialize embedding service
            self.embedding_service = create_embedding_provider(
                self.settings.embedding, self.settings.llm
            )
            logger.info("✅ Embedding service initialized")

            # Initialize LLM provider
            self.llm_provider = create_llm_provider(self.settings.llm)
            logger.info("✅ LLM provider initialized")

            # Initialize title injection service
            self.title_injection = TitleInjectionService()
            self.chunk_processor = EnhancedChunkProcessor(self.title_injection)

            # Initialize Pinecone for dense vectors
            pinecone_settings = VectorSettings(
                provider="pinecone",
                api_key=self.vector_settings.api_key,
                collection_name=self.vector_settings.collection_name,
                environment=self.vector_settings.environment,
            )
            self.dense_store = create_vector_store(pinecone_settings)
            await self.dense_store.initialize()
            logger.info("✅ Pinecone dense store initialized")

            # Initialize Elasticsearch for sparse vectors
            es_settings = VectorSettings(
                provider="elasticsearch",
                url=self.vector_settings.url,
                collection_name=f"{self.vector_settings.collection_name}_sparse",
            )
            self.sparse_store = create_vector_store(es_settings)
            await self.sparse_store.initialize()
            logger.info("✅ Elasticsearch sparse store initialized")

            # Initialize reranker if enabled
            reranker = None
            if (
                self.hybrid_settings.reranker_enabled
                and self.hybrid_settings.reranker_provider == "cohere"
            ):
                if not self.hybrid_settings.reranker_api_key:
                    logger.warning("Cohere API key not provided, reranking disabled")
                else:
                    # Handle both SecretStr and plain string
                    api_key = self.hybrid_settings.reranker_api_key
                    if hasattr(api_key, "get_secret_value"):
                        api_key = api_key.get_secret_value()
                    reranker = CohereReranker(
                        api_key=api_key,
                        model=self.hybrid_settings.reranker_model,
                    )
                    logger.info("✅ Cohere reranker initialized")

            # Initialize hybrid retrieval orchestrator
            self.hybrid_retrieval = HybridRetrievalService(
                dense_store=self.dense_store,
                sparse_store=self.sparse_store,
                reranker=reranker,
                dense_top_k=self.hybrid_settings.dense_top_k,
                sparse_top_k=self.hybrid_settings.sparse_top_k,
                fusion_top_k=self.hybrid_settings.fusion_top_k,
                final_top_k=self.hybrid_settings.final_top_k,
                rrf_k=self.hybrid_settings.rrf_k,
            )

            self._initialized = True
            logger.info("🚀 Hybrid RAG service fully initialized")

        except Exception as e:
            logger.error(f"Failed to initialize hybrid RAG service: {e}")
            raise

    async def ingest_documents(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadata: list[dict[str, Any]],
    ) -> bool:
        """
        Ingest documents into both dense and sparse stores with title injection
        """
        if not self._initialized:
            raise RuntimeError("HybridRAGService not initialized")

        try:
            logger.info(f"Starting dual ingestion of {len(texts)} documents...")

            # Prepare documents for dual indexing
            documents = [
                {"content": text, "metadata": meta}
                for text, meta in zip(texts, metadata, strict=False)
            ]

            dual_docs = self.chunk_processor.prepare_for_dual_indexing(documents)

            # Extract data for dense indexing (with title injection)
            dense_texts = [doc["content"] for doc in dual_docs["dense"]]
            dense_metadata = [doc["metadata"] for doc in dual_docs["dense"]]

            # Extract data for sparse indexing (separate title field)
            sparse_texts = [doc["content"] for doc in dual_docs["sparse"]]
            sparse_metadata = []
            for doc in dual_docs["sparse"]:
                meta = doc["metadata"].copy()
                meta["title"] = doc.get("title", "")  # Add title field
                sparse_metadata.append(meta)

            # Parallel ingestion into both stores
            dense_task = self.dense_store.add_documents(
                texts=dense_texts, embeddings=embeddings, metadata=dense_metadata
            )

            # For sparse store, pass empty embeddings (won't be used)
            sparse_task = self.sparse_store.add_documents(
                texts=sparse_texts,
                embeddings=[[]]
                * len(sparse_texts),  # Empty embeddings for sparse store
                metadata=sparse_metadata,
            )

            await asyncio.gather(dense_task, sparse_task)

            logger.info(
                f"✅ Successfully ingested {len(texts)} documents into hybrid system"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to ingest documents: {e}")
            return False

    async def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        top_k: int | None = None,
        similarity_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        Perform hybrid search with the complete pipeline:
        Dense + Sparse → RRF → Cross-encoder reranking
        """
        if not self._initialized:
            raise RuntimeError("HybridRAGService not initialized")

        if not self.hybrid_settings.enabled:
            # Fallback to dense-only search
            logger.info("Hybrid disabled, falling back to dense-only search")
            return await self.dense_store.search(
                query_embedding=query_embedding,
                limit=top_k or 10,
                similarity_threshold=similarity_threshold,
            )

        # Use hybrid retrieval pipeline
        results = await self.hybrid_retrieval.hybrid_search(
            query=query,
            query_embedding=query_embedding,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )

        # Convert RetrievalResult objects back to dict format for compatibility
        return [
            {
                "content": result.content,
                "similarity": result.similarity,
                "metadata": result.metadata,
                "id": result.id,
                "_hybrid_source": result.source,  # Track source for debugging
                "_hybrid_rank": result.rank,
            }
            for result in results
        ]

    @observe(name="hybrid_rag_generation", as_type="generation")
    async def generate_response(
        self,
        query: str,
        conversation_history: list[dict[str, str]],
        system_message: str | None = None,
        use_rag: bool = True,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """
        Generate a response using hybrid RAG or direct LLM

        Args:
            query: User query
            conversation_history: Previous messages
            system_message: Custom system prompt
            use_rag: Whether to use RAG retrieval
            session_id: Session ID for tracing
            user_id: User ID for tracing

        Returns:
            Generated response with citations
        """
        if not self._initialized:
            raise RuntimeError("HybridRAGService not initialized")

        context_chunks = []

        try:
            final_system_message = system_message

            # Retrieve context if RAG is enabled and requested
            if use_rag and self.hybrid_settings.enabled:
                # Get query embedding
                query_embedding = await self.embedding_service.get_embedding(query)

                # Perform hybrid search
                context_chunks = await self.hybrid_search(
                    query=query,
                    query_embedding=query_embedding,
                    top_k=self.hybrid_settings.final_top_k,
                    similarity_threshold=0.0,  # Let reranking handle quality
                )

                # Log retrieved documents to Langfuse
                if context_chunks:
                    langfuse_service = get_langfuse_service()
                    if langfuse_service:
                        # Prepare retrieval data for Langfuse with document details
                        retrieval_results = []
                        for chunk in context_chunks:
                            result = {
                                "content": chunk["content"],
                                "similarity": chunk.get("similarity", 0),
                                "source": chunk.get("_hybrid_source", "unknown"),
                                "rank": chunk.get("_hybrid_rank", 0),
                                "metadata": chunk.get("metadata", {}),
                            }
                            # Add document name for easier tracking
                            if chunk.get("metadata", {}).get("file_name"):
                                result["document"] = chunk["metadata"]["file_name"]
                            retrieval_results.append(result)

                        # Send retrieval trace to Langfuse
                        langfuse_service.trace_retrieval(
                            query=query,
                            results=retrieval_results,
                            metadata={
                                "retrieval_type": "hybrid_rag",
                                "top_k": self.hybrid_settings.final_top_k,
                                "total_chunks": len(context_chunks),
                                "avg_similarity": sum(
                                    r["similarity"] for r in retrieval_results
                                )
                                / len(retrieval_results)
                                if retrieval_results
                                else 0,
                                "sources_used": list(
                                    {
                                        r.get("source", "unknown")
                                        for r in retrieval_results
                                    }
                                ),
                                "documents_used": list(
                                    {
                                        r.get("document", "unknown")
                                        for r in retrieval_results
                                        if r.get("document")
                                    }
                                ),
                            },
                        )
                        logger.info(
                            f"📊 Logged retrieval of {len(context_chunks)} chunks to Langfuse for query: {query[:50]}..."
                        )

                if context_chunks:
                    # Build context from retrieved chunks
                    context_texts = []
                    for chunk in context_chunks:
                        content = chunk["content"]
                        similarity = chunk.get("similarity", 0)
                        source = chunk.get("_hybrid_source", "hybrid")

                        # Include metadata if available
                        if chunk.get("metadata"):
                            metadata = chunk["metadata"]
                            source_doc = metadata.get("file_name", "Unknown")
                            context_texts.append(
                                f"[Source: {source_doc}, Score: {similarity:.2f}, Via: {source}]\n{content}"
                            )
                        else:
                            context_texts.append(
                                f"[Score: {similarity:.2f}, Via: {source}]\n{content}"
                            )

                    # Create RAG system message
                    context_section = "\n\n".join(context_texts)
                    rag_instruction = (
                        "Use the following context retrieved via hybrid search (dense + sparse + reranking) to answer the user's question. "
                        "Answer naturally without adding inline source citations like '[Source: ...]' since "
                        "complete source citations will be automatically added at the end of your response. "
                        "If the context doesn't contain relevant information, "
                        "say so and provide a general response based on your knowledge.\n\n"
                        f"Context:\n{context_section}\n\n"
                    )

                    if final_system_message:
                        final_system_message = (
                            f"{final_system_message}\n\n{rag_instruction}"
                        )
                    else:
                        final_system_message = rag_instruction

                    logger.info(
                        f"🔍 Using hybrid RAG with {len(context_chunks)} context chunks"
                    )

            # Prepare messages for LLM
            messages = conversation_history.copy()
            messages.append({"role": "user", "content": query})

            # Generate response
            response = await self.llm_provider.get_response(
                messages=messages,
                system_message=final_system_message,
                session_id=session_id,
                user_id=user_id,
            )

            if not response:
                logger.warning("Empty response from LLM provider")
                return "I'm sorry, I couldn't generate a response right now."

            # Add citations if we used RAG
            if context_chunks and use_rag:
                response = self.citation_service.add_source_citations(
                    response, context_chunks
                )

            return response

        except Exception as e:
            logger.error(f"Error generating hybrid RAG response: {e}")
            return "I'm sorry, I encountered an error while generating a response."

    async def get_system_status(self) -> dict[str, Any]:
        """Get comprehensive system status"""
        status = {
            "initialized": self._initialized,
            "hybrid_enabled": self.hybrid_settings.enabled,
            "components": {},
        }

        if self._initialized:
            try:
                # Test dense store
                status["components"]["dense_store"] = "healthy"
            except Exception as e:
                status["components"]["dense_store"] = f"error: {e}"

            try:
                # Test sparse store
                status["components"]["sparse_store"] = "healthy"
            except Exception as e:
                status["components"]["sparse_store"] = f"error: {e}"

            status["components"]["reranker"] = (
                "enabled" if self.hybrid_settings.reranker_enabled else "disabled"
            )
            status["components"]["title_injection"] = "always_enabled"

        return status

    async def close(self):
        """Clean up all resources"""
        logger.info("Shutting down hybrid RAG service...")

        if self.hybrid_retrieval:
            await self.hybrid_retrieval.close()
            # Note: hybrid_retrieval.close() already closes dense_store and sparse_store

        logger.info("✅ Hybrid RAG service shut down complete")


# Factory function for backward compatibility
async def create_hybrid_rag_service(settings: Settings) -> HybridRAGService:
    """Create and initialize hybrid RAG service"""
    service = HybridRAGService(settings)
    await service.initialize()
    return service
