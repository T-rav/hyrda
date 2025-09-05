"""
Langfuse service for LLM observability and tracing
"""

import logging
from typing import TYPE_CHECKING, Any

from config.settings import LangfuseSettings

if TYPE_CHECKING:
    from langfuse import Langfuse

logger = logging.getLogger(__name__)

# Optional import to handle cases where langfuse isn't installed
try:
    from langfuse import Langfuse  # type: ignore[import-untyped]

    _langfuse_available = True
    logger.info("Langfuse client available")
except ImportError:
    logger.warning("Langfuse not available - tracing will be disabled")
    _langfuse_available = False


# Provide no-op decorator if langfuse is not available or decorators are missing
def observe(name: str = None, as_type: str = None, **kwargs):
    """Simple no-op decorator since langfuse.openai handles tracing automatically"""

    def decorator(func):
        return func

    return decorator


class MockLangfuseContext:
    """Mock context for compatibility"""

    def update_current_trace(self, **kwargs):
        pass

    def update_current_observation(self, **kwargs):
        pass

    def score_current_trace(self, **kwargs):
        pass

    def score_current_observation(self, **kwargs):
        pass


# Use mock context since decorators aren't available in this langfuse version
langfuse_context = MockLangfuseContext()


class LangfuseService:
    """
    Service for managing Langfuse observability integration
    """

    def __init__(self, settings: LangfuseSettings):
        self.settings = settings
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
                )
                logger.info("Langfuse client initialized successfully")
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
        """
        if not self.enabled:
            return

        try:
            # Update current observation with LLM details
            langfuse_context.update_current_observation(
                name=f"{provider}_llm_call",
                model=model,
                input=messages,
                output=response,
                metadata={
                    "provider": provider,
                    "model": model,
                    **(metadata or {}),
                },
                usage=usage,
                level="ERROR" if error else "DEFAULT",
            )

            if error:
                langfuse_context.update_current_observation(status_message=error)

        except Exception as e:
            logger.error(f"Error tracing LLM call: {e}")

    def trace_retrieval(
        self,
        query: str,
        results: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ):
        """
        Trace RAG retrieval operation

        Args:
            query: Search query
            results: Retrieved documents/chunks
            metadata: Additional metadata
        """
        if not self.enabled:
            return

        try:
            langfuse_context.update_current_observation(
                name="rag_retrieval",
                input={"query": query},
                output={
                    "retrieved_chunks": len(results),
                    "chunks": [
                        {
                            "content": result.get("content", "")[:200] + "...",
                            "similarity": result.get("similarity", 0),
                            "metadata": result.get("metadata", {}),
                        }
                        for result in results[:5]  # Limit to first 5 for brevity
                    ],
                },
                metadata={
                    "chunk_count": len(results),
                    "avg_similarity": (
                        sum(r.get("similarity", 0) for r in results) / len(results)
                        if results
                        else 0
                    ),
                    **(metadata or {}),
                },
            )
        except Exception as e:
            logger.error(f"Error tracing retrieval: {e}")

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
            # TODO: Fix Langfuse trace creation - API method unclear
            # Temporarily disable trace creation to avoid errors
            logger.debug(
                f"Langfuse trace creation disabled - would create trace for session: {conversation_id}"
            )
            # self.current_trace = self.client.trace({
            #     "name": "slack_conversation",
            #     "user_id": user_id,
            #     "session_id": conversation_id,
            #     "metadata": {
            #         "platform": "slack",
            #         "conversation_id": conversation_id,
            #         **(metadata or {}),
            #     },
            # })
            # self.current_session_id = conversation_id
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
                # Update the trace with conversation data
                self.current_trace.update(
                    input={"user_message": user_message},
                    output={"bot_response": bot_response},
                    metadata={
                        "platform": "slack",
                        "conversation_id": conversation_id,
                        **(metadata or {}),
                    },
                )
                logger.debug(
                    f"Updated conversation trace for session: {conversation_id}"
                )

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
            langfuse_context.score_current_trace(
                name=score_name,
                value=value,
                comment=comment,
                metadata=metadata,
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


def initialize_langfuse_service(settings: LangfuseSettings) -> LangfuseService:
    """Initialize the global Langfuse service"""
    global langfuse_service  # noqa: PLW0603
    langfuse_service = LangfuseService(settings)
    return langfuse_service
