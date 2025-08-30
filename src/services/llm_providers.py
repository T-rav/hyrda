"""
LLM provider implementations for direct API integration
"""

import logging
import time
from abc import ABC, abstractmethod

import aiohttp
from anthropic import AsyncAnthropic
from langfuse.openai import AsyncOpenAI

from config.settings import LLMSettings
from services.langfuse_service import get_langfuse_service, observe

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
            request_params = {
                "model": self.model,
                "messages": formatted_messages,  # type: ignore[arg-type]
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }

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


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider"""

    def __init__(self, settings: LLMSettings):
        super().__init__(settings)
        self.client = AsyncAnthropic(api_key=settings.api_key.get_secret_value())

    @observe(name="anthropic_llm_call", as_type="generation")
    async def get_response(
        self,
        messages: list[dict[str, str]],
        system_message: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> str | None:
        """Get response from Anthropic API"""
        start_time = time.time()
        langfuse_service = get_langfuse_service()

        try:
            # Convert messages to Anthropic format
            formatted_messages = []
            for msg in messages:
                if msg["role"] in ["user", "assistant"]:
                    formatted_messages.append(
                        {"role": msg["role"], "content": msg["content"]}
                    )

            logger.info(
                "Calling Anthropic API",
                extra={
                    "model": self.model,
                    "message_count": len(formatted_messages),
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "event_type": "anthropic_api_request",
                },
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
            duration = time.time() - start_time

            # Extract usage information
            usage = None
            if response.usage:
                usage = {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens
                    + response.usage.output_tokens,
                }

            # Trace with Langfuse
            if langfuse_service:
                langfuse_service.trace_llm_call(
                    provider="anthropic",
                    model=self.model,
                    messages=formatted_messages,
                    response=content,
                    metadata={
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                        "duration_seconds": duration,
                        "system_message": system_message,
                    },
                    usage=usage,
                )

            logger.info(
                "Anthropic API success",
                extra={
                    "model": self.model,
                    "response_length": len(content) if content else 0,
                    "tokens_used": (
                        response.usage.input_tokens + response.usage.output_tokens
                        if response.usage
                        else 0
                    ),
                    "event_type": "anthropic_api_success",
                    "duration": duration,
                },
            )

            return content

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            # Trace error with Langfuse
            if langfuse_service:
                langfuse_service.trace_llm_call(
                    provider="anthropic",
                    model=self.model,
                    messages=formatted_messages
                    if "formatted_messages" in locals()
                    else messages,
                    response=None,
                    metadata={
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                        "duration_seconds": duration,
                        "system_message": system_message,
                    },
                    error=error_msg,
                )

            logger.error(
                "Anthropic API error",
                extra={
                    "model": self.model,
                    "error": error_msg,
                    "event_type": "anthropic_api_error",
                    "duration": duration,
                },
            )
            return None

    async def close(self):
        """Close Anthropic client"""
        if hasattr(self.client, "_client"):
            await self.client.close()


class OllamaProvider(LLMProvider):
    """Ollama local API provider"""

    def __init__(self, settings: LLMSettings):
        super().__init__(settings)
        self.base_url = settings.base_url or "http://localhost:11434"
        self.session: aiohttp.ClientSession | None = None

    async def ensure_session(self) -> aiohttp.ClientSession:
        """Ensure an active client session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    @observe(name="ollama_llm_call", as_type="generation")
    async def get_response(
        self,
        messages: list[dict[str, str]],
        system_message: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> str | None:
        """Get response from Ollama API"""
        start_time = time.time()
        langfuse_service = get_langfuse_service()

        try:
            session = await self.ensure_session()

            # Prepare payload for Ollama chat API
            payload = {
                "model": self.model,
                "messages": messages.copy(),
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            }

            # Add system message if provided
            if system_message:
                payload["messages"].insert(
                    0, {"role": "system", "content": system_message}
                )

            logger.info(
                "Calling Ollama API",
                extra={
                    "model": self.model,
                    "base_url": self.base_url,
                    "message_count": len(payload["messages"]),
                    "event_type": "ollama_api_request",
                },
            )

            async with session.post(
                f"{self.base_url}/api/chat", json=payload
            ) as response:
                HTTP_OK = 200
                if response.status == HTTP_OK:
                    result = await response.json()
                    content = result.get("message", {}).get("content", "")
                    duration = time.time() - start_time

                    # Trace with Langfuse (Ollama doesn't provide token usage)
                    if langfuse_service:
                        langfuse_service.trace_llm_call(
                            provider="ollama",
                            model=self.model,
                            messages=payload["messages"],
                            response=content,
                            metadata={
                                "temperature": self.temperature,
                                "max_tokens": self.max_tokens,
                                "duration_seconds": duration,
                                "base_url": self.base_url,
                            },
                        )

                    logger.info(
                        "Ollama API success",
                        extra={
                            "model": self.model,
                            "response_length": len(content),
                            "event_type": "ollama_api_success",
                            "duration": duration,
                        },
                    )

                    return str(content)
                else:
                    error_text = await response.text()
                    duration = time.time() - start_time

                    # Trace error with Langfuse
                    if langfuse_service:
                        langfuse_service.trace_llm_call(
                            provider="ollama",
                            model=self.model,
                            messages=payload["messages"],
                            response=None,
                            metadata={
                                "temperature": self.temperature,
                                "max_tokens": self.max_tokens,
                                "duration_seconds": duration,
                                "base_url": self.base_url,
                                "status_code": response.status,
                            },
                            error=f"HTTP {response.status}: {error_text}",
                        )

                    logger.error(
                        "Ollama API error",
                        extra={
                            "model": self.model,
                            "status_code": response.status,
                            "error": error_text,
                            "event_type": "ollama_api_error",
                            "duration": duration,
                        },
                    )
                    return None

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            # Trace error with Langfuse
            if langfuse_service:
                langfuse_service.trace_llm_call(
                    provider="ollama",
                    model=self.model,
                    messages=messages,
                    response=None,
                    metadata={
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                        "duration_seconds": duration,
                        "base_url": self.base_url,
                    },
                    error=error_msg,
                )

            logger.error(
                "Ollama API exception",
                extra={
                    "model": self.model,
                    "error": error_msg,
                    "event_type": "ollama_api_exception",
                    "duration": duration,
                },
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

    return provider_class(settings)  # type: ignore[abstract]
