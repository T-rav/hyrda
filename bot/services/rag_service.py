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
        Retrieve relevant context for a query with hybrid search (semantic + keyword)

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

            # Extract entities for potential metadata filtering
            entities = self._extract_entities_simple(query)

            # Try entity-focused search first if entities detected
            entity_results = []
            if entities:
                entity_results = await self._search_with_entity_filtering(
                    query_embedding, entities
                )

            # Run regular semantic search with very broad parameters to capture all Apple docs
            semantic_results = await self.vector_store.search(
                query_embedding=query_embedding,
                limit=200,  # Get even more candidates for reranking
                similarity_threshold=0.01,  # Very low threshold to capture all potential matches
            )

            # Combine results (entity results get priority)
            results = self._combine_search_results(entity_results, semantic_results)

            # Apply hybrid search: boost documents with exact entity matches
            enhanced_results = self._apply_hybrid_search_boosting(query, results)

            # Two-pass filtering system:
            # Pass 1: Lower threshold to allow entity-boosted documents through
            pass1_threshold = self.settings.rag.similarity_threshold  # 0.5
            pass1_filtered = [
                result
                for result in enhanced_results
                if result.get("similarity", 0) >= pass1_threshold
            ]

            # Pass 2: Higher threshold for final high-quality results
            pass2_threshold = self.settings.rag.results_similarity_threshold  # 0.7
            final_results = [
                result
                for result in pass1_filtered
                if result.get("similarity", 0) >= pass2_threshold
            ][: self.settings.rag.max_results]  # Use max_results instead of max_chunks

            # Debug logging
            pass1_filtered_out = len(enhanced_results) - len(pass1_filtered)
            pass2_filtered_out = len(pass1_filtered) - len(final_results)

            if pass1_filtered_out > 0:
                logger.info(
                    f"📊 PASS 1 FILTER: Filtered out {pass1_filtered_out} results below {pass1_threshold} threshold"
                )

            if pass2_filtered_out > 0:
                logger.info(
                    f"📊 PASS 2 FILTER: Filtered out {pass2_filtered_out} results below {pass2_threshold} threshold"
                )
                # Show what got filtered in pass 2
                pass2_filtered_out_results = [
                    r
                    for r in pass1_filtered
                    if r.get("similarity", 0) < pass2_threshold
                ][:3]
                for result in pass2_filtered_out_results:
                    metadata = result.get("metadata", {})
                    file_name = metadata.get("file_name", "unknown")
                    similarity = result.get("similarity", 0)
                    logger.info(
                        f"   • {file_name[:60]}... (similarity: {similarity:.3f})"
                    )

            # Trace retrieval with Langfuse
            if langfuse_service:
                langfuse_service.trace_retrieval(
                    query=query,
                    results=final_results,
                    metadata={
                        "vector_provider": self.settings.vector.provider,
                        "embedding_provider": self.settings.embedding.provider,
                        "embedding_model": self.settings.embedding.model,
                        "max_chunks": self.settings.rag.max_chunks,
                        "similarity_threshold": self.settings.rag.similarity_threshold,
                        "hybrid_search": True,
                        "candidates_retrieved": len(results),
                    },
                )

            logger.info(
                f"Retrieved {len(final_results)} relevant chunks for query (from {len(results)} candidates)"
            )
            return final_results

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
                        "When you reference information from the context, you can mention the document names naturally in your response. "
                        "Source citations with clickable links will be automatically added at the end of your response. "
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
                # Add source citations to the response if RAG was used
                if use_rag and context_chunks:
                    response = self._add_source_citations(response, context_chunks)

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

    def _add_source_citations(
        self, response: str, context_chunks: list[dict[str, Any]]
    ) -> str:
        """
        Add source citations with Google Drive links to the response

        Args:
            response: The generated response from the LLM
            context_chunks: List of context chunks used for generation

        Returns:
            Response with source citations appended
        """
        # Extract unique sources from context chunks
        sources = {}
        for chunk in context_chunks:
            metadata = chunk.get("metadata", {})

            # Use file_id as the key to avoid duplicates
            file_id = metadata.get("file_id")
            if not file_id:
                continue

            file_name = metadata.get("file_name", "Unknown Document")
            web_view_link = metadata.get("web_view_link")
            folder_path = metadata.get("folder_path", "")

            if file_id not in sources:
                sources[file_id] = {
                    "name": file_name,
                    "link": web_view_link,
                    "path": folder_path,
                    "similarity": chunk.get("similarity", 0),
                }
            else:
                # Keep the highest similarity score if we see the same document multiple times
                sources[file_id]["similarity"] = max(
                    sources[file_id]["similarity"], chunk.get("similarity", 0)
                )

        if not sources:
            return response

        # Build citations section
        citations = ["\n\n📚 **Sources:**"]

        # Sort sources by similarity score (highest first)
        sorted_sources = sorted(
            sources.items(), key=lambda x: x[1]["similarity"], reverse=True
        )

        for i, (_file_id, source_info) in enumerate(sorted_sources, 1):
            name = source_info["name"]
            link = source_info["link"]
            path = source_info["path"]
            similarity = source_info["similarity"]

            if link:
                # Create clickable link for Slack
                citation = f"{i}. [{name}]({link})"
                if path:
                    citation += f" (📁 {path})"
                citation += f" - *Relevance: {similarity:.1%}*"
            else:
                # Fallback if no link available
                citation = f"{i}. {name}"
                if path:
                    citation += f" (📁 {path})"
                citation += f" - *Relevance: {similarity:.1%}*"

            citations.append(citation)

        return response + "\n".join(citations)

    def _apply_hybrid_search_boosting(
        self, query: str, results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Apply hybrid search boosting to prioritize exact entity matches

        Args:
            query: Original user query
            results: Vector search results

        Returns:
            Results with boosted similarity scores for exact matches
        """
        # Extract entities using simple but effective regex patterns
        entities = self._extract_entities_simple(query)

        logger.info(
            f"🔍 ENTITY DETECTION: Query='{query}', Detected entities={entities}"
        )

        if not entities:
            logger.info(
                f"❌ NO ENTITIES DETECTED - returning {len(results)} original results"
            )
            return results

        logger.info(
            f"🚀 HYBRID SEARCH ACTIVE: Applying boosting for entities: {entities}"
        )

        enhanced_results = []
        for result in results:
            boosted_result = result.copy()

            # Check content and metadata for entity mentions
            content = result.get("content", "").lower()
            metadata = result.get("metadata", {})
            file_name = metadata.get("file_name", "").lower()
            folder_path = metadata.get("folder_path", "").lower()

            # Search text includes content, filename, and path
            search_text = f"{content} {file_name} {folder_path}"

            # Calculate boost factor based on entity matches
            boost_factor = 1.0
            matches_found = []

            for entity in entities:
                # Exact match in title gets highest boost
                if entity in file_name:
                    boost_factor *= 5.0  # 5x boost for title matches - ensure all Apple docs get through
                    matches_found.append(f"{entity}(title)")
                # Exact match in content or path
                elif (
                    f" {entity} " in f" {search_text} "
                    or search_text.startswith(entity)
                    or search_text.endswith(entity)
                ):
                    boost_factor *= 2.5  # 2.5x boost per exact match
                    matches_found.append(f"{entity}(exact)")
                # Partial match boost (lower priority)
                elif entity in search_text:
                    boost_factor *= 1.5  # 1.5x boost per partial match
                    matches_found.append(f"{entity}(partial)")

            # Extra boost for short/unique entity names (avoid false positives)
            for entity in entities:
                if (
                    len(entity) <= 5  # Short names are more unique
                    and entity in search_text
                    and entity not in ["video", "audio", "media"]
                ):  # Avoid common false positives
                    boost_factor *= 1.0  # No extra boost - just the 2x is enough
                    matches_found.append(f"{entity}(unique)")

            # Apply boost to similarity score (cap at 0.95 to maintain relative ordering)
            original_similarity = result.get("similarity", 0)
            boosted_similarity = min(0.95, original_similarity * boost_factor)
            boosted_result["similarity"] = boosted_similarity

            # Add debug info
            if boost_factor > 1.0:
                boosted_result["boost_info"] = {
                    "boost_factor": boost_factor,
                    "matches": matches_found,
                    "original_similarity": original_similarity,
                }
                logger.debug(
                    f"Boosted document '{file_name}' from {original_similarity:.3f} to {boosted_similarity:.3f} (factor: {boost_factor:.2f}, matches: {matches_found})"
                )

            enhanced_results.append(boosted_result)

        # Sort by boosted similarity scores
        enhanced_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)

        # Deduplicate by document title - return max 1 chunk per unique document
        seen_documents = set()
        deduplicated_results = []

        for result in enhanced_results:
            metadata = result.get("metadata", {})
            file_name = metadata.get("file_name", "Unknown")

            if file_name not in seen_documents:
                seen_documents.add(file_name)
                deduplicated_results.append(result)

                # Stop when we have enough unique documents
                if len(deduplicated_results) >= len(enhanced_results):
                    break

        logger.debug(
            f"Deduplicated results: {len(enhanced_results)} chunks → {len(deduplicated_results)} unique documents"
        )

        # Remove debug info for cleaner results
        # Debug info removed to clean up output

        return deduplicated_results

    def _extract_entities_simple(self, query: str) -> set[str]:
        """
        Extract entities from query - just get every meaningful word
        """
        entities = set()

        # Super simple stop words
        stop_words = {
            "has",
            "have",
            "is",
            "are",
            "was",
            "were",
            "with",
            "the",
            "and",
            "or",
            "but",
            "to",
            "of",
            "in",
            "on",
            "for",
            "at",
            "by",
            "from",
            "how",
            "what",
            "when",
            "where",
            "why",
            "who",
            "which",
            "this",
            "that",
            "i",
            "we",
            "you",
            "they",
            "8th",
            "light",
            "worked",
            "work",
        }

        # Just split and clean
        words = query.lower().split()
        for word in words:
            clean_word = word.strip('.,!?();:"')
            if clean_word not in stop_words and len(clean_word) > 2:
                entities.add(clean_word)

        return entities

    async def _search_with_entity_filtering(
        self, query_embedding: list[float], entities: set[str]
    ) -> list[dict[str, Any]]:
        """
        Search with entity-based metadata filtering for Pinecone

        Args:
            query_embedding: Query embedding vector
            entities: Set of entities to filter by

        Returns:
            List of search results filtered by entities
        """
        if not self.vector_store or not entities:
            return []

        # Only use metadata filtering for Pinecone
        if self.settings.vector.provider.lower() != "pinecone":
            return []

        try:
            # Create metadata filter for entities
            # Pinecone doesn't support $contains, so we'll skip metadata filtering
            # and rely on the hybrid boosting system instead
            logger.info(
                "🔍 Skipping Pinecone metadata filtering (not supported), relying on hybrid boosting"
            )
            return []  # Return empty, let hybrid boosting handle entity prioritization

        except Exception as e:
            logger.error(f"Error in entity-filtered search: {e}")
            return []

    def _combine_search_results(
        self,
        entity_results: list[dict[str, Any]],
        semantic_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Combine entity-filtered and semantic search results

        Args:
            entity_results: Results from entity-filtered search
            semantic_results: Results from regular semantic search

        Returns:
            Combined and deduplicated results with entity results prioritized
        """
        # Use document ID to track duplicates
        seen_docs = set()
        combined_results = []

        # Add entity results first (higher priority)
        for result in entity_results:
            doc_id = result.get("id")
            if doc_id and doc_id not in seen_docs:
                seen_docs.add(doc_id)
                combined_results.append(result)

        # Add semantic results that weren't already included
        for result in semantic_results:
            doc_id = result.get("id")
            if doc_id and doc_id not in seen_docs:
                seen_docs.add(doc_id)
                result["source"] = "semantic"  # Mark as semantic result
                combined_results.append(result)

        # Sort by similarity score (entity-boosted results should naturally rank higher)
        combined_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)

        logger.info(
            f"🔄 Combined results: {len(entity_results)} entity + {len(semantic_results)} semantic = {len(combined_results)} total"
        )

        return combined_results


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
