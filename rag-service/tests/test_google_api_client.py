"""Tests for Google API client utilities."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.google_api_client import (
    GoogleAPIError,
    get_drive_file_content,
    get_gmail_message,
    is_oauth_token_valid,
    search_gmail,
    search_google_drive,
)


@pytest.mark.asyncio
async def test_search_google_drive_success():
    """Test successful Google Drive file search."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(
        return_value={
            "files": [
                {
                    "id": "1ABC123",
                    "name": "Q4 Report.pdf",
                    "mimeType": "application/pdf",
                    "webViewLink": "https://drive.google.com/file/d/1ABC123",
                },
                {
                    "id": "2DEF456",
                    "name": "Q4 Presentation.pptx",
                    "mimeType": "application/vnd.ms-powerpoint",
                    "webViewLink": "https://drive.google.com/file/d/2DEF456",
                },
            ]
        }
    )
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        oauth_token = "ya29.test-token"
        results = await search_google_drive(oauth_token, query="name contains 'Q4'", max_results=10)

        assert len(results) == 2
        assert results[0]["name"] == "Q4 Report.pdf"
        assert results[1]["name"] == "Q4 Presentation.pptx"


@pytest.mark.asyncio
async def test_search_google_drive_expired_token():
    """Test Google Drive search with expired OAuth token."""
    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        oauth_token = "ya29.expired-token"

        with pytest.raises(GoogleAPIError) as exc_info:
            await search_google_drive(oauth_token, query="test")

        assert "expired or invalid" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_search_google_drive_no_files():
    """Test Google Drive search with no results."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={"files": []})
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        oauth_token = "ya29.test-token"
        results = await search_google_drive(oauth_token, query="nonexistent")

        assert results == []


@pytest.mark.asyncio
async def test_get_drive_file_content_success():
    """Test successful file download from Google Drive."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"This is file content"
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        oauth_token = "ya29.test-token"
        file_id = "1ABC123"
        content = await get_drive_file_content(oauth_token, file_id)

        assert content == b"This is file content"


@pytest.mark.asyncio
async def test_search_gmail_success():
    """Test successful Gmail message search."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(
        return_value={
            "messages": [
                {"id": "msg123", "threadId": "thread123"},
                {"id": "msg456", "threadId": "thread456"},
            ]
        }
    )
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        oauth_token = "ya29.test-token"
        results = await search_gmail(oauth_token, query="from:boss@company.com", max_results=5)

        assert len(results) == 2
        assert results[0]["id"] == "msg123"
        assert results[1]["id"] == "msg456"


@pytest.mark.asyncio
async def test_search_gmail_expired_token():
    """Test Gmail search with expired OAuth token."""
    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        oauth_token = "ya29.expired-token"

        with pytest.raises(GoogleAPIError) as exc_info:
            await search_gmail(oauth_token, query="test")

        assert "expired or invalid" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_gmail_message_success():
    """Test successful Gmail message retrieval."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(
        return_value={
            "id": "msg123",
            "threadId": "thread123",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Email"},
                    {"name": "From", "value": "sender@example.com"},
                ],
                "body": {"data": "VGVzdCBtZXNzYWdlIGNvbnRlbnQ="},
            },
        }
    )
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        oauth_token = "ya29.test-token"
        message_id = "msg123"
        message = await get_gmail_message(oauth_token, message_id, format="full")

        assert message["id"] == "msg123"
        assert message["payload"]["headers"][0]["value"] == "Test Email"


def test_is_oauth_token_valid():
    """Test OAuth token validation."""
    # Valid tokens (longer than 20 chars)
    assert is_oauth_token_valid("ya29.a0AeXXXXXXXXXXXXXXXXXXXXX") is True
    assert is_oauth_token_valid("x" * 30) is True

    # Invalid tokens
    assert is_oauth_token_valid(None) is False
    assert is_oauth_token_valid("") is False
    assert is_oauth_token_valid("short") is False  # Less than 20 chars
    assert is_oauth_token_valid("12345678901234567890") is False  # Exactly 20 chars (boundary)
    assert is_oauth_token_valid("123456789012345678901") is True  # 21 chars (valid)
