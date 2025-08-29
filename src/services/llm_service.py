"""
LLM Service with RAG support - backward compatible interface
"""

import logging

from config.settings import Settings
from services.rag_service import RAGService
from services.user_prompt_service import UserPromptService

logger = logging.getLogger(__name__)


class LLMService:
    """
    Enhanced LLM service with RAG capabilities
    
    Maintains backward compatibility with the original interface while
    adding support for direct LLM providers and vector-based retrieval
    """

    def __init__(self, settings: Settings, user_prompt_service: UserPromptService | None = None):
        self.settings = settings
        self.user_prompt_service = user_prompt_service
        self.rag_service = RAGService(settings)

        # Legacy properties for backward compatibility
        self.model = settings.llm.model
        self.api_url = f"{settings.llm.provider} API"  # For logging compatibility

        logger.info(f"Initialized LLM service with provider: {settings.llm.provider}")

    async def initialize(self):
        """Initialize RAG service"""
        await self.rag_service.initialize()

    async def get_response(
        self,
        messages: list[dict[str, str]],
        user_id: str | None = None,
        use_rag: bool = True
    ) -> str | None:
        """
        Get response from LLM with optional RAG enhancement
        
        Args:
            messages: Conversation history
            user_id: User ID for custom system prompts
            use_rag: Whether to use RAG retrieval (default: True)
            
        Returns:
            Generated response or None if failed
        """
        try:
            # Get user's custom system prompt if available
            system_message = None
            if user_id and self.user_prompt_service:
                try:
                    custom_prompt = await self.user_prompt_service.get_user_prompt(user_id)
                    if custom_prompt:
                        system_message = custom_prompt
                        logger.info(f"Using custom system prompt for user {user_id}")
                except Exception as e:
                    logger.warning(f"Failed to get custom prompt for user {user_id}: {e}")

            # Extract the current query (last user message)
            current_query = None
            conversation_history = []

            for msg in messages:
                if msg.get("role") == "user":
                    current_query = msg.get("content", "")
                conversation_history.append(msg)

            if not current_query:
                logger.warning("No user query found in messages")
                return None

            # Generate response using RAG service
            response = await self.rag_service.generate_response(
                query=current_query,
                conversation_history=conversation_history[:-1],  # Exclude current query
                system_message=system_message,
                use_rag=use_rag
            )

            return response

        except Exception as e:
            logger.error(f"Error in LLM service: {e}")
            return None

    async def get_response_without_rag(
        self,
        messages: list[dict[str, str]],
        user_id: str | None = None
    ) -> str | None:
        """Get response without RAG retrieval"""
        return await self.get_response(messages, user_id, use_rag=False)

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
        logger.info("LLM service closed")
