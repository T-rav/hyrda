"""Prompt service for profiler agent.

Lightweight prompt service that can optionally fetch prompts from Langfuse
without depending on bot/ services.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class PromptService:
    """Lightweight prompt service for custom agents."""

    def __init__(self):
        """Initialize prompt service with Langfuse credentials from environment."""
        self.langfuse_enabled = os.getenv("LANGFUSE_ENABLED", "").lower() == "true"
        self.langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        self.langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        self.langfuse_host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        self._prompt_cache: dict[str, str] = {}

        # Only import Langfuse if enabled and credentials available
        self._langfuse = None
        if (
            self.langfuse_enabled
            and self.langfuse_public_key
            and self.langfuse_secret_key
        ):
            try:
                from langfuse import Langfuse

                self._langfuse = Langfuse(
                    public_key=self.langfuse_public_key,
                    secret_key=self.langfuse_secret_key,
                    host=self.langfuse_host,
                )
                logger.info("Langfuse prompt service initialized")
            except ImportError:
                logger.warning("Langfuse library not installed - prompts will use local fallbacks")
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse: {e}")

    def get_prompt(
        self,
        template_name: str,
        version: str | None = None,
        fallback: str | None = None,
    ) -> str | None:
        """Get a prompt template from Langfuse.

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
            logger.debug(f"Using cached prompt: {template_name}")
            return self._prompt_cache[cache_key]

        # Try Langfuse if available
        if self._langfuse:
            try:
                prompt_obj = self._langfuse.get_prompt(template_name, version=version)
                if prompt_obj and hasattr(prompt_obj, "prompt"):
                    prompt_text = prompt_obj.prompt
                    self._prompt_cache[cache_key] = prompt_text
                    logger.info(f"Fetched prompt from Langfuse: {template_name}")
                    return prompt_text
            except Exception as e:
                logger.warning(f"Failed to fetch prompt '{template_name}' from Langfuse: {e}")

        # Return fallback or None
        if fallback:
            logger.info(f"Using fallback for prompt: {template_name}")
            return fallback

        logger.warning(f"Prompt '{template_name}' not found and no fallback provided")
        return None

    def clear_cache(self):
        """Clear the prompt cache."""
        self._prompt_cache.clear()
        logger.debug("Prompt cache cleared")


# Global instance
_prompt_service: PromptService | None = None


def get_prompt_service() -> PromptService:
    """Get or create the global prompt service instance."""
    global _prompt_service  # noqa: PLW0603
    if _prompt_service is None:
        _prompt_service = PromptService()
    return _prompt_service
