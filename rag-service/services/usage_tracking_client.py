"""Usage tracking client for RAG service.

Sends usage data to the bot service or writes directly to shared database.
"""

import logging
import os

import httpx
from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class UsageTrackingClient:
    """Client for tracking usage from RAG service.

    Tracks LibreChat and other UI interactions for analytics.
    """

    def __init__(self, bot_service_url: str | None = None):
        """Initialize the usage tracking client.

        Args:
            bot_service_url: URL of bot service for usage tracking API
        """
        self.bot_service_url = bot_service_url or os.getenv("BOT_SERVICE_URL", "http://bot:8080")
        self.logger = logging.getLogger(self.__class__.__name__)

    async def track_librechat_usage(
        self,
        user_id: str,
        conversation_id: str,
        agent_used: str | None = None,
        deep_search: str | None = None,
        interaction_type: str = "message",
        email: str | None = None,
    ) -> bool:
        """Track LibreChat usage.

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            agent_used: Agent name if agent was used
            deep_search: Deep search enabled (true/false)
            interaction_type: Type of interaction
            email: User email

        Returns:
            True if tracking succeeded
        """
        with tracer.start_as_current_span(
            "rag.usage_tracking.librechat",
            attributes={
                "user_id": user_id,
                "conversation_id": conversation_id,
                "agent_used": agent_used or "",
                "deep_search": deep_search or "",
                "interaction_type": interaction_type,
            },
        ) as span:
            try:
                # Try to call bot service API to track usage
                payload = {
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "agent_used": agent_used,
                    "deep_search": deep_search,
                    "interaction_type": interaction_type,
                    "email": email,
                    "source": "librechat",
                }

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.bot_service_url}/api/v1/usage/librechat",
                        json=payload,
                        timeout=5.0,
                    )

                    success = response.status_code == 200
                    span.set_attribute("tracking.success", success)
                    return success

            except Exception as e:
                self.logger.debug(f"Failed to track LibreChat usage via API: {e}")
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                # Non-blocking - don't fail the request if tracking fails
                return False


# Global instance
_usage_client: UsageTrackingClient | None = None


def get_usage_client() -> UsageTrackingClient:
    """Get or create global usage tracking client."""
    global _usage_client
    if _usage_client is None:
        _usage_client = UsageTrackingClient()
    return _usage_client
