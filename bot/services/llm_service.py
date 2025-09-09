"""
LLM Service with RAG support - backward compatible interface
"""

import logging
import time

from config.settings import Settings
from services.hybrid_rag_service import create_hybrid_rag_service
from services.langfuse_service import (
    get_langfuse_service,
    initialize_langfuse_service,
    observe,
)
from services.metrics_service import get_metrics_service
from services.rag_service import RAGService  # Fallback for non-hybrid mode

logger = logging.getLogger(__name__)


class LLMService:
    """
    Enhanced LLM service with RAG capabilities

    Maintains backward compatibility with the original interface while
    adding support for direct LLM providers and vector-based retrieval
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        # Use hybrid RAG service if enabled, otherwise fallback to single vector
        if getattr(settings, "hybrid", None) and settings.hybrid.enabled:
            self.rag_service = None  # Will be initialized in async initialize method
            self.use_hybrid = True
            logger.info("Using hybrid RAG service (Pinecone + Elasticsearch)")
        else:
            self.rag_service = RAGService(settings)
            self.use_hybrid = False
            logger.info("Using single vector RAG service")

        # Initialize Langfuse service
        self.langfuse_service = initialize_langfuse_service(settings.langfuse)

        # Legacy properties for backward compatibility
        self.model = settings.llm.model
        self.api_url = f"{settings.llm.provider} API"  # For logging compatibility

        logger.info(f"Initialized LLM service with provider: {settings.llm.provider}")
        if self.langfuse_service.enabled:
            logger.info("Langfuse observability enabled")
        else:
            logger.info("Langfuse observability disabled")

    async def initialize(self):
        """Initialize RAG service"""
        if self.use_hybrid:
            self.rag_service = await create_hybrid_rag_service(self.settings)
        else:
            await self.rag_service.initialize()

    @observe(name="llm_service_response", as_type="generation")
    async def get_response(
        self,
        messages: list[dict[str, str]],
        user_id: str | None = None,
        use_rag: bool = True,
        conversation_id: str | None = None,
        current_query: str | None = None,
    ) -> str | None:
        """
        Get response from LLM with optional RAG enhancement

        Args:
            messages: Conversation history
            user_id: User ID for custom system prompts
            use_rag: Whether to use RAG retrieval (default: True)
            conversation_id: Conversation/thread ID for tracing

        Returns:
            Generated response or None if failed
        """
        langfuse_service = get_langfuse_service()
        metrics_service = get_metrics_service()
        start_time = time.time()

        try:
            # No custom system prompts - using default only
            system_message = None

            # Use provided current_query or extract from messages
            if current_query:
                # Use the explicitly provided current query
                query_to_use = current_query
                conversation_history = messages  # Use full history for context
            else:
                # Fallback: extract the current query (last user message)
                query_to_use = None
                conversation_history = []

                for msg in messages:
                    if msg.get("role") == "user":
                        query_to_use = msg.get("content", "")
                    conversation_history.append(msg)

            if not query_to_use:
                logger.warning("No user query found in messages")
                return None

            # Generate response using RAG service
            response = await self.rag_service.generate_response(
                query=query_to_use,
                conversation_history=conversation_history[:-1]
                if not current_query
                else conversation_history,
                system_message=system_message,
                use_rag=use_rag,
                session_id=conversation_id,
                user_id=user_id,
            )

            # Trace complete conversation with Langfuse
            if langfuse_service and user_id and response:
                langfuse_service.trace_conversation(
                    user_id=user_id,
                    conversation_id=conversation_id or "unknown",
                    user_message=current_query,
                    bot_response=response,
                    metadata={
                        "rag_enabled": use_rag,
                        "custom_prompt_used": system_message is not None,
                        "message_count": len(conversation_history),
                        "llm_provider": self.settings.llm.provider,
                        "llm_model": self.settings.llm.model,
                    },
                )

            # Record metrics
            if metrics_service and response:
                duration = time.time() - start_time
                token_count = len(response.split()) * 1.3  # Rough estimate
                metrics_service.record_llm_request(
                    provider=self.settings.llm.provider,
                    model=self.settings.llm.model,
                    status="success",
                    duration=duration,
                    tokens=int(token_count),
                )

            return response

        except Exception as e:
            logger.error(f"Error in LLM service: {e}")

            # Record error metric
            if metrics_service:
                metrics_service.record_llm_request(
                    provider=self.settings.llm.provider,
                    model=self.settings.llm.model,
                    status="error",
                )

            return None

    async def get_response_without_rag(
        self,
        messages: list[dict[str, str]],
        user_id: str | None = None,
        conversation_id: str | None = None,
    ) -> str | None:
        """Get response without RAG retrieval"""
        return await self.get_response(
            messages, user_id, use_rag=False, conversation_id=conversation_id
        )

    async def ingest_documents(self, documents: list[dict]) -> int:
        """
        Ingest documents into the knowledge base

        Args:
            documents: List of documents with 'content' and optional 'metadata'

        Returns:
            Number of chunks ingested
        """
        if not self.settings.vector.enabled:
            logger.warning("Vector storage disabled - cannot ingest documents")
            return 0

        try:
            return await self.rag_service.ingest_documents(documents)
        except Exception as e:
            logger.error(f"Error ingesting documents: {e}")
            return 0

    async def get_system_status(self) -> dict:
        """Get system status information"""
        return await self.rag_service.get_system_status()

    async def close(self):
        """Clean up resources"""
        await self.rag_service.close()

        # Close Langfuse service
        if self.langfuse_service:
            await self.langfuse_service.close()

        logger.info("LLM service closed")
