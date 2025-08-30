"""
RAG (Retrieval-Augmented Generation) service that combines vector search with LLM generation
"""

import json
import logging
from typing import Any

from config.settings import Settings
from services.embedding_service import chunk_text, create_embedding_provider
from services.langfuse_service import get_langfuse_service, observe
from services.llm_providers import create_llm_provider
from services.vector_service import create_vector_store

logger = logging.getLogger(__name__)


class RAGService:
    """
    RAG service that handles document ingestion, retrieval, and augmented generation
    """

    def __init__(self, settings: Settings):
        self.settings = settings

        # Initialize components if RAG is enabled
        self.vector_store = None
        self.embedding_provider = None
        self.llm_provider = None

        if settings.vector.enabled:
            self.vector_store = create_vector_store(settings.vector)
            self.embedding_provider = create_embedding_provider(
                settings.embedding, settings.llm
            )

        self.llm_provider = create_llm_provider(settings.llm)

    async def initialize(self):
        """Initialize all services"""
        logger.info("Initializing RAG service...")

        if self.vector_store:
            await self.vector_store.initialize()
            logger.info("Vector store initialized")

        logger.info("RAG service initialization complete")

    async def ingest_documents(
        self, documents: list[dict[str, Any]], batch_size: int = 50
    ) -> int:
        """
        Ingest documents into the vector store

        Args:
            documents: List of documents with 'content' and optional 'metadata'
            batch_size: Number of documents to process in each batch

        Returns:
            Number of chunks successfully ingested
        """
        if not self.vector_store or not self.embedding_provider:
            logger.warning("RAG not enabled - documents not ingested")
            return 0

        total_chunks = 0

        try:
            # Process documents in batches
            for i in range(0, len(documents), batch_size):
                batch = documents[i : i + batch_size]

                # Chunk all documents in the batch
                all_chunks = []
                all_metadata = []

                for doc in batch:
                    content = doc.get("content", "")
                    base_metadata = doc.get("metadata", {})

                    # Split document into chunks
                    chunks = chunk_text(
                        content,
                        chunk_size=self.settings.embedding.chunk_size,
                        chunk_overlap=self.settings.embedding.chunk_overlap,
                    )

                    # Add metadata for each chunk
                    for chunk_idx, chunk in enumerate(chunks):
                        chunk_metadata = base_metadata.copy()
                        chunk_metadata.update(
                            {
                                "chunk_index": chunk_idx,
                                "total_chunks": len(chunks),
                                "source_document": doc.get("id", f"doc_{i}"),
                            }
                        )

                        all_chunks.append(chunk)
                        all_metadata.append(chunk_metadata)

                if not all_chunks:
                    continue

                # Generate embeddings for all chunks
                logger.info(f"Generating embeddings for {len(all_chunks)} chunks...")
                embeddings = await self.embedding_provider.get_embeddings(all_chunks)

                # Add to vector store
                await self.vector_store.add_documents(
                    texts=all_chunks, embeddings=embeddings, metadata=all_metadata
                )

                total_chunks += len(all_chunks)
                logger.info(
                    f"Ingested batch {i // batch_size + 1}: {len(all_chunks)} chunks"
                )

            logger.info(
                f"Successfully ingested {total_chunks} total chunks from {len(documents)} documents"
            )
            return total_chunks

        except Exception as e:
            logger.error(f"Error during document ingestion: {e}")
            raise

    @observe(name="rag_retrieval", as_type="retrieval")
    async def retrieve_context(self, query: str) -> list[dict[str, Any]]:
        """
        Retrieve relevant context for a query

        Args:
            query: User query

        Returns:
            List of relevant document chunks with metadata
        """
        if not self.vector_store or not self.embedding_provider:
            logger.warning("RAG not enabled - no context retrieved")
            return []

        langfuse_service = get_langfuse_service()

        try:
            # Generate query embedding
            query_embedding = await self.embedding_provider.get_embedding(query)

            # Search vector store
            results = await self.vector_store.search(
                query_embedding=query_embedding,
                limit=self.settings.rag.max_chunks,
                similarity_threshold=self.settings.rag.similarity_threshold,
            )

            # Trace retrieval with Langfuse
            if langfuse_service:
                langfuse_service.trace_retrieval(
                    query=query,
                    results=results,
                    metadata={
                        "vector_provider": self.settings.vector.provider,
                        "embedding_provider": self.settings.embedding.provider,
                        "embedding_model": self.settings.embedding.model,
                        "max_chunks": self.settings.rag.max_chunks,
                        "similarity_threshold": self.settings.rag.similarity_threshold,
                    },
                )

            logger.info(f"Retrieved {len(results)} relevant chunks for query")
            return results

        except Exception as e:
            logger.error(f"Error during context retrieval: {e}")
            return []

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
        Generate a response using RAG or direct LLM

        Args:
            query: User query
            conversation_history: Previous messages
            system_message: Custom system prompt
            use_rag: Whether to use RAG retrieval

        Returns:
            Generated response
        """
        langfuse_service = get_langfuse_service()
        context_chunks = []

        try:
            final_system_message = system_message

            # Retrieve context if RAG is enabled and requested
            if use_rag and self.vector_store and self.embedding_provider:
                context_chunks = await self.retrieve_context(query)

                if context_chunks:
                    # Build context from retrieved chunks
                    context_texts = []
                    for chunk in context_chunks:
                        content = chunk["content"]
                        similarity = chunk.get("similarity", 0)

                        # Optionally include metadata
                        if self.settings.rag.include_metadata and chunk.get("metadata"):
                            metadata = chunk["metadata"]
                            source = metadata.get("source_document", "Unknown")
                            context_texts.append(
                                f"[Source: {source}, Similarity: {similarity:.2f}]\n{content}"
                            )
                        else:
                            context_texts.append(content)

                    # Create RAG system message
                    context_section = "\n\n".join(context_texts)
                    rag_instruction = (
                        "Use the following context to answer the user's question. "
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

                    logger.info(f"Using RAG with {len(context_chunks)} context chunks")

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

            if response:
                # Trace the complete RAG generation
                if langfuse_service:
                    metadata = {
                        "rag_enabled": use_rag,
                        "context_chunks_used": len(context_chunks),
                        "llm_provider": self.settings.llm.provider,
                        "llm_model": self.settings.llm.model,
                        "conversation_length": len(conversation_history),
                    }

                    if context_chunks:
                        metadata["avg_similarity"] = sum(
                            chunk.get("similarity", 0) for chunk in context_chunks
                        ) / len(context_chunks)

                logger.info(f"Generated response with length: {len(response)}")
                return response
            else:
                return "I apologize, but I'm unable to generate a response right now. Please try again."

        except Exception as e:
            logger.error(f"Error during response generation: {e}")
            return "I encountered an error while processing your request. Please try again."

    async def get_system_status(self) -> dict[str, Any]:
        """Get status information about the RAG system"""
        status = {
            "rag_enabled": self.settings.vector.enabled,
            "llm_provider": self.settings.llm.provider,
            "llm_model": self.settings.llm.model,
        }

        if self.settings.vector.enabled:
            status.update(
                {
                    "vector_provider": self.settings.vector.provider,
                    "embedding_provider": self.settings.embedding.provider,
                    "embedding_model": self.settings.embedding.model,
                    "max_chunks": self.settings.rag.max_chunks,
                    "similarity_threshold": self.settings.rag.similarity_threshold,
                }
            )

        return status

    async def close(self):
        """Clean up all resources"""
        logger.info("Shutting down RAG service...")

        if self.vector_store:
            await self.vector_store.close()

        if self.embedding_provider:
            await self.embedding_provider.close()

        if self.llm_provider:
            await self.llm_provider.close()

        logger.info("RAG service shutdown complete")


class DocumentProcessor:
    """Helper class for processing documents before ingestion"""

    @staticmethod
    def process_text_file(
        file_path: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Process a text file for ingestion"""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            doc_metadata = metadata or {}
            doc_metadata.update(
                {
                    "source_file": file_path,
                    "document_type": "text",
                    "file_size": len(content),
                }
            )

            return {"content": content, "metadata": doc_metadata, "id": file_path}

        except Exception as e:
            logger.error(f"Error processing text file {file_path}: {e}")
            raise

    @staticmethod
    def process_markdown_file(
        file_path: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Process a markdown file for ingestion"""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            doc_metadata = metadata or {}
            doc_metadata.update(
                {
                    "source_file": file_path,
                    "document_type": "markdown",
                    "file_size": len(content),
                }
            )

            return {"content": content, "metadata": doc_metadata, "id": file_path}

        except Exception as e:
            logger.error(f"Error processing markdown file {file_path}: {e}")
            raise

    @staticmethod
    def process_json_file(
        file_path: str,
        content_field: str = "content",
        metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Process a JSON file containing multiple documents"""

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            documents = []

            # Handle different JSON structures
            if isinstance(data, list):
                for i, item in enumerate(data):
                    if isinstance(item, dict) and content_field in item:
                        doc_metadata = metadata or {}
                        doc_metadata.update(
                            {
                                "source_file": file_path,
                                "document_type": "json",
                                "document_index": i,
                            }
                        )
                        doc_metadata.update(item.get("metadata", {}))

                        documents.append(
                            {
                                "content": item[content_field],
                                "metadata": doc_metadata,
                                "id": f"{file_path}_{i}",
                            }
                        )

            elif isinstance(data, dict) and content_field in data:
                doc_metadata = metadata or {}
                doc_metadata.update(
                    {
                        "source_file": file_path,
                        "document_type": "json",
                    }
                )
                doc_metadata.update(data.get("metadata", {}))

                documents.append(
                    {
                        "content": data[content_field],
                        "metadata": doc_metadata,
                        "id": file_path,
                    }
                )

            return documents

        except Exception as e:
            logger.error(f"Error processing JSON file {file_path}: {e}")
            raise
