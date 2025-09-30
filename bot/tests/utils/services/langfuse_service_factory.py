"""
LangfuseServiceFactory for test utilities
"""

from unittest.mock import MagicMock


class LangfuseServiceFactory:
    """Factory for creating Langfuse service mocks"""

    @staticmethod
    def create_mock_service() -> MagicMock:
        """Create basic mock Langfuse service"""
        service = MagicMock()
        service.trace_conversation = MagicMock()
        service.trace_llm_call = MagicMock()
        service.get_prompt = MagicMock(return_value=None)
        return service

    @staticmethod
    def create_service_with_prompt(prompt: str) -> MagicMock:
        """Create Langfuse service that returns a specific prompt"""
        service = LangfuseServiceFactory.create_mock_service()
        prompt_obj = MagicMock()
        prompt_obj.compile.return_value = prompt
        service.get_prompt = MagicMock(return_value=prompt_obj)
        return service
