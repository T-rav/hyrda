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

from bot_types import HealthStatus

from config.settings import Settings
from services.citation_service import CitationService
from services.context_builder import ContextBuilder
from services.conversation_manager import ConversationManager
from services.embedding import create_embedding_provider
from services.internal_deep_research import create_internal_deep_research_service
from services.langfuse_service import get_langfuse_service, observe
from services.llm_providers import create_llm_provider
from services.retrieval_service import RetrievalService
from services.search_clients import get_perplexity_client, get_tavily_client
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
        self.vector_store = create_vector_store(settings.vector)
        self.embedding_provider = create_embedding_provider(settings.embedding, settings.llm)
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

        # Initialize conversation manager for context management
        self.conversation_manager = ConversationManager(
            llm_provider=self.llm_provider,
            max_messages=settings.conversation.max_messages,
            keep_recent=settings.conversation.keep_recent,
            summarize_threshold=settings.conversation.summarize_threshold,
            model_context_window=settings.conversation.model_context_window,
        )

        # Initialize internal deep research service
        self.internal_deep_research = create_internal_deep_research_service(
            llm_service=query_rewrite_llm
            or self.llm_provider,  # Use query rewrite LLM or fallback to main LLM
            retrieval_service=self.retrieval_service,
            vector_service=self.vector_store,
            embedding_service=self.embedding_provider,
        )
        logger.info("✅ Internal deep research service initialized")

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
                        content[i : i + chunk_size] for i in range(0, len(content), chunk_size)
                    ]

                    # Generate embeddings for chunks
                    for chunk_content in chunks:
                        try:
                            chunk_embedding = await self.embedding_provider.get_embedding(
                                chunk_content
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

                logger.info(f"✅ Processed batch {i // batch_size + 1}: {len(texts)} chunks")

            except Exception as e:
                logger.error(f"Error processing batch {i // batch_size + 1}: {e}")
                error_count += len(batch)

        logger.info(f"📊 Ingestion complete: {success_count} success, {error_count} errors")

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
            logger.info(f"📊 Logged document ingestion to Langfuse: {len(documents)} documents")

        return success_count, error_count

    @observe(name="rag_generation", as_type="generation")
    async def _manage_conversation_context(
        self,
        conversation_history: list[dict[str, str]],
        system_message: str | None,
        session_id: str | None,
        conversation_cache: object | None,
    ) -> tuple[str | None, list[dict[str, str]]]:
        """
        Manage conversation context with summarization.

        Args:
            conversation_history: Previous messages
            system_message: System prompt
            session_id: Session ID
            conversation_cache: Conversation cache

        Returns:
            Tuple of (managed_system_message, managed_history)
        """
        existing_summary = None
        if conversation_cache and session_id:
            existing_summary = await conversation_cache.get_summary(session_id)

        (
            managed_system_message,
            managed_history,
        ) = await self.conversation_manager.manage_context(
            messages=conversation_history,
            system_message=system_message,
            existing_summary=existing_summary,
        )

        # Store updated summary if context was managed
        if (
            managed_system_message
            and managed_system_message != system_message
            and conversation_cache
            and session_id
            and "**Previous Conversation Summary:**" in managed_system_message
        ):
            summary_start = managed_system_message.index("**Previous Conversation Summary:**")
            summary_section = managed_system_message[summary_start:]
            await conversation_cache.store_summary(
                thread_ts=session_id,
                summary=summary_section,
                message_count=len(managed_history),
                compressed_from=len(conversation_history),
            )
            logger.info(
                f"✅ Stored conversation summary for session {session_id}: "
                f"compressed {len(conversation_history)} → {len(managed_history)} messages"
            )

        return managed_system_message, managed_history

    async def _retrieve_and_log_context(
        self,
        query: str,
        conversation_history: list[dict[str, str]],
        user_id: str | None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve context from vector store and log metrics.

        Args:
            query: User query
            conversation_history: Conversation history
            user_id: User ID

        Returns:
            List of context chunks
        """
        logger.info(f"Searching knowledge base for query: {query[:100]}...")
        context_chunks = await self.retrieval_service.retrieve_context(
            query,
            self.vector_store,
            self.embedding_provider,
            conversation_history=conversation_history,
            user_id=user_id,
        )
        logger.info(f"Found {len(context_chunks)} chunks from knowledge base")

        if context_chunks:
            await self._log_retrieval_metrics(query, context_chunks)
            summary = self.context_builder.format_context_summary(context_chunks)
            logger.info(f"🔍 {summary}")
        else:
            await self._log_retrieval_miss()

        return context_chunks

    async def _log_retrieval_metrics(
        self, query: str, context_chunks: list[dict[str, Any]]
    ) -> None:
        """Log RAG retrieval metrics to monitoring services."""
        from services.metrics_service import get_metrics_service

        metrics_service = get_metrics_service()
        if metrics_service:
            unique_docs = len(
                {chunk.get("metadata", {}).get("file_name", "unknown") for chunk in context_chunks}
            )
            avg_similarity = sum(chunk.get("similarity", 0) for chunk in context_chunks) / len(
                context_chunks
            )
            total_context_length = sum(len(chunk.get("content", "")) for chunk in context_chunks)

            metrics_service.record_rag_query_result(
                result_type="hit",
                provider=self.settings.vector.provider if self.settings.vector else "unknown",
                chunks_found=len(context_chunks),
                unique_documents=unique_docs,
                context_length=total_context_length,
                avg_similarity=avg_similarity,
            )

            for chunk in context_chunks:
                doc_metadata = chunk.get("metadata", {})
                doc_type = doc_metadata.get("file_type", "unknown")
                source = doc_metadata.get("source", "vector_db")
                metrics_service.record_document_usage(doc_type, source)

        langfuse_service = get_langfuse_service()
        if langfuse_service:
            retrieval_results = []
            for chunk in context_chunks:
                result = {
                    "content": chunk.get("content", ""),
                    "similarity": chunk.get("similarity", 0),
                    "metadata": chunk.get("metadata", {}),
                }
                if chunk.get("metadata", {}).get("file_name"):
                    result["document"] = chunk["metadata"]["file_name"]
                retrieval_results.append(result)

            langfuse_service.trace_retrieval(
                query=query,
                results=retrieval_results,
                metadata={
                    "retrieval_type": f"{self.settings.vector.provider}_rag"
                    if self.settings.vector
                    else "unknown_rag",
                    "total_chunks": len(context_chunks),
                    "avg_similarity": sum(r["similarity"] for r in retrieval_results)
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
            logger.info(f"📊 Logged retrieval of {len(context_chunks)} chunks to Langfuse")

    async def _log_retrieval_miss(self) -> None:
        """Log RAG retrieval miss (no context found)."""
        from services.metrics_service import get_metrics_service

        metrics_service = get_metrics_service()
        if metrics_service:
            metrics_service.record_rag_query_result(
                result_type="miss",
                provider=self.settings.vector.provider if self.settings.vector else "unknown",
            )

    def _add_document_to_context(
        self,
        document_content: str,
        document_filename: str | None,
        context_chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Add uploaded document chunks to context.

        Args:
            document_content: Document content
            document_filename: Document filename
            context_chunks: Existing context chunks

        Returns:
            Updated context chunks with document added
        """
        logger.info(f"💾 Adding chunked uploaded document to context: {document_filename}")
        from services.embedding import chunk_text

        document_chunks_content = chunk_text(document_content)
        document_chunks = []

        for i, chunk_content in enumerate(document_chunks_content):
            document_chunk = {
                "content": chunk_content,
                "metadata": {
                    "file_name": document_filename or "uploaded_document",
                    "source": "uploaded_document",
                    "chunk_id": f"uploaded_doc_{i}",
                },
                "similarity": 1.0,
            }
            document_chunks.append(document_chunk)

        updated_chunks = document_chunks + context_chunks
        logger.info(
            f"🔧 Added {len(document_chunks)} document chunks + {len(context_chunks)} RAG chunks"
        )
        return updated_chunks

    def _get_web_search_tools(self, use_rag: bool) -> list[dict] | None:
        """
        Get web search tools if available and appropriate.

        Args:
            use_rag: Whether RAG is enabled

        Returns:
            List of tool definitions or None
        """
        tavily_client = get_tavily_client()
        if not tavily_client:
            return None

        if use_rag:
            from services.search_clients import get_tool_definitions

            tools = get_tool_definitions(include_deep_research=False)
            logger.info(f"🔍 Web search tools available: {len(tools)} tools")
            return tools
        else:
            logger.info("🚫 Web search tools disabled (RAG disabled)")
            return None

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
        conversation_cache: object | None = None,
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
            conversation_cache: Optional conversation cache for summary storage

        Returns:
            Generated response with citations if RAG was used
        """
        try:
            # Step 1: Manage conversation context with summarization
            (
                system_message,
                conversation_history,
            ) = await self._manage_conversation_context(
                conversation_history, system_message, session_id, conversation_cache
            )

            # Step 2: Retrieve context if RAG is enabled
            context_chunks = []
            if use_rag and self.vector_store:
                context_chunks = await self._retrieve_and_log_context(
                    query, conversation_history, user_id
                )

            # Step 3: Add uploaded document to context if provided
            if document_content:
                context_chunks = self._add_document_to_context(
                    document_content, document_filename, context_chunks
                )

            # Step 4: Build prompt with context
            final_system_message, messages = self.context_builder.build_rag_prompt(
                query, context_chunks, conversation_history, system_message
            )

            # Step 5: Get web search tools if appropriate
            tools = self._get_web_search_tools(use_rag)

            # Step 6: Generate response from LLM
            response = await self.llm_provider.get_response(
                messages=messages,
                system_message=final_system_message,
                session_id=session_id,
                user_id=user_id,
                prompt_template_name=self.settings.langfuse.system_prompt_template
                if self.settings.langfuse.use_prompt_templates
                else None,
                prompt_template_version=self.settings.langfuse.prompt_template_version,
                tools=tools,
            )

            # Step 7: Handle tool calls if requested
            if isinstance(response, dict) and response.get("tool_calls"):
                logger.info(f"🛠️ LLM requested {len(response['tool_calls'])} tool calls")
                response = await self._handle_tool_calls(
                    response,
                    messages,
                    final_system_message,
                    session_id,
                    user_id,
                    tools,
                    conversation_history,
                )

            # Step 8: Validate and format response
            if not response:
                logger.warning("Empty response from LLM provider")
                return "I'm sorry, I couldn't generate a response right now."

            if isinstance(response, dict):
                response = response.get("content", "")

            # Step 9: Add citations if we used RAG
            if context_chunks and use_rag and response:
                response = self.citation_service.add_source_citations(response, context_chunks)

            return response or ""

        except Exception as e:
            logger.error(f"Error generating RAG response: {e}")
            return "I'm sorry, I encountered an error while generating a response."

    async def _execute_web_search(
        self,
        tool_args: dict,
        tool_id: str,
        session_id: str | None,
        user_id: str | None,
    ) -> dict:
        """Execute web search via Tavily."""
        tavily_client = get_tavily_client()
        query = tool_args.get("query", "")
        max_results = tool_args.get("max_results", 15)

        search_results = await tavily_client.search(query, max_results)
        formatted_results = "\n\n".join(
            [
                f"**{r.get('title', 'Untitled')}**\n{r.get('url', '')}\n{r.get('snippet', '')}"
                for r in search_results
            ]
        )

        logger.info(f"✅ Web search returned {len(search_results)} results")

        # Trace to Langfuse
        langfuse_service = get_langfuse_service()
        if langfuse_service:
            langfuse_service.trace_tool_execution(
                tool_name="web_search",
                tool_input=tool_args,
                tool_output=search_results,
                metadata={
                    "tool_id": tool_id,
                    "results_count": len(search_results),
                    "query": query,
                    "max_results": max_results,
                    "session_id": session_id,
                    "user_id": user_id,
                },
            )

        return {
            "tool_call_id": tool_id,
            "role": "tool",
            "name": "web_search",
            "content": formatted_results or "No results found",
        }

    async def _execute_url_scrape(
        self,
        tool_args: dict,
        tool_id: str,
        session_id: str | None,
        user_id: str | None,
    ) -> dict:
        """Execute URL scraping via Tavily."""
        tavily_client = get_tavily_client()
        url = tool_args.get("url", "")
        scrape_result = await tavily_client.scrape_url(url)

        if scrape_result.get("success"):
            content = scrape_result.get("content", "")
            title = scrape_result.get("title", "")
            formatted_content = f"# {title}\n\nURL: {url}\n\n{content[:5000]}"

            logger.info(f"✅ URL scrape returned {len(content)} chars from {url}")

            # Trace to Langfuse
            langfuse_service = get_langfuse_service()
            if langfuse_service:
                langfuse_service.trace_tool_execution(
                    tool_name="scrape_url",
                    tool_input=tool_args,
                    tool_output={"success": True, "content_length": len(content)},
                    metadata={
                        "tool_id": tool_id,
                        "url": url,
                        "title": title,
                        "content_length": len(content),
                        "session_id": session_id,
                        "user_id": user_id,
                    },
                )

            return {
                "tool_call_id": tool_id,
                "role": "tool",
                "name": "scrape_url",
                "content": formatted_content,
            }
        else:
            error = scrape_result.get("error", "Unknown error")
            logger.warning(f"❌ Scrape failed for {url}: {error}")
            return {
                "tool_call_id": tool_id,
                "role": "tool",
                "name": "scrape_url",
                "content": f"Failed to scrape URL: {error}",
            }

    async def _execute_deep_research(
        self,
        tool_args: dict,
        tool_id: str,
        session_id: str | None,
        user_id: str | None,
    ) -> dict:
        """Execute deep research via Perplexity."""
        perplexity_client = get_perplexity_client()

        if not perplexity_client:
            logger.warning("Perplexity client not available")
            return {
                "tool_call_id": tool_id,
                "role": "tool",
                "name": "deep_research",
                "content": "Deep research is not available (Perplexity API key not configured)",
            }

        query = tool_args.get("query", "")
        research_result = await perplexity_client.deep_research(query)

        if research_result.get("success") or research_result.get("answer"):
            answer = research_result.get("answer", "")
            sources = research_result.get("sources", [])

            # Format answer with sources
            formatted_answer = f"{answer}\n\n"
            if sources:
                formatted_answer += "### Sources\n\n"
                for source in sources[:10]:
                    url = source.get("url", "")
                    title = source.get("title", "Untitled")
                    formatted_answer += f"- {url} - Deep Research Results: {title}\n"

            logger.info(
                f"✅ Deep research returned {len(answer)} chars with {len(sources)} sources"
            )

            # Trace to Langfuse
            langfuse_service = get_langfuse_service()
            if langfuse_service:
                langfuse_service.trace_tool_execution(
                    tool_name="deep_research",
                    tool_input=tool_args,
                    tool_output={
                        "answer_length": len(answer),
                        "sources_count": len(sources),
                    },
                    metadata={
                        "tool_id": tool_id,
                        "query": query,
                        "answer_length": len(answer),
                        "sources_count": len(sources),
                        "session_id": session_id,
                        "user_id": user_id,
                    },
                )

            return {
                "tool_call_id": tool_id,
                "role": "tool",
                "name": "deep_research",
                "content": formatted_answer,
            }
        else:
            error = research_result.get("error", "Unknown error")
            logger.warning(f"❌ Deep research failed for {query}: {error}")
            return {
                "tool_call_id": tool_id,
                "role": "tool",
                "name": "deep_research",
                "content": f"Failed to perform deep research: {error}",
            }

    def _prepare_tool_messages(
        self,
        tool_call_response: dict,
        messages: list[dict[str, str]],
        tool_results: list[dict],
    ) -> list[dict[str, Any]]:
        """Prepare messages with tool calls and results for LLM."""
        import json

        tool_calls_for_message = []
        for tc in tool_call_response.get("tool_calls", []):
            tool_call_copy = tc.copy()
            # Ensure arguments is a JSON string
            if isinstance(tool_call_copy.get("function", {}).get("arguments"), dict):
                tool_call_copy["function"]["arguments"] = json.dumps(
                    tool_call_copy["function"]["arguments"]
                )
            tool_calls_for_message.append(tool_call_copy)

        return (
            messages
            + [
                {
                    "role": "assistant",
                    "content": tool_call_response.get("content", ""),
                    "tool_calls": tool_calls_for_message,
                },
            ]
            + tool_results
        )

    async def _handle_tool_calls(
        self,
        tool_call_response: dict,
        messages: list[dict[str, str]],
        system_message: str | None,
        session_id: str | None,
        user_id: str | None,
        tools: list[dict] | None,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        """
        Handle tool calls from the LLM (e.g., web search, internal research)

        Args:
            tool_call_response: Response containing tool calls
            messages: Conversation messages
            system_message: System prompt
            session_id: Session ID
            user_id: User ID
            tools: Available tools
            conversation_history: Conversation history for context

        Returns:
            Final response after executing tools
        """
        tavily_client = get_tavily_client()
        if not tavily_client:
            logger.warning("Tavily client not available for tool calls")
            return tool_call_response.get("content", "")

        # Execute each tool call
        tool_results = []
        for tool_call in tool_call_response.get("tool_calls", []):
            tool_name = tool_call.get("function", {}).get("name")
            tool_args = tool_call.get("function", {}).get("arguments", {})
            tool_id = tool_call.get("id", "unknown")

            logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

            try:
                if tool_name == "web_search":
                    result = await self._execute_web_search(tool_args, tool_id, session_id, user_id)
                    tool_results.append(result)
                elif tool_name == "scrape_url":
                    result = await self._execute_url_scrape(tool_args, tool_id, session_id, user_id)
                    tool_results.append(result)
                elif tool_name == "deep_research":
                    result = await self._execute_deep_research(
                        tool_args, tool_id, session_id, user_id
                    )
                    tool_results.append(result)
                else:
                    logger.warning(f"Unknown tool: {tool_name}")
                    tool_results.append(
                        {
                            "tool_call_id": tool_id,
                            "role": "tool",
                            "name": tool_name,
                            "content": f"Error: Unknown tool '{tool_name}'",
                        }
                    )
            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}")
                tool_results.append(
                    {
                        "tool_call_id": tool_id,
                        "role": "tool",
                        "name": tool_name,
                        "content": f"Error executing tool: {str(e)}",
                    }
                )

        # Prepare messages with tool results
        messages_with_tools = self._prepare_tool_messages(
            tool_call_response, messages, tool_results
        )

        # Get final response with tool results
        logger.info("🔄 Getting final response with tool results...")
        final_response = await self.llm_provider.get_response(
            messages=messages_with_tools,
            system_message=system_message,
            session_id=session_id,
            user_id=user_id,
            prompt_template_name=self.settings.langfuse.system_prompt_template
            if self.settings.langfuse.use_prompt_templates
            else None,
            prompt_template_version=self.settings.langfuse.prompt_template_version,
            tools=None,
        )

        if isinstance(final_response, dict):
            return final_response.get("content", "")
        return final_response or ""

    async def get_system_status(self) -> HealthStatus:
        """Get system status information"""
        status = {
            "vector_enabled": self.vector_store is not None,
            "embedding_provider": type(self.embedding_provider).__name__
            if self.embedding_provider
            else None,
            "llm_provider": type(self.llm_provider).__name__ if self.llm_provider else None,
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


# Global instance
_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    """Get or create global RAG service instance."""
    global _rag_service  # noqa: PLW0603

    if _rag_service is None:
        from config.settings import get_settings

        settings = get_settings()
        _rag_service = RAGService(settings)

    return _rag_service
