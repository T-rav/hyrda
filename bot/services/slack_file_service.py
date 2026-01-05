"""
Slack File Service

Handles downloading and processing files shared in Slack channels.
"""

import logging
from typing import Any

import aiohttp
from slack_sdk.web.async_client import AsyncWebClient

logger = logging.getLogger(__name__)


class SlackFileService:
    """Service for downloading and processing files from Slack"""

    def __init__(self, slack_client: AsyncWebClient):
        self.client = slack_client

    async def download_file_content(self, file_info: dict[str, Any]) -> bytes | None:
        """
        Download file content from Slack using the private download URL.

        Args:
            file_info: File information from Slack event

        Returns:
            File content as bytes, or None if download fails
        """
        try:
            # Get the private download URL
            download_url = file_info.get("url_private_download")
            if not download_url:
                logger.warning(f"No download URL for file {file_info.get('id')}")
                return None

            # Get bot token for authentication
            if not hasattr(self.client, "token") or not self.client.token:
                logger.error("No bot token available for file download")
                return None

            # Download file with authentication
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.client.token}"}

                async with session.get(download_url, headers=headers) as response:
                    if response.status == 200:
                        content = await response.read()
                        logger.info(
                            f"Downloaded file {file_info.get('name', 'unknown')} "
                            f"({len(content)} bytes)"
                        )
                        return content
                    else:
                        logger.warning(
                            f"Failed to download file {file_info.get('id')}: "
                            f"HTTP {response.status}"
                        )
                        return None

        except Exception as e:
            logger.error(f"Error downloading file {file_info.get('id')}: {e}")
            return None

    def extract_file_metadata(self, file_info: dict[str, Any]) -> dict[str, Any]:
        """
        Extract relevant metadata from Slack file info.

        Args:
            file_info: File information from Slack event

        Returns:
            Dictionary with extracted metadata
        """
        return {
            "file_id": file_info.get("id"),
            "name": file_info.get("name"),
            "title": file_info.get("title"),
            "mimetype": file_info.get("mimetype"),
            "filetype": file_info.get("filetype"),
            "size": file_info.get("size"),
            "uploaded_by": file_info.get("user"),
            "created": file_info.get("created"),
            "is_external": file_info.get("is_external", False),
        }

    def is_processable_file(self, file_info: dict[str, Any]) -> bool:
        """
        Check if file type is supported for text extraction.

        Args:
            file_info: File information from Slack event

        Returns:
            True if file can be processed for text content
        """
        mimetype = file_info.get("mimetype", "").lower()
        filetype = file_info.get("filetype", "").lower()

        # Supported MIME types (matching DocumentProcessor)
        supported_mimetypes = {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }

        # Supported file extensions
        supported_extensions = {"pdf", "docx", "xlsx", "pptx", "txt", "md", "csv"}

        # Check if text-based mimetype
        is_text_mime = mimetype.startswith("text/")

        return (
            mimetype in supported_mimetypes
            or filetype in supported_extensions
            or is_text_mime
        )
