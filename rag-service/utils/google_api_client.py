"""Google API client utilities for acting on behalf of authenticated users.

This module provides helper functions for calling Google APIs using OAuth tokens
passed from LibreChat via the X-Google-OAuth-Token header.

Example usage:
    @router.post("/chat/completions")
    async def generate_response(
        request: RAGGenerateRequest,
        auth: dict = Depends(require_service_auth),
    ):
        oauth_token = auth.get("google_oauth_token")
        if oauth_token:
            # Search user's Google Drive
            files = await search_google_drive(oauth_token, query="quarterly report")

            # Read user's Gmail
            emails = await search_gmail(oauth_token, query="from:boss@company.com")
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class GoogleAPIError(Exception):
    """Raised when Google API calls fail."""

    pass


async def search_google_drive(
    oauth_token: str,
    query: str,
    max_results: int = 10,
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    """Search user's Google Drive files.

    Args:
        oauth_token: Google OAuth access token from user
        query: Google Drive search query (e.g., "name contains 'report'")
        max_results: Maximum number of results to return
        timeout: Request timeout in seconds

    Returns:
        List of file metadata dicts with keys: id, name, mimeType, webViewLink

    Raises:
        GoogleAPIError: If API call fails

    Example:
        files = await search_google_drive(
            oauth_token,
            query="name contains 'Q4' and mimeType='application/pdf'",
            max_results=5
        )
        for file in files:
            print(f"Found: {file['name']} - {file['webViewLink']}")
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/drive/v3/files",
                headers={"Authorization": f"Bearer {oauth_token}"},
                params={
                    "q": query,
                    "pageSize": max_results,
                    "fields": "files(id,name,mimeType,webViewLink,createdTime,modifiedTime)",
                },
                timeout=timeout,
            )

            if response.status_code == 401:
                raise GoogleAPIError(
                    "OAuth token expired or invalid. User needs to re-authenticate."
                )

            response.raise_for_status()
            data = response.json()
            return data.get("files", [])

    except httpx.HTTPStatusError as e:
        logger.error(f"Google Drive API error: {e.response.status_code} - {e.response.text}")
        raise GoogleAPIError(f"Google Drive API failed: {e.response.status_code}") from e
    except Exception as e:
        logger.error(f"Failed to search Google Drive: {e}")
        raise GoogleAPIError(f"Google Drive search failed: {str(e)}") from e


async def get_drive_file_content(
    oauth_token: str,
    file_id: str,
    timeout: float = 30.0,
) -> bytes:
    """Download content from a Google Drive file.

    Args:
        oauth_token: Google OAuth access token from user
        file_id: Google Drive file ID
        timeout: Request timeout in seconds

    Returns:
        File content as bytes

    Raises:
        GoogleAPIError: If download fails

    Example:
        content = await get_drive_file_content(oauth_token, "1ABC...XYZ")
        text = content.decode("utf-8")
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                headers={"Authorization": f"Bearer {oauth_token}"},
                params={"alt": "media"},
                timeout=timeout,
            )

            if response.status_code == 401:
                raise GoogleAPIError(
                    "OAuth token expired or invalid. User needs to re-authenticate."
                )

            response.raise_for_status()
            return response.content

    except httpx.HTTPStatusError as e:
        logger.error(f"Google Drive download error: {e.response.status_code}")
        raise GoogleAPIError(f"Drive file download failed: {e.response.status_code}") from e
    except Exception as e:
        logger.error(f"Failed to download Drive file: {e}")
        raise GoogleAPIError(f"Drive download failed: {str(e)}") from e


async def search_gmail(
    oauth_token: str,
    query: str,
    max_results: int = 10,
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    """Search user's Gmail messages.

    Args:
        oauth_token: Google OAuth access token from user
        query: Gmail search query (e.g., "from:boss@company.com subject:report")
        max_results: Maximum number of results to return
        timeout: Request timeout in seconds

    Returns:
        List of message metadata dicts with keys: id, threadId, snippet

    Raises:
        GoogleAPIError: If API call fails

    Example:
        messages = await search_gmail(
            oauth_token,
            query="from:boss@company.com after:2024/01/01",
            max_results=5
        )
        for msg in messages:
            print(f"Message: {msg['snippet']}")
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers={"Authorization": f"Bearer {oauth_token}"},
                params={
                    "q": query,
                    "maxResults": max_results,
                },
                timeout=timeout,
            )

            if response.status_code == 401:
                raise GoogleAPIError(
                    "OAuth token expired or invalid. User needs to re-authenticate."
                )

            response.raise_for_status()
            data = response.json()
            return data.get("messages", [])

    except httpx.HTTPStatusError as e:
        logger.error(f"Gmail API error: {e.response.status_code} - {e.response.text}")
        raise GoogleAPIError(f"Gmail API failed: {e.response.status_code}") from e
    except Exception as e:
        logger.error(f"Failed to search Gmail: {e}")
        raise GoogleAPIError(f"Gmail search failed: {str(e)}") from e


async def get_gmail_message(
    oauth_token: str,
    message_id: str,
    format: str = "full",
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Get full Gmail message details.

    Args:
        oauth_token: Google OAuth access token from user
        message_id: Gmail message ID
        format: Response format - "full", "metadata", "minimal", or "raw"
        timeout: Request timeout in seconds

    Returns:
        Message dict with headers, body, attachments, etc.

    Raises:
        GoogleAPIError: If API call fails

    Example:
        message = await get_gmail_message(oauth_token, "18abc123def")
        print(f"Subject: {message['payload']['headers'][0]['value']}")
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
                headers={"Authorization": f"Bearer {oauth_token}"},
                params={"format": format},
                timeout=timeout,
            )

            if response.status_code == 401:
                raise GoogleAPIError(
                    "OAuth token expired or invalid. User needs to re-authenticate."
                )

            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        logger.error(f"Gmail message fetch error: {e.response.status_code}")
        raise GoogleAPIError(f"Gmail message fetch failed: {e.response.status_code}") from e
    except Exception as e:
        logger.error(f"Failed to get Gmail message: {e}")
        raise GoogleAPIError(f"Gmail message fetch failed: {str(e)}") from e


def is_oauth_token_valid(oauth_token: str | None) -> bool:
    """Check if an OAuth token is present (doesn't verify expiration).

    Args:
        oauth_token: OAuth token or None

    Returns:
        True if token exists and looks valid

    Example:
        if is_oauth_token_valid(auth.get("google_oauth_token")):
            # Safe to use token
            pass
    """
    return bool(oauth_token and len(oauth_token) > 20)
