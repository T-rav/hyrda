"""
RAG (Retrieval-Augmented Generation) Service - Refactored

Clean, focused RAG orchestration service that coordinates between:
- RetrievalService: Document retrieval and search
- ContextBuilder: Context formatting and prompt building
- CitationService: Source citation management
- DocumentProcessor: Document processing and chunking
"""

import logging
from typing import Any

from config.settings import Settings
from services.citation_service import CitationService
from services.context_builder import ContextBuilder
from services.document_processor import DocumentProcessor
from services.embedding_service import create_embedding_provider
from services.langfuse_service import observe
from services.llm_providers import create_llm_provider
from services.retrieval_service import RetrievalService
from services.vector_service import create_vector_store

logger = logging.getLogger(__name__)


class RAGService:
    """
    Main RAG orchestration service that coordinates retrieval and generation.

    This service acts as the main interface for RAG operations while delegating
    specific responsibilities to focused service classes.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

        # Initialize core components
        self.vector_store = None
        self.embedding_provider = None
        self.llm_provider = None

        if settings.vector.enabled:
            self.vector_store = create_vector_store(settings.vector)
            self.embedding_provider = create_embedding_provider(
                settings.embedding, settings.llm
            )

        self.llm_provider = create_llm_provider(settings.llm)

        # Initialize specialized services
        self.retrieval_service = RetrievalService(settings)
        self.context_builder = ContextBuilder()
        self.citation_service = CitationService()
        self.document_processor = DocumentProcessor()

    async def initialize(self):
        """Initialize all services"""
        logger.info("Initializing RAG service...")

        if self.vector_store:
            await self.vector_store.initialize()
            logger.info("✅ Vector store initialized")

        logger.info("✅ RAG service initialization complete")

    async def ingest_documents(
        self, documents: list[dict[str, Any]], batch_size: int = 50
    ) -> tuple[int, int]:
        """
        Ingest documents into the vector store.

        Args:
            documents: List of documents with content and metadata
            batch_size: Number of documents to process at once

        Returns:
            Tuple of (success_count, error_count)
        """
        if not self.vector_store:
            raise RuntimeError("Vector store not initialized")

        success_count = 0
        error_count = 0

        logger.info(f"📥 Starting ingestion of {len(documents)} documents")

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]

            try:
                texts = []
                metadatas = []
                embeddings = []

                for doc in batch:
                    content = doc.get("content", "")
                    metadata = doc.get("metadata", {})

                    if not content.strip():
                        logger.warning("Skipping document with empty content")
                        error_count += 1
                        continue

                    # Process document based on type
                    file_type = metadata.get("file_type", "text")
                    processed_chunks = self.document_processor.process_generic_document(
                        content, file_type, metadata
                    )

                    # Generate embeddings for chunks
                    for chunk in processed_chunks:
                        try:
                            chunk_embedding = (
                                await self.embedding_provider.get_embedding(
                                    chunk["content"]
                                )
                            )

                            texts.append(chunk["content"])
                            metadatas.append(chunk["metadata"])
                            embeddings.append(chunk_embedding)

                        except Exception as e:
                            logger.error(f"Error generating embedding: {e}")
                            error_count += 1

                # Add batch to vector store
                if texts:
                    await self.vector_store.add_documents(
                        texts=texts, embeddings=embeddings, metadata=metadatas
                    )
                    success_count += len(texts)

                logger.info(
                    f"✅ Processed batch {i // batch_size + 1}: {len(texts)} chunks"
                )

            except Exception as e:
                logger.error(f"Error processing batch {i // batch_size + 1}: {e}")
                error_count += len(batch)

        logger.info(
            f"📊 Ingestion complete: {success_count} success, {error_count} errors"
        )
        return success_count, error_count

    @observe(name="rag_generation", as_type="generation")
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
        Generate a response using RAG or direct LLM.

        Args:
            query: User query
            conversation_history: Previous messages in the conversation
            system_message: Custom system prompt
            use_rag: Whether to use RAG retrieval
            session_id: Session ID for tracing
            user_id: User ID for tracing

        Returns:
            Generated response with citations if RAG was used
        """
        context_chunks = []

        try:
            # Retrieve context if RAG is enabled and requested
            if use_rag and self.vector_store:
                context_chunks = await self.retrieval_service.retrieve_context(
                    query, self.vector_store, self.embedding_provider
                )

                # Log context quality
                if context_chunks:
                    summary = self.context_builder.format_context_summary(
                        context_chunks
                    )
                    logger.info(f"🔍 {summary}")

            # Build prompt with context
            final_system_message, messages = self.context_builder.build_rag_prompt(
                query, context_chunks, conversation_history, system_message
            )

            # Generate response from LLM
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
            logger.error(f"Error generating RAG response: {e}")
            return "I'm sorry, I encountered an error while generating a response."

    async def get_system_status(self) -> dict[str, Any]:
        """Get system status information"""
        status = {
            "vector_enabled": self.vector_store is not None,
            "embedding_provider": type(self.embedding_provider).__name__
            if self.embedding_provider
            else None,
            "llm_provider": type(self.llm_provider).__name__
            if self.llm_provider
            else None,
            "services": {
                "retrieval": "initialized",
                "context_builder": "initialized",
                "citation": "initialized",
                "document_processor": "initialized",
            },
        }

        if self.vector_store:
            try:
                # Test vector store connectivity
                test_embedding = [0.0] * 1536  # OpenAI embedding dimension
                await self.vector_store.search(
                    query_embedding=test_embedding, limit=1, similarity_threshold=0.9
                )
                status["vector_store_status"] = "healthy"
            except Exception as e:
                status["vector_store_status"] = f"error: {e}"

        return status

    async def close(self):
        """Clean up resources"""
        logger.info("Shutting down RAG service...")

        if self.vector_store:
            await self.vector_store.close()

        logger.info("✅ RAG service shut down complete")


# Factory function for backward compatibility
async def create_rag_service(settings: Settings) -> RAGService:
    """Create and initialize RAG service"""
    service = RAGService(settings)
    await service.initialize()
    return service
