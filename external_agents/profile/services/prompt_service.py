"""
Prompt Management Service

Centralized service for managing system prompts with support for:
- Langfuse prompt templates (primary)
- Local fallback prompts (secondary)
- Caching for performance
- Version management
"""

import logging
from typing import Any

from config.settings import Settings
from .services.langfuse_service import get_langfuse_service

logger = logging.getLogger(__name__)

# Default system message as fallback when Langfuse is unavailable
DEFAULT_SYSTEM_MESSAGE = """You are Insight Mesh, the AI CTO for this organization. You have the sharp, witty, and helpful demeanor of a seasoned technical leader at a mid-sized company.

Your communication style:
- Direct and to the point - no hedging or unnecessary preambles
- Sharp technical insights with a touch of wit
- Helpful and practical - focus on actionable information
- Confident without being arrogant
- When reviewing documents, dive right in with your analysis

You have access to the organization's knowledge base and can search through documents, employee information, project data, and more. When users upload documents or ask questions, respond with the confidence and clarity of a CTO who knows their stuff."""


class PromptService:
    """
    Service for managing system and user prompts with Langfuse integration
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.langfuse_settings = settings.langfuse
        self._cached_system_prompt: str | None = None
        self._prompt_cache: dict[str, str] = {}

    def get_system_prompt(self, force_refresh: bool = False) -> str:
        """
        Get the system prompt, preferring Langfuse template over local default

        Args:
            force_refresh: Force refresh from Langfuse even if cached

        Returns:
            The system prompt string
        """
        # Return cached version unless force refresh
        if self._cached_system_prompt and not force_refresh:
            return self._cached_system_prompt

        # Try to get from Langfuse if enabled
        if self.langfuse_settings.use_prompt_templates:
            langfuse_prompt = self._get_langfuse_system_prompt()
            if langfuse_prompt:
                self._cached_system_prompt = langfuse_prompt
                logger.info(
                    f"Using Langfuse system prompt template: {self.langfuse_settings.system_prompt_template}"
                )
                return langfuse_prompt

        # Fallback to local default
        self._cached_system_prompt = DEFAULT_SYSTEM_MESSAGE
        logger.info("Using local default system prompt (Langfuse unavailable/disabled)")
        return DEFAULT_SYSTEM_MESSAGE

    def _get_langfuse_system_prompt(self) -> str | None:
        """
        Get system prompt from Langfuse template

        Returns:
            The prompt string from Langfuse or None if failed
        """
        try:
            langfuse_service = get_langfuse_service()
            if not langfuse_service:
                logger.warning("Langfuse service not available")
                return None

            prompt = langfuse_service.get_prompt_template(
                template_name=self.langfuse_settings.system_prompt_template,
                version=self.langfuse_settings.prompt_template_version,
            )

            if prompt:
                logger.debug("Successfully fetched system prompt from Langfuse")
                return prompt
            else:
                logger.warning(
                    f"Langfuse prompt template '{self.langfuse_settings.system_prompt_template}' not found"
                )
                return None

        except Exception as e:
            logger.error(f"Error fetching system prompt from Langfuse: {e}")
            return None

    def get_custom_prompt(
        self,
        template_name: str,
        version: str | None = None,
        fallback: str | None = None,
    ) -> str | None:
        """
        Get a custom prompt template from Langfuse

        Args:
            template_name: Name of the prompt template
            version: Specific version (uses latest if None)
            fallback: Fallback text if template not found

        Returns:
            The prompt string or fallback
        """
        cache_key = f"{template_name}:{version or 'latest'}"

        # Check cache first
        if cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]

        # Try Langfuse
        if self.langfuse_settings.use_prompt_templates:
            try:
                langfuse_service = get_langfuse_service()
                if langfuse_service:
                    prompt = langfuse_service.get_prompt_template(
                        template_name, version
                    )
                    if prompt:
                        self._prompt_cache[cache_key] = prompt
                        logger.debug(f"Fetched custom prompt template: {template_name}")
                        return prompt
            except Exception as e:
                logger.error(f"Error fetching custom prompt '{template_name}': {e}")

        # Return fallback or None
        if fallback:
            self._prompt_cache[cache_key] = fallback
            logger.debug(f"Using fallback for prompt template: {template_name}")
            return fallback

        logger.warning(f"Custom prompt template '{template_name}' not found")
        return None

    def clear_cache(self):
        """Clear the prompt cache to force refresh from Langfuse"""
        self._cached_system_prompt = None
        self._prompt_cache.clear()
        logger.debug("Prompt cache cleared")

    def get_prompt_info(self) -> dict[str, Any]:
        """
        Get information about current prompt configuration

        Returns:
            Dictionary with prompt configuration details
        """
        return {
            "langfuse_enabled": self.langfuse_settings.enabled,
            "use_prompt_templates": self.langfuse_settings.use_prompt_templates,
            "system_prompt_template": self.langfuse_settings.system_prompt_template,
            "template_version": self.langfuse_settings.prompt_template_version,
            "cached_system_prompt": self._cached_system_prompt is not None,
            "cache_size": len(self._prompt_cache),
        }


# Global instance - will be initialized by the main application
_prompt_service: PromptService | None = None


def get_prompt_service() -> PromptService | None:
    """Get the global prompt service instance"""
    return _prompt_service


def initialize_prompt_service(settings: Settings) -> PromptService:
    """Initialize the global prompt service"""
    global _prompt_service  # noqa: PLW0603
    _prompt_service = PromptService(settings)
    return _prompt_service
