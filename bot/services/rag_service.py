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
from services.embedding import create_embedding_provider
from services.langfuse_service import get_langfuse_service, observe
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

        # Create separate LLM provider for query rewriting (uses different model)
        query_rewrite_llm = None
        if settings.rag.enable_query_rewriting:
            # Create LLM settings for query rewriting model
            from copy import deepcopy

            query_llm_settings = deepcopy(settings.llm)
            query_llm_settings.model = settings.rag.query_rewrite_model
            query_rewrite_llm = create_llm_provider(query_llm_settings)
            logger.info(
                f"✅ Query rewriting enabled with model: {settings.rag.query_rewrite_model}"
            )

        # Initialize specialized services
        self.retrieval_service = RetrievalService(
            settings,
            llm_service=query_rewrite_llm,  # Use separate model for query rewriting
            enable_query_rewriting=settings.rag.enable_query_rewriting,
        )
        self.context_builder = ContextBuilder()
        self.citation_service = CitationService()

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

                    # Simple text chunking (document processing handled by ingest service)
                    chunk_size = 1000
                    chunks = [
                        content[i : i + chunk_size]
                        for i in range(0, len(content), chunk_size)
                    ]

                    # Generate embeddings for chunks
                    for chunk_content in chunks:
                        try:
                            chunk_embedding = (
                                await self.embedding_provider.get_embedding(
                                    chunk_content
                                )
                            )

                            texts.append(chunk_content)
                            metadatas.append(metadata)
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

        # Trace document ingestion to Langfuse
        langfuse_service = get_langfuse_service()
        if langfuse_service:
            langfuse_service.trace_document_ingestion(
                documents=documents,
                success_count=success_count,
                error_count=error_count,
                metadata={
                    "ingestion_type": "rag_service",
                    "batch_size": batch_size,
                    "vector_store": self.settings.vector.provider
                    if self.settings.vector
                    else "unknown",
                    "embedding_provider": type(self.embedding_provider).__name__
                    if self.embedding_provider
                    else "unknown",
                },
            )
            logger.info(
                f"📊 Logged document ingestion to Langfuse: {len(documents)} documents"
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
        document_content: str | None = None,
        document_filename: str | None = None,
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
            document_content: Content of uploaded document for context
            document_filename: Name of uploaded document

        Returns:
            Generated response with citations if RAG was used
        """
        context_chunks = []

        try:
            # Retrieve context if RAG is enabled and requested
            if use_rag and self.vector_store:
                # If document content is provided, use document-based vector search
                if document_content:
                    logger.info(
                        f"Performing document-based vector search for uploaded file: {document_filename}"
                    )
                    # Generate embedding for the uploaded document
                    document_embeddings = await self.embedding_provider.get_embeddings(
                        [document_content]
                    )
                    if document_embeddings:
                        # Search vector store using document's embedding
                        context_chunks = (
                            await self.retrieval_service.retrieve_context_by_embedding(
                                document_embeddings[0], self.vector_store
                            )
                        )
                        logger.info(
                            f"Found {len(context_chunks)} related chunks using document embedding"
                        )
                    else:
                        logger.warning(
                            "Failed to generate embedding for uploaded document, falling back to query-based search"
                        )
                        context_chunks = await self.retrieval_service.retrieve_context(
                            query, self.vector_store, self.embedding_provider
                        )
                else:
                    # Standard query-based retrieval (pass conversation history for context)
                    context_chunks = await self.retrieval_service.retrieve_context(
                        query,
                        self.vector_store,
                        self.embedding_provider,
                        conversation_history=conversation_history,
                    )

                # Log retrieved documents to Langfuse and record metrics
                if context_chunks:
                    # Record RAG metrics
                    from services.metrics_service import get_metrics_service

                    metrics_service = get_metrics_service()
                    if metrics_service:
                        # Calculate metrics
                        unique_docs = len(
                            {
                                chunk.get("metadata", {}).get("file_name", "unknown")
                                for chunk in context_chunks
                            }
                        )
                        avg_similarity = sum(
                            chunk.get("similarity", 0) for chunk in context_chunks
                        ) / len(context_chunks)
                        total_context_length = sum(
                            len(chunk.get("content", "")) for chunk in context_chunks
                        )

                        # Record successful RAG query
                        metrics_service.record_rag_query_result(
                            result_type="hit",
                            provider=self.settings.vector.provider
                            if self.settings.vector
                            else "unknown",
                            chunks_found=len(context_chunks),
                            unique_documents=unique_docs,
                            context_length=total_context_length,
                            avg_similarity=avg_similarity,
                        )

                        # Record document usage
                        for chunk in context_chunks:
                            doc_metadata = chunk.get("metadata", {})
                            doc_type = doc_metadata.get("file_type", "unknown")
                            source = doc_metadata.get("source", "vector_db")
                            metrics_service.record_document_usage(doc_type, source)

                    langfuse_service = get_langfuse_service()
                    if langfuse_service:
                        # Prepare retrieval data for Langfuse with document details
                        retrieval_results = []
                        for chunk in context_chunks:
                            result = {
                                "content": chunk.get("content", ""),
                                "similarity": chunk.get("similarity", 0),
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
                                "retrieval_type": f"{self.settings.vector.provider}_rag"
                                if self.settings.vector
                                else "unknown_rag",
                                "total_chunks": len(context_chunks),
                                "avg_similarity": sum(
                                    r["similarity"] for r in retrieval_results
                                )
                                / len(retrieval_results)
                                if retrieval_results
                                else 0,
                                "documents_used": list(
                                    {
                                        r.get("document", "unknown")
                                        for r in retrieval_results
                                        if r.get("document")
                                    }
                                ),
                                "vector_store": self.settings.vector.provider
                                if self.settings.vector
                                else "unknown",
                            },
                        )
                        logger.info(
                            f"📊 Logged retrieval of {len(context_chunks)} chunks to Langfuse for query: {query[:50]}..."
                        )
                else:
                    # Record RAG miss when no context found
                    from services.metrics_service import get_metrics_service

                    metrics_service = get_metrics_service()
                    if metrics_service:
                        metrics_service.record_rag_query_result(
                            result_type="miss",
                            provider=self.settings.vector.provider
                            if self.settings.vector
                            else "unknown",
                        )

                # Log context quality
                if context_chunks:
                    summary = self.context_builder.format_context_summary(
                        context_chunks
                    )
                    logger.info(f"🔍 {summary}")

            # Add uploaded document to context if provided
            if document_content:
                logger.info(
                    f"💾 Adding chunked uploaded document to context: {document_filename}"
                )
                # Chunk the document content properly for context
                from services.embedding import chunk_text

                document_chunks_content = chunk_text(
                    document_content
                )  # Get chunks for the document

                # Create document chunks for each piece of the uploaded content
                document_chunks = []
                for i, chunk_content in enumerate(document_chunks_content):
                    document_chunk = {
                        "content": chunk_content,
                        "metadata": {
                            "file_name": document_filename or "uploaded_document",
                            "source": "uploaded_document",
                            "chunk_id": f"uploaded_doc_{i}",
                        },
                        "similarity": 1.0,  # Perfect match since it's the actual uploaded doc
                    }
                    document_chunks.append(document_chunk)

                # Add all uploaded document chunks as first context (highest priority)
                context_chunks = document_chunks + context_chunks
                logger.info(
                    f"🔧 Added {len(document_chunks)} document chunks plus {len(context_chunks)-len(document_chunks)} RAG chunks"
                )

            # Build prompt with context (includes uploaded document + retrieved context)
            final_system_message, messages = self.context_builder.build_rag_prompt(
                query, context_chunks, conversation_history, system_message
            )

            # Generate response from LLM
            response = await self.llm_provider.get_response(
                messages=messages,
                system_message=final_system_message,
                session_id=session_id,
                user_id=user_id,
                prompt_template_name=self.settings.langfuse.system_prompt_template
                if self.settings.langfuse.use_prompt_templates
                else None,
                prompt_template_version=self.settings.langfuse.prompt_template_version,
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
