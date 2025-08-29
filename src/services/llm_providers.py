"""
LLM provider implementations for direct API integration
"""

import logging
from abc import ABC, abstractmethod

import aiohttp
from anthropic import AsyncAnthropic
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
        system_message: str | None = None
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
        system_message: str | None = None
    ) -> str | None:
        """Get response from OpenAI API"""
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
                }
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            content = response.choices[0].message.content

            logger.info(
                "OpenAI API success",
                extra={
                    "model": self.model,
                    "response_length": len(content) if content else 0,
                    "tokens_used": response.usage.total_tokens if response.usage else 0,
                    "event_type": "openai_api_success",
                }
            )

            return content

        except Exception as e:
            logger.error(
                "OpenAI API error",
                extra={
                    "model": self.model,
                    "error": str(e),
                    "event_type": "openai_api_error",
                }
            )
            return None

    async def close(self):
        """Close OpenAI client"""
        if hasattr(self.client, '_client'):
            await self.client.close()


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider"""

    def __init__(self, settings: LLMSettings):
        super().__init__(settings)
        self.client = AsyncAnthropic(
            api_key=settings.api_key.get_secret_value()
        )

    async def get_response(
        self,
        messages: list[dict[str, str]],
        system_message: str | None = None
    ) -> str | None:
        """Get response from Anthropic API"""
        try:
            # Convert messages to Anthropic format
            formatted_messages = []
            for msg in messages:
                if msg["role"] in ["user", "assistant"]:
                    formatted_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

            logger.info(
                "Calling Anthropic API",
                extra={
                    "model": self.model,
                    "message_count": len(formatted_messages),
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "event_type": "anthropic_api_request",
                }
            )

            kwargs = {
                "model": self.model,
                "messages": formatted_messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }

            if system_message:
                kwargs["system"] = system_message

            response = await self.client.messages.create(**kwargs)

            content = response.content[0].text if response.content else None

            logger.info(
                "Anthropic API success",
                extra={
                    "model": self.model,
                    "response_length": len(content) if content else 0,
                    "tokens_used": response.usage.input_tokens + response.usage.output_tokens if response.usage else 0,
                    "event_type": "anthropic_api_success",
                }
            )

            return content

        except Exception as e:
            logger.error(
                "Anthropic API error",
                extra={
                    "model": self.model,
                    "error": str(e),
                    "event_type": "anthropic_api_error",
                }
            )
            return None

    async def close(self):
        """Close Anthropic client"""
        if hasattr(self.client, '_client'):
            await self.client.close()


class OllamaProvider(LLMProvider):
    """Ollama local API provider"""

    def __init__(self, settings: LLMSettings):
        super().__init__(settings)
        self.base_url = settings.base_url or "http://localhost:11434"
        self.session = None

    async def ensure_session(self) -> aiohttp.ClientSession:
        """Ensure an active client session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def get_response(
        self,
        messages: list[dict[str, str]],
        system_message: str | None = None
    ) -> str | None:
        """Get response from Ollama API"""
        try:
            session = await self.ensure_session()

            # Prepare payload for Ollama chat API
            payload = {
                "model": self.model,
                "messages": messages.copy(),
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                }
            }

            # Add system message if provided
            if system_message:
                payload["messages"].insert(0, {"role": "system", "content": system_message})

            logger.info(
                "Calling Ollama API",
                extra={
                    "model": self.model,
                    "base_url": self.base_url,
                    "message_count": len(payload["messages"]),
                    "event_type": "ollama_api_request",
                }
            )

            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result.get("message", {}).get("content", "")

                    logger.info(
                        "Ollama API success",
                        extra={
                            "model": self.model,
                            "response_length": len(content),
                            "event_type": "ollama_api_success",
                        }
                    )

                    return content
                else:
                    error_text = await response.text()
                    logger.error(
                        "Ollama API error",
                        extra={
                            "model": self.model,
                            "status_code": response.status,
                            "error": error_text,
                            "event_type": "ollama_api_error",
                        }
                    )
                    return None

        except Exception as e:
            logger.error(
                "Ollama API exception",
                extra={
                    "model": self.model,
                    "error": str(e),
                    "event_type": "ollama_api_exception",
                }
            )
            return None

    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
        self.session = None


def create_llm_provider(settings: LLMSettings) -> LLMProvider:
    """Factory function to create the appropriate LLM provider"""
    provider_map = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "ollama": OllamaProvider,
    }

    provider_class = provider_map.get(settings.provider.lower())
    if not provider_class:
        raise ValueError(f"Unsupported LLM provider: {settings.provider}")

    return provider_class(settings)
