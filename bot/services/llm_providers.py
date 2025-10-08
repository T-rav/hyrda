"""
LLM provider implementations for OpenAI chat completion spec
"""

import logging
import time
from abc import ABC, abstractmethod

try:
    from langfuse.openai import AsyncOpenAI  # type: ignore[reportMissingImports]
except ImportError:
    from openai import AsyncOpenAI

from config.settings import LLMSettings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    def __init__(self, settings: LLMSettings):
        self.settings = settings
        self.model = settings.model
        self.temperature = settings.temperature
        self.max_tokens = settings.max_tokens

    @abstractmethod
    async def get_response(
        self,
        messages: list[dict[str, str]],
        system_message: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        prompt_template_name: str | None = None,
        prompt_template_version: str | None = None,
    ) -> str | None:
        """Generate a response from the LLM"""
        pass

    @abstractmethod
    async def close(self):
        """Clean up resources"""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI API provider"""

    def __init__(self, settings: LLMSettings):
        super().__init__(settings)

        # Configure client
        client_kwargs = {
            "api_key": settings.api_key.get_secret_value(),
        }

        if settings.base_url:
            client_kwargs["base_url"] = settings.base_url

        self.client = AsyncOpenAI(**client_kwargs)

    async def get_response(
        self,
        messages: list[dict[str, str]],
        system_message: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        prompt_template_name: str | None = None,
        prompt_template_version: str | None = None,
    ) -> str | None:
        """Get response from OpenAI API"""
        start_time = time.time()

        try:
            # Prepare messages
            formatted_messages = []

            if system_message:
                formatted_messages.append({"role": "system", "content": system_message})

            # Add conversation history
            formatted_messages.extend(messages)

            logger.info(
                "Calling OpenAI API",
                extra={
                    "model": self.model,
                    "message_count": len(formatted_messages),
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "event_type": "openai_api_request",
                },
            )

            # Prepare request parameters
            # Note: Newer models have parameter restrictions:
            # - gpt-4o and newer: use max_completion_tokens (max_tokens deprecated)
            # - gpt-5-mini and o1/o3: only support temperature=1.0 (default)
            is_reasoning_model = any(
                model_id in self.model.lower() for model_id in ["gpt-5", "o1-", "o3-"]
            )

            request_params = {
                "model": self.model,
                "messages": formatted_messages,  # type: ignore[arg-type]
                "max_completion_tokens": self.max_tokens,
            }

            # Only add temperature for non-reasoning models
            if not is_reasoning_model:
                request_params["temperature"] = self.temperature

            # Add Langfuse tracking metadata if provided
            metadata = {}
            if session_id:
                metadata["langfuse_session_id"] = session_id
            if user_id:
                metadata["langfuse_user_id"] = user_id

            if metadata:
                request_params["metadata"] = metadata

            response = await self.client.chat.completions.create(**request_params)

            content = response.choices[0].message.content
            duration = time.time() - start_time

            # Extract usage information
            usage = None
            if response.usage:
                usage = {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            logger.info(
                "OpenAI API success",
                extra={
                    "model": self.model,
                    "response_length": len(content) if content else 0,
                    "tokens_used": response.usage.total_tokens if response.usage else 0,
                    "usage": usage,
                    "event_type": "openai_api_success",
                    "duration": duration,
                },
            )

            return str(content) if content else None

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            logger.error(
                "OpenAI API error",
                extra={
                    "model": self.model,
                    "error": error_msg,
                    "event_type": "openai_api_error",
                    "duration": duration,
                },
            )
            return None

    async def close(self):
        """Close OpenAI client"""
        if hasattr(self.client, "_client"):
            await self.client.close()


def create_llm_provider(settings: LLMSettings) -> LLMProvider:
    """Factory function to create LLM provider instances"""
    provider_name = settings.provider.lower()

    if provider_name == "openai":
        return OpenAIProvider(settings)
    else:
        raise ValueError(
            f"Unsupported LLM provider: {settings.provider}. Only 'openai' is supported."
        )
