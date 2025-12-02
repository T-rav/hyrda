"""User prompt management for bot message handlers.

Handles retrieval and customization of system prompts with user context injection.
"""

import logging

from services.prompt_service import get_prompt_service

logger = logging.getLogger(__name__)


def get_user_system_prompt(user_id: str | None = None) -> str:
    """Get the system prompt with user context injected.

    Fetches base prompt from PromptService and optionally injects user-specific
    context to personalize responses.

    Args:
        user_id: Slack user ID to look up and inject context for

    Returns:
        System prompt with user context
    """
    prompt_service = get_prompt_service()
    base_prompt = ""

    if prompt_service:
        base_prompt = prompt_service.get_system_prompt()
    else:
        # Ultimate fallback if PromptService is not available
        logger.warning("PromptService not available, using minimal fallback prompt")
        base_prompt = "I'm Insight Mesh, your AI assistant. I help you find information from your organization's knowledge base and provide intelligent assistance with your questions."

    # Inject user context if user_id provided
    if user_id:
        try:
            from services.user_service import get_user_service

            user_service = get_user_service()
            user_info = user_service.get_user_info(user_id)

            if user_info:
                user_context = "\n\n**Current User Context:**\n"
                user_context += f"- Name: {user_info.get('real_name') or user_info.get('display_name', 'Unknown')}\n"
                if user_info.get("email_address"):
                    user_context += f"- Email: {user_info['email_address']}\n"

                user_context += "\nWhen responding, you can personalize your responses knowing who the user is. Address them by name when appropriate."

                return base_prompt + user_context
        except Exception as e:
            logger.error(f"Error injecting user context: {e}")

    return base_prompt
