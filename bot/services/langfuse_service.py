"""
Langfuse service for LLM observability and tracing
"""

import logging
from typing import TYPE_CHECKING, Any

from config.settings import LangfuseSettings

if TYPE_CHECKING:
    from langfuse import Langfuse  # type: ignore[reportMissingImports]

logger = logging.getLogger(__name__)

# Optional import to handle cases where langfuse isn't installed
try:
    from langfuse import (  # type: ignore[reportMissingImports]
        Langfuse,  # type: ignore[import-untyped]
        observe,  # type: ignore[import-untyped]
    )

    _langfuse_available = True
    logger.info("Langfuse client available")
except ImportError:
    logger.warning("Langfuse not available - tracing will be disabled")
    _langfuse_available = False

    # Provide no-op decorator if langfuse is not available
    def observe(name: str = None, as_type: str = None, **kwargs):  # noqa: ARG001
        """No-op decorator when Langfuse is not available"""
        _ = (name, as_type, kwargs)  # Acknowledge but ignore parameters

        def decorator(func):
            return func

        return decorator


class LangfuseService:
    """
    Service for managing Langfuse observability integration
    """

    def __init__(self, settings: LangfuseSettings, environment: str = "development"):
        self.settings = settings
        self.environment = environment
        self.client: Langfuse | None = None
        self.enabled = settings.enabled and _langfuse_available
        self.current_trace = None
        self.current_session_id = None

        if self.enabled:
            self._initialize_client()

    def _initialize_client(self):
        """Initialize Langfuse client"""
        if not _langfuse_available:
            logger.warning("Langfuse not available - cannot initialize client")
            return

        try:
            # Only initialize if we have valid credentials
            if self.settings.public_key and self.settings.secret_key.get_secret_value():
                self.client = Langfuse(
                    public_key=self.settings.public_key,
                    secret_key=self.settings.secret_key.get_secret_value(),
                    host=self.settings.host,
                    debug=self.settings.debug,
                    environment=self.environment,  # Set environment for all traces
                )
                logger.info(
                    f"Langfuse client initialized successfully (environment: {self.environment})"
                )
            else:
                logger.warning("Langfuse credentials not provided - tracing disabled")
                self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse client: {e}")
            self.enabled = False

    def trace_llm_call(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, str]],
        response: str | None,
        metadata: dict[str, Any] | None = None,
        usage: dict[str, Any] | None = None,
        error: str | None = None,
        prompt_template_name: str | None = None,
        prompt_template_version: str | None = None,
    ):
        """
        Trace an LLM call with Langfuse

        Args:
            provider: LLM provider name (openai, anthropic, ollama)
            model: Model name
            messages: Input messages
            response: Generated response
            metadata: Additional metadata
            usage: Token usage information
            error: Error message if call failed
            prompt_template_name: Name of the Langfuse prompt template used
            prompt_template_version: Version of the prompt template used
        """
        if not self.enabled:
            return

        try:
            if not self.client:
                return

            # Prepare generation parameters
            generation_params = {
                "name": f"{provider}_llm_call",
                "model": model,
                "input": messages,
                "output": response,
                "metadata": {
                    "provider": provider,
                    "model": model,
                    "environment": self.environment,
                    **(metadata or {}),
                },
                "tags": [self.environment],  # Add environment as tag for filtering
                "usage": usage,
            }

            # Link to prompt template if provided
            if prompt_template_name:
                try:
                    # Get the prompt template from Langfuse to link it
                    if prompt_template_version:
                        prompt = self.client.get_prompt(
                            prompt_template_name, version=prompt_template_version
                        )
                    else:
                        prompt = self.client.get_prompt(prompt_template_name)

                    if prompt:
                        generation_params["prompt"] = prompt
                        logger.debug(
                            f"Linked generation to prompt template: {prompt_template_name}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Could not link prompt template {prompt_template_name}: {e}"
                    )

            # Create generation observation for LLM call
            generation = self.client.start_generation(**generation_params)

            if error:
                generation.end()

        except Exception as e:
            logger.error(f"Error tracing LLM call: {e}")

    def trace_retrieval(
        self,
        query: str,
        results: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ):
        """
        Trace RAG retrieval operation with enhanced document visibility

        Args:
            query: Search query
            results: Retrieved documents/chunks
            metadata: Additional metadata
        """
        if not self.enabled:
            return

        try:
            if not self.client:
                return

            # Prepare enhanced chunk data with full content for better visibility
            enhanced_chunks = []
            document_sources = set()

            for i, result in enumerate(results):
                content = result.get("content", "")
                chunk_metadata = result.get("metadata", {})

                # Track unique document sources
                doc_name = chunk_metadata.get("file_name") or result.get(
                    "document", f"chunk_{i}"
                )
                document_sources.add(doc_name)

                enhanced_chunk = {
                    "chunk_id": i + 1,
                    "content": content,  # Full content for better analysis
                    "content_preview": content[:300] + "..."
                    if len(content) > 300
                    else content,
                    "similarity_score": result.get("similarity", 0),
                    "document_source": doc_name,
                    "metadata": chunk_metadata,
                }

                enhanced_chunks.append(enhanced_chunk)

            # Create span for RAG retrieval with enhanced data
            span = self.client.start_span(
                name="rag_retrieval",
                input={
                    "query": query,
                    "query_length": len(query),
                },
                output={
                    "total_chunks_retrieved": len(results),
                    "unique_documents": len(document_sources),
                    "document_sources": list(document_sources),
                    "chunks": enhanced_chunks,  # Full chunk data
                    "retrieval_summary": {
                        "avg_similarity": (
                            sum(r.get("similarity", 0) for r in results) / len(results)
                            if results
                            else 0
                        ),
                        "top_similarity": max(
                            (r.get("similarity", 0) for r in results), default=0
                        ),
                        "min_similarity": min(
                            (r.get("similarity", 0) for r in results), default=0
                        ),
                    },
                },
                metadata={
                    "retrieval_type": metadata.get("retrieval_type", "unknown")
                    if metadata
                    else "unknown",
                    "vector_store": metadata.get("vector_store", "unknown")
                    if metadata
                    else "unknown",
                    "chunk_count": len(results),
                    "unique_document_count": len(document_sources),
                    "environment": self.environment,
                    **(metadata or {}),
                },
            )
            span.end()

            logger.debug(
                f"Enhanced retrieval trace created: {len(results)} chunks from {len(document_sources)} documents"
            )

        except Exception as e:
            logger.error(f"Error tracing retrieval: {e}")

    def trace_tool_execution(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: Any,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Trace tool execution (e.g., web search, API calls)

        Args:
            tool_name: Name of the tool executed
            tool_input: Input parameters to the tool
            tool_output: Output/results from the tool
            metadata: Additional metadata
        """
        if not self.enabled:
            return

        try:
            if not self.client:
                return

            # Create span for tool execution
            span = self.client.start_span(
                name=f"tool_{tool_name}",
                input={
                    "tool_name": tool_name,
                    "tool_parameters": tool_input,
                },
                output={
                    "tool_result": tool_output,
                    "result_count": len(tool_output)
                    if isinstance(tool_output, list)
                    else 1,
                },
                metadata={
                    "tool_type": tool_name,
                    "environment": self.environment,
                    **(metadata or {}),
                },
            )
            span.end()

            logger.debug(f"Tool execution trace created: {tool_name}")

        except Exception as e:
            logger.error(f"Error tracing tool execution: {e}")

    def trace_document_ingestion(
        self,
        documents: list[dict[str, Any]],
        success_count: int,
        error_count: int,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Trace document ingestion process to track what documents are being added to the knowledge base

        Args:
            documents: List of documents being ingested
            success_count: Number of successfully ingested chunks
            error_count: Number of failed chunks
            metadata: Additional metadata
        """
        if not self.enabled:
            return

        try:
            if not self.client:
                return

            # Prepare document summary for ingestion tracking
            document_summaries = []
            total_content_length = 0

            for i, doc in enumerate(
                documents[:10]
            ):  # Limit to first 10 for performance
                content = doc.get("content", "")
                doc_metadata = doc.get("metadata", {})
                total_content_length += len(content)

                doc_summary = {
                    "document_id": i + 1,
                    "file_name": doc_metadata.get("file_name", f"document_{i}"),
                    "file_type": doc_metadata.get("file_type", "unknown"),
                    "content_length": len(content),
                    "content_preview": content[:500] + "..."
                    if len(content) > 500
                    else content,
                    "metadata": doc_metadata,
                }
                document_summaries.append(doc_summary)

            # Create span for document ingestion
            span = self.client.start_span(
                name="document_ingestion",
                input={
                    "total_documents": len(documents),
                    "documents": document_summaries,
                },
                output={
                    "ingestion_results": {
                        "successful_chunks": success_count,
                        "failed_chunks": error_count,
                        "success_rate": success_count / (success_count + error_count)
                        if (success_count + error_count) > 0
                        else 0,
                    }
                },
                metadata={
                    "total_documents": len(documents),
                    "total_content_length": total_content_length,
                    "avg_document_size": total_content_length / len(documents)
                    if documents
                    else 0,
                    "successful_chunks": success_count,
                    "failed_chunks": error_count,
                    "environment": self.environment,
                    **(metadata or {}),
                },
            )
            span.end()

            logger.debug(
                f"Document ingestion trace created: {len(documents)} documents, {success_count} successful chunks"
            )

        except Exception as e:
            logger.error(f"Error tracing document ingestion: {e}")

    def create_rag_trace(
        self,
        user_id: str,
        conversation_id: str,
        query: str,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Create a comprehensive RAG trace that will contain both retrieval and generation spans

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            query: User query
            metadata: Additional metadata
        """
        if not self.enabled or not self.client:
            return None

        try:
            # Create a parent trace for the entire RAG operation
            trace = self.client.start_trace(
                name="rag_operation",
                input={"user_query": query},
                metadata={
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "operation_type": "rag_query",
                    "environment": self.environment,
                    **(metadata or {}),
                },
            )

            logger.debug(f"Created RAG trace for query: {query[:50]}...")
            return trace

        except Exception as e:
            logger.error(f"Error creating RAG trace: {e}")
            return None

    def start_conversation_trace(
        self,
        user_id: str,
        conversation_id: str,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Start a new conversation trace with session tracking

        Args:
            user_id: Slack user ID
            conversation_id: Conversation/thread ID for session grouping
            metadata: Additional metadata
        """
        if not self.enabled or not self.client:
            return

        try:
            # Create new trace using Langfuse v3.x API
            self.current_trace = self.client.start_span(
                name="slack_conversation",
                metadata={
                    "platform": "slack",
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "session_id": conversation_id,
                    "environment": self.environment,
                    **(metadata or {}),
                },
            )
            self.current_session_id = conversation_id
            logger.debug(f"Created Langfuse trace for session: {conversation_id}")
        except Exception as e:
            logger.error(f"Error starting conversation trace: {e}")

    def trace_conversation(
        self,
        user_id: str,
        conversation_id: str,
        user_message: str,
        bot_response: str,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Trace a complete conversation turn

        Args:
            user_id: Slack user ID
            conversation_id: Conversation/thread ID
            user_message: User's message
            bot_response: Bot's response
            metadata: Additional metadata
        """
        if not self.enabled or not self.client:
            return

        try:
            # Create or get existing trace for this conversation
            if not self.current_trace or self.current_session_id != conversation_id:
                self.start_conversation_trace(user_id, conversation_id, metadata)

            if self.current_trace:
                # Update the trace with conversation data using v3.x API
                try:
                    # Create a new generation within the trace for this conversation turn
                    generation = self.client.start_generation(
                        name="conversation_turn",
                        input={"user_message": user_message},
                        output={"bot_response": bot_response},
                        metadata={
                            "platform": "slack",
                            "conversation_id": conversation_id,
                            "environment": self.environment,
                            **(metadata or {}),
                        },
                    )
                    generation.end()
                    logger.debug(
                        f"Updated conversation trace for session: {conversation_id}"
                    )
                except Exception as e:
                    logger.error(f"Error updating conversation generation: {e}")

        except Exception as e:
            logger.error(f"Error tracing conversation: {e}")

    def score_response(
        self,
        score_name: str,
        value: float,
        comment: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Add a score to the current trace/observation

        Args:
            score_name: Name of the score (e.g., "quality", "helpfulness")
            value: Score value (typically 0-1 or 1-5)
            comment: Optional comment about the score
            metadata: Additional metadata
        """
        if not self.enabled:
            return

        try:
            if self.enabled and self.client:
                # TODO: score_current_trace API changed in newer Langfuse versions
                # This method needs to be updated to match the current Langfuse API
                logger.debug(
                    f"Score {score_name}={value} (not implemented for current Langfuse version)"
                )
        except Exception as e:
            logger.error(f"Error adding score: {e}")

    def flush(self):
        """Flush pending traces to Langfuse"""
        if self.enabled and self.client:
            try:
                self.client.flush()
            except Exception as e:
                logger.error(f"Error flushing Langfuse traces: {e}")

    def get_prompt_template(
        self, template_name: str, version: str | None = None
    ) -> str | None:
        """
        Fetch a prompt template from Langfuse

        Args:
            template_name: Name of the prompt template in Langfuse
            version: Specific version to fetch (uses latest if None)

        Returns:
            The prompt template string or None if not found/failed
        """
        if not self.enabled or not self.client:
            logger.warning("Langfuse not enabled - cannot fetch prompt template")
            return None

        try:
            # Use Langfuse client to fetch prompt template
            if version:
                prompt = self.client.get_prompt(template_name, version=version)
            else:
                prompt = self.client.get_prompt(template_name)

            if prompt and hasattr(prompt, "prompt"):
                logger.debug(f"Fetched prompt template '{template_name}' from Langfuse")
                return prompt.prompt
            else:
                logger.warning(
                    f"Prompt template '{template_name}' not found in Langfuse"
                )
                return None

        except Exception as e:
            logger.error(f"Error fetching prompt template '{template_name}': {e}")
            return None

    async def get_lifetime_stats(
        self, start_date: str = "2025-10-21"
    ) -> dict[str, Any]:
        """
        Get lifetime conversation statistics from Langfuse API since start_date

        Args:
            start_date: Start date in YYYY-MM-DD format (default: Oct 21, 2025)

        Returns:
            Dictionary with:
            - total_interactions: Total number of observations (LLM calls, RAG, tools, etc)
            - unique_sessions: Number of unique conversation threads
            - start_date: The start date used for the query
        """
        if not self.enabled or not self.settings.public_key:
            return {
                "total_interactions": 0,
                "unique_sessions": 0,
                "start_date": start_date,
                "error": "Langfuse not enabled or credentials missing",
            }

        try:
            from datetime import datetime

            import aiohttp

            # Langfuse API endpoint
            api_base = self.settings.host.rstrip("/")

            # Convert start_date to timestamp
            start_datetime = datetime.fromisoformat(f"{start_date}T00:00:00Z")

            # Use basic auth with public_key as username and secret_key as password
            auth = aiohttp.BasicAuth(
                login=self.settings.public_key,
                password=self.settings.secret_key.get_secret_value(),
            )

            async with aiohttp.ClientSession() as session:
                # Query observations endpoint for total interactions (all LLM calls, RAG, tools, etc)
                observations_url = f"{api_base}/api/public/observations"
                params = {
                    "fromTimestamp": start_datetime.isoformat(),
                    "page": 1,
                    "limit": 1,  # We only need the count
                }

                async with session.get(
                    observations_url, auth=auth, params=params, timeout=10
                ) as response:
                    if response.status != 200:
                        logger.error(
                            f"Langfuse API error: {response.status} - {await response.text()}"
                        )
                        return {
                            "total_interactions": 0,
                            "unique_sessions": 0,
                            "start_date": start_date,
                            "error": f"API returned {response.status}",
                        }

                    data = await response.json()
                    total_interactions = data.get("meta", {}).get("totalItems", 0)

                # Query sessions endpoint for unique sessions
                sessions_url = f"{api_base}/api/public/sessions"
                async with session.get(
                    sessions_url, auth=auth, params=params, timeout=10
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Could not fetch sessions: {response.status}")
                        unique_sessions = 0
                    else:
                        sessions_data = await response.json()
                        unique_sessions = sessions_data.get("meta", {}).get(
                            "totalItems", 0
                        )

                logger.info(
                    f"Langfuse lifetime stats: {total_interactions} observations, {unique_sessions} unique sessions since {start_date}"
                )

                return {
                    "total_interactions": total_interactions,
                    "unique_sessions": unique_sessions,
                    "start_date": start_date,
                }

        except Exception as e:
            logger.error(f"Error fetching Langfuse lifetime stats: {e}")
            return {
                "total_interactions": 0,
                "unique_sessions": 0,
                "start_date": start_date,
                "error": str(e),
            }

    async def close(self):
        """Close Langfuse client and flush pending traces"""
        if self.enabled and self.client:
            try:
                self.client.flush()
                logger.info("Langfuse service closed and traces flushed")
            except Exception as e:
                logger.error(f"Error closing Langfuse service: {e}")


# Global instance - will be initialized by the main service
langfuse_service: LangfuseService | None = None


def get_langfuse_service() -> LangfuseService | None:
    """Get the global Langfuse service instance"""
    return langfuse_service


def initialize_langfuse_service(
    settings: LangfuseSettings, environment: str = "development"
) -> LangfuseService:
    """Initialize the global Langfuse service"""
    global langfuse_service  # noqa: PLW0603
    langfuse_service = LangfuseService(settings, environment)
    return langfuse_service
