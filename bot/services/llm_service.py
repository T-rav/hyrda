"""
LLM Service with RAG support - backward compatible interface
"""

import logging
import time

from config.settings import Settings

# Hybrid search removed
from services.langfuse_service import (
    initialize_langfuse_service,
    observe,
)
from services.metrics_service import get_metrics_service
from services.prompt_service import PromptService
from services.rag_service import RAGService

logger = logging.getLogger(__name__)


class LLMService:
    """
    Enhanced LLM service with RAG capabilities

    Maintains backward compatibility with the original interface while
    adding support for direct LLM providers and vector-based retrieval
    """

    def __init__(self, settings: Settings):
        self.settings = settings

        # Initialize prompt service for system prompts
        self.prompt_service = PromptService(settings)

        # Hybrid search removed - always use standard RAG
        self.rag_service = RAGService(settings)
        self.use_hybrid = False
        logger.info("Using standard RAG service")

        # Initialize Langfuse service
        self.langfuse_service = initialize_langfuse_service(
            settings.langfuse, settings.environment
        )

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
        await self.rag_service.initialize()

    @observe(name="llm_service_response", as_type="generation")
    async def get_response(
        self,
        messages: list[dict[str, str]],
        user_id: str | None = None,
        use_rag: bool = True,
        conversation_id: str | None = None,
        current_query: str | None = None,
        document_content: str | None = None,
        document_filename: str | None = None,
        conversation_cache=None,
    ) -> str | None:
        """
        Get response from LLM with optional RAG enhancement

        Args:
            messages: Conversation history
            user_id: User ID for custom system prompts
            use_rag: Whether to use RAG retrieval (default: True)
            conversation_id: Conversation/thread ID for tracing
            current_query: Override for the current user query
            document_content: Content of uploaded document for context
            document_filename: Name of uploaded document
            conversation_cache: Optional conversation cache for summary management

        Returns:
            Generated response or None if failed
        """
        metrics_service = get_metrics_service()
        start_time = time.time()

        try:
            # Get system prompt with user context injected
            from handlers.prompt_manager import get_user_system_prompt

            system_message = get_user_system_prompt(user_id)

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
                document_content=document_content,
                document_filename=document_filename,
                conversation_cache=conversation_cache,
            )

            # NOTE: conversation_turn tracking moved to message_handlers.py to avoid double-counting
            # Each message handler (handle_message, handle_agent_command) calls trace_conversation()
            # Tracking here would create duplicate observations for every user message

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
            messages,
            user_id,
            use_rag=False,
            conversation_id=conversation_id,
            document_content=None,
            document_filename=None,
        )

    async def ingest_documents(self, documents: list[dict]) -> tuple[int, int]:
        """
        Ingest documents into the knowledge base

        Args:
            documents: List of documents with 'content' and optional 'metadata'

        Returns:
            Tuple of (success_count, error_count)
        """
        try:
            return await self.rag_service.ingest_documents(documents)
        except Exception as e:
            logger.error(f"Error ingesting documents: {e}")
            return (0, len(documents))

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


async def create_llm_service(llm_settings) -> LLMService:
    """
    Factory function to create and initialize an LLM service instance

    Args:
        llm_settings: LLM settings object

    Returns:
        Initialized LLMService instance
    """
    # Create a minimal settings object with just the LLM settings
    # This is needed for contextual retrieval functionality
    from config.settings import Settings

    # Create a full settings object to ensure all dependencies are available
    try:
        settings = Settings()
        # Override with provided LLM settings if different
        if hasattr(llm_settings, "model"):
            settings.llm = llm_settings
    except Exception:
        # Fallback: create minimal settings structure
        class MinimalSettings:
            """MinimalSettings class."""

            def __init__(self):
                self.llm = llm_settings
                # Add minimal required attributes
                self.langfuse = type("obj", (object,), {"enabled": False})()
                self.vector = type("obj", (object,), {"enabled": True})()

        settings = MinimalSettings()

    # Create and initialize the service
    service = LLMService(settings)
    await service.initialize()
    return service
