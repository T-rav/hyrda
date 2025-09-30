"""
HTTPResponseFactory for test utilities
"""

from typing import Any
from unittest.mock import MagicMock


class HTTPResponseFactory:
    """Factory for creating mock HTTP responses"""

    @staticmethod
    def create_success_response(
        status_code: int = 200,
        content: bytes = b"Success",
        headers: dict[str, str] | None = None,
    ) -> MagicMock:
        """Create successful HTTP response"""
        response = MagicMock()
        response.status_code = status_code
        response.content = content
        response.headers = headers or {}
        response.text = content.decode("utf-8")
        response.json = MagicMock(return_value={})
        response.raise_for_status = MagicMock()
        return response

    @staticmethod
    def create_error_response(
        status_code: int = 404,
        content: bytes = b"Not Found",
    ) -> MagicMock:
        """Create error HTTP response"""
        response = HTTPResponseFactory.create_success_response(status_code, content)
        response.raise_for_status = MagicMock(
            side_effect=Exception(f"HTTP {status_code}")
        )
        return response

    @staticmethod
    def create_json_response(data: dict[str, Any], status_code: int = 200) -> MagicMock:
        """Create HTTP response with JSON data"""
        import json

        content = json.dumps(data).encode("utf-8")
        response = HTTPResponseFactory.create_success_response(status_code, content)
        response.json = MagicMock(return_value=data)
        return response
