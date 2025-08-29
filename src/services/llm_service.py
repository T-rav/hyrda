import logging

import aiohttp

from config.settings import LLMSettings

logger = logging.getLogger(__name__)


class LLMService:
    """Service for interacting with the LLM API"""

    def __init__(self, settings: LLMSettings):
        self.api_url = settings.api_url
        self.api_key = settings.api_key.get_secret_value()
        self.model = settings.model
        self.session = None

    async def ensure_session(self) -> aiohttp.ClientSession:
        """Ensure an active client session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def get_response(
        self, messages: list[dict[str, str]], user_id: str | None = None
    ) -> str | None:
        """Get response from LLM via API"""
        if not self.api_key:
            logger.error("LLM_API_KEY is not set")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Add user auth token if provided
        if user_id:
            auth_token = f"slack:{user_id}"
            headers["X-Auth-Token"] = auth_token
            logger.info(f"Added X-Auth-Token header: {auth_token}")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000,
        }

        # Add metadata with user auth token for the callback pipeline
        if user_id:
            auth_token = f"slack:{user_id}"
            payload["metadata"] = {"X-Auth-Token": auth_token, "user_id": user_id}
            logger.info(f"Added user auth token to metadata: {auth_token}")

        logger.info(f"LLM API URL: {self.api_url}")
        logger.info(f"LLM Model: {self.model}")

        session = await self.ensure_session()

        try:
            logger.info(
                "Calling LLM API",
                extra={
                    "api_url": self.api_url,
                    "model": self.model,
                    "user_id": user_id,
                    "message_count": len(messages),
                    "event_type": "llm_api_request",
                },
            )

            async with session.post(
                f"{self.api_url}/chat/completions", headers=headers, json=payload
            ) as response:
                result_text = await response.text()

                if response.status == 200:
                    result = await response.json()
                    response_content = result["choices"][0]["message"]["content"]

                    logger.info(
                        "LLM API success",
                        extra={
                            "api_url": self.api_url,
                            "model": self.model,
                            "user_id": user_id,
                            "status_code": response.status,
                            "response_length": len(response_content),
                            "event_type": "llm_api_success",
                        },
                    )

                    return response_content
                else:
                    logger.error(
                        "LLM API error",
                        extra={
                            "api_url": self.api_url,
                            "model": self.model,
                            "user_id": user_id,
                            "status_code": response.status,
                            "error_response": result_text,
                            "event_type": "llm_api_error",
                        },
                    )
                    return None
        except Exception as e:
            logger.error(
                "LLM API exception",
                extra={
                    "api_url": self.api_url,
                    "model": self.model,
                    "user_id": user_id,
                    "error": str(e),
                    "event_type": "llm_api_exception",
                },
            )
            import traceback

            logger.error(f"LLM API exception traceback: {traceback.format_exc()}")
            return None

    async def close(self):
        """Close the HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
        self.session = None
