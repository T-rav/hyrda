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
from services.conversation_manager import ConversationManager
from services.embedding import create_embedding_provider
from services.internal_deep_research import create_internal_deep_research_service
from services.langfuse_service import LangfuseService, get_langfuse_service, observe
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
        conversation_cache=None,
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
        context_chunks = []

        try:
            # Manage conversation context with summarization
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
                # Extract summary from system message (it's appended after "---")
                summary_start = managed_system_message.index(
                    "**Previous Conversation Summary:**"
                )
                summary_section = managed_system_message[summary_start:]
                # Store summary with metadata for better tracking
                await conversation_cache.store_summary(
                    thread_ts=session_id,
                    summary=summary_section,
                    message_count=len(managed_history),  # Messages kept
                    compressed_from=len(conversation_history),  # Original message count
                )
                logger.info(
                    f"✅ Stored conversation summary v? for session {session_id}: "
                    f"compressed {len(conversation_history)} messages to {len(managed_history)} "
                    f"(kept recent {len(managed_history)} + summary)"
                )

            # Use managed context for the rest of the generation
            system_message = managed_system_message
            conversation_history = managed_history
            # Retrieve context if RAG is enabled and requested
            if use_rag and self.vector_store:
                # Always search for relevant knowledge based on the user's query
                # This ensures we find internal knowledge even when a document is uploaded
                logger.info(f"Searching knowledge base for query: {query[:100]}...")
                context_chunks = await self.retrieval_service.retrieve_context(
                    query,
                    self.vector_store,
                    self.embedding_provider,
                    conversation_history=conversation_history,
                    user_id=user_id,
                )
                logger.info(
                    f"Found {len(context_chunks)} chunks from knowledge base for query"
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

                        # Get trace context from current @observe decorator
                        trace_context = LangfuseService.get_current_trace_context()

                        # Send retrieval trace to Langfuse with hierarchical linking
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
                            trace_context=trace_context,
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
                    f"🔧 Added {len(document_chunks)} document chunks plus {len(context_chunks) - len(document_chunks)} RAG chunks"
                )

            # Build prompt with context (includes uploaded document + retrieved context)
            final_system_message, messages = self.context_builder.build_rag_prompt(
                query, context_chunks, conversation_history, system_message
            )

            # Check if we should enable web search tools
            # Regular chat only gets Tavily (web_search + scrape_url), NOT deep_research
            # IMPORTANT: Disable tools when RAG is disabled (e.g., profile threads)
            tavily_client = get_tavily_client()
            tools = None
            if tavily_client and use_rag:
                from services.search_clients import get_tool_definitions

                tools = get_tool_definitions(include_deep_research=False)
                logger.info(
                    f"🔍 Web search tools available: {len(tools)} tools (Tavily only)"
                )
            elif tavily_client and not use_rag:
                logger.info(
                    "🚫 Web search tools disabled (RAG disabled for this thread)"
                )

            # Generate response from LLM (with optional function calling)
            response = await self.llm_provider.get_response(
                messages=messages,
                system_message=final_system_message,
                session_id=session_id,
                user_id=user_id,
                prompt_template_name=self.settings.langfuse.system_prompt_template
                if self.settings.langfuse.use_prompt_templates
                else None,
                prompt_template_version=self.settings.langfuse.prompt_template_version,
                tools=tools,  # Pass web search tools
            )

            # Handle tool calls if LLM requested web search or internal research
            if isinstance(response, dict) and response.get("tool_calls"):
                logger.info(f"🛠️ LLM requested {len(response['tool_calls'])} tool calls")
                response_str = await self._handle_tool_calls(
                    response,
                    messages,
                    final_system_message,
                    session_id,
                    user_id,
                    tools,
                    conversation_history,  # Pass conversation history for internal research
                )
                response = response_str

            if not response:
                logger.warning("Empty response from LLM provider")
                return "I'm sorry, I couldn't generate a response right now."

            # Ensure response is a string at this point
            if isinstance(response, dict):
                response = response.get("content", "")

            # Add citations if we used RAG
            if context_chunks and use_rag and response:
                response = self.citation_service.add_source_citations(
                    response, context_chunks
                )

            return response or ""

        except Exception as e:
            logger.error(f"Error generating RAG response: {e}")
            return "I'm sorry, I encountered an error while generating a response."

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
        perplexity_client = get_perplexity_client()

        if not tavily_client:
            logger.warning("Tavily client not available for tool calls")
            return tool_call_response.get("content", "")

        # Execute each tool call
        tool_results = []
        langfuse_service = get_langfuse_service()

        for tool_call in tool_call_response.get("tool_calls", []):
            tool_name = tool_call.get("function", {}).get("name")
            tool_args = tool_call.get("function", {}).get("arguments", {})
            tool_id = tool_call.get("id", "unknown")

            logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

            try:
                if tool_name == "web_search":
                    # Execute web search
                    query = tool_args.get("query", "")
                    max_results = tool_args.get("max_results", 15)

                    search_results = await tavily_client.search(query, max_results)

                    # Format results for LLM
                    formatted_results = "\n\n".join(
                        [
                            f"**{r.get('title', 'Untitled')}**\n{r.get('url', '')}\n{r.get('snippet', '')}"
                            for r in search_results
                        ]
                    )

                    tool_results.append(
                        {
                            "tool_call_id": tool_id,
                            "role": "tool",
                            "name": tool_name,
                            "content": formatted_results or "No results found",
                        }
                    )

                    logger.info(f"✅ Web search returned {len(search_results)} results")

                    # Trace tool execution to Langfuse with hierarchical linking
                    if langfuse_service:
                        # Get trace context from current @observe decorator
                        trace_context = LangfuseService.get_current_trace_context()

                        langfuse_service.trace_tool_execution(
                            tool_name=tool_name,
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
                            trace_context=trace_context,
                        )
                        logger.info(
                            f"📊 Logged tool execution to Langfuse: {tool_name}"
                        )

                elif tool_name == "scrape_url":
                    # Execute URL scraping
                    url = tool_args.get("url", "")
                    scrape_result = await tavily_client.scrape_url(url)

                    if scrape_result.get("success"):
                        content = scrape_result.get("content", "")
                        title = scrape_result.get("title", "")
                        formatted_content = f"# {title}\n\nURL: {url}\n\n{content[:5000]}"  # Limit to 5k chars

                        tool_results.append(
                            {
                                "tool_call_id": tool_id,
                                "role": "tool",
                                "name": tool_name,
                                "content": formatted_content,
                            }
                        )

                        logger.info(
                            f"✅ URL scrape returned {len(content)} chars from {url}"
                        )

                        # Trace tool execution to Langfuse with hierarchical linking
                        if langfuse_service:
                            # Get trace context from current @observe decorator
                            trace_context = LangfuseService.get_current_trace_context()

                            langfuse_service.trace_tool_execution(
                                tool_name=tool_name,
                                tool_input=tool_args,
                                tool_output={
                                    "success": True,
                                    "content_length": len(content),
                                },
                                metadata={
                                    "tool_id": tool_id,
                                    "url": url,
                                    "title": title,
                                    "content_length": len(content),
                                    "session_id": session_id,
                                    "user_id": user_id,
                                },
                                trace_context=trace_context,
                            )
                            logger.info(
                                f"📊 Logged tool execution to Langfuse: {tool_name}"
                            )
                    else:
                        error = scrape_result.get("error", "Unknown error")
                        tool_results.append(
                            {
                                "tool_call_id": tool_id,
                                "role": "tool",
                                "name": tool_name,
                                "content": f"Failed to scrape URL: {error}",
                            }
                        )
                        logger.warning(f"❌ Scrape failed for {url}: {error}")

                elif tool_name == "deep_research":
                    # Execute deep research via Perplexity
                    if not perplexity_client:
                        logger.warning("Perplexity client not available")
                        tool_results.append(
                            {
                                "tool_call_id": tool_id,
                                "role": "tool",
                                "name": tool_name,
                                "content": "Deep research is not available (Perplexity API key not configured)",
                            }
                        )
                        continue

                    query = tool_args.get("query", "")
                    research_result = await perplexity_client.deep_research(query)

                    if research_result.get("success") or research_result.get("answer"):
                        answer = research_result.get("answer", "")
                        sources = research_result.get("sources", [])

                        # Format answer with sources
                        # Use "Deep Research Results" keyword so sources get tagged as [DEEP_RESEARCH]
                        formatted_answer = f"{answer}\n\n"
                        if sources:
                            formatted_answer += "### Sources\n\n"
                            for source in sources[:10]:  # Limit to 10 sources
                                url = source.get("url", "")
                                title = source.get("title", "Untitled")
                                # Add "Deep Research Results" to description so it's detected by format_research_context
                                formatted_answer += (
                                    f"- {url} - Deep Research Results: {title}\n"
                                )

                        tool_results.append(
                            {
                                "tool_call_id": tool_id,
                                "role": "tool",
                                "name": tool_name,
                                "content": formatted_answer,
                            }
                        )

                        logger.info(
                            f"✅ Deep research returned {len(answer)} chars with {len(sources)} sources for: {query}"
                        )

                        # Trace tool execution to Langfuse with hierarchical linking
                        if langfuse_service:
                            # Get trace context from current @observe decorator
                            trace_context = LangfuseService.get_current_trace_context()

                            langfuse_service.trace_tool_execution(
                                tool_name=tool_name,
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
                                trace_context=trace_context,
                            )
                            logger.info(
                                f"📊 Logged tool execution to Langfuse: {tool_name}"
                            )
                    else:
                        error = research_result.get("error", "Unknown error")
                        tool_results.append(
                            {
                                "tool_call_id": tool_id,
                                "role": "tool",
                                "name": tool_name,
                                "content": f"Failed to perform deep research: {error}",
                            }
                        )
                        logger.warning(f"❌ Deep research failed for {query}: {error}")

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

        # Add tool results to conversation and get final response
        # OpenAI expects tool_calls[].function.arguments to be a JSON string
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

        messages_with_tools = (
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
            tools=None,  # Don't allow more tool calls - LLM should synthesize answer from results
        )

        # Ensure we return a string (tool calls should not happen in second call)
        if isinstance(final_response, dict):
            return final_response.get("content", "")
        return final_response or ""

    async def deep_research_for_agent(
        self,
        query: str,
        system_prompt: str | None = None,
        effort: str = "medium",
        agent_context: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Perform deep research with agent-specific context and custom prompts.

        This method is designed for agents (like the research agent) to call
        instead of implementing their own custom internal search tools.

        Args:
            query: Research query to investigate
            system_prompt: Optional custom system prompt for agent-specific behavior
            effort: Research effort level - "low", "medium", or "high"
            agent_context: Agent-specific metadata (e.g., {"research_topic": "...", "focus_area": "..."})
            user_id: User ID for access control and personalization

        Returns:
            Dict with:
                - success: bool - Whether research succeeded
                - content: str - Formatted answer with citations
                - chunks: list[dict] - Retrieved context chunks with metadata
                - sources: list[str] - Unique document sources (file names)
                - summary: str - Synthesized summary of findings
                - unique_documents: int - Number of unique documents found
                - total_chunks: int - Total number of chunks retrieved
                - error: str - Error message if failed (only if success=False)

        Example:
            result = await rag_service.deep_research_for_agent(
                query="What are our best practices for AI implementation?",
                system_prompt="You are researching for a technical proposal...",
                effort="high",
                agent_context={"research_topic": "AI Strategy", "focus_area": "implementation"}
            )

            if result["success"]:
                print(result["content"])  # Formatted answer with citations

        """
        if not self.internal_deep_research:
            logger.warning("Internal deep research service not available")
            return {
                "success": False,
                "error": "Internal deep research service not configured",
                "query": query,
            }

        try:
            logger.info(f"🔬 Agent deep research ({effort} effort): {query[:100]}...")

            # Use the internal deep research service (already integrated)
            result = await self.internal_deep_research.deep_research(
                query=query,
                effort=effort,
                conversation_history=None,  # Agents typically don't have conversation history
                user_id=user_id,
            )

            if not result.get("success"):
                return result  # Return error as-is

            # Extract results
            chunks = result.get("chunks", [])
            summary = result.get("summary", "")

            # Build formatted content with citations
            formatted_content = self._format_agent_research_result(
                query=query,
                summary=summary,
                chunks=chunks,
                system_prompt=system_prompt,
                agent_context=agent_context,
            )

            # Extract unique sources
            sources = list(
                {
                    chunk.get("metadata", {}).get("file_name", "unknown")
                    for chunk in chunks
                }
            )

            logger.info(
                f"✅ Agent deep research complete: {len(chunks)} chunks from "
                f"{result.get('unique_documents', 0)} documents"
            )

            return {
                "success": True,
                "content": formatted_content,  # Formatted for agent consumption
                "chunks": chunks,  # Raw chunks for additional processing
                "sources": sources,  # List of document names
                "summary": summary,  # Synthesized summary
                "unique_documents": result.get("unique_documents", 0),
                "total_chunks": result.get("total_chunks", 0),
                "query": query,
                "effort": effort,
            }

        except Exception as e:
            logger.error(f"Agent deep research failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
            }

    def _format_agent_research_result(
        self,
        query: str,
        summary: str,
        chunks: list[dict[str, Any]],
        system_prompt: str | None,
        agent_context: dict[str, Any] | None,
    ) -> str:
        """
        Format deep research results for agent consumption.

        Args:
            query: Original research query
            summary: Synthesized summary from deep research
            chunks: Retrieved context chunks
            system_prompt: Optional custom prompt (for context)
            agent_context: Optional agent metadata

        Returns:
            Formatted string with summary and citations

        """
        if not chunks:
            return "No relevant information found in internal knowledge base."

        # Start with summary
        formatted = f"**Research Summary:**\n{summary}\n\n"

        # Add sources section with citations
        formatted += "**Sources:**\n"
        unique_sources = {}
        for idx, chunk in enumerate(chunks[:10], 1):  # Limit to top 10 sources
            file_name = chunk.get("metadata", {}).get("file_name", "unknown")
            if file_name not in unique_sources:
                unique_sources[file_name] = idx
                # Add snippet for context
                content_preview = chunk.get("content", "")[:200].replace("\n", " ")
                formatted += f"\n[{idx}] **{file_name}**\n"
                formatted += f"    Excerpt: {content_preview}...\n"

        # Add metadata if agent context provided
        if agent_context:
            formatted += "\n**Research Context:**\n"
            for key, value in agent_context.items():
                formatted += f"- {key}: {value}\n"

        return formatted

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
