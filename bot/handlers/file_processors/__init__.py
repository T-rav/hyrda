"""File processors for handling document attachments in bot messages.

This module provides text extraction from various file formats:
- PDF (.pdf)
- Microsoft Word (.docx)
- Microsoft Excel (.xlsx)
- Microsoft PowerPoint (.pptx)
- Plain text (.txt)

All extraction is done async-safe to avoid blocking the event loop.
"""

import logging

import requests

from .office_processor import extract_office_text
from .pdf_processor import extract_pdf_text

logger = logging.getLogger(__name__)

# Constants
HTTP_OK = 200

# Re-export for backward compatibility
__all__ = ["process_file_attachments", "extract_pdf_text", "extract_office_text"]


async def process_file_attachments(files: list[dict], slack_service) -> str:
    """Process file attachments and extract text content.

    Handles multiple file types and downloads files from Slack if needed.

    Args:
        files: List of file dictionaries from Slack API
        slack_service: SlackService instance for downloading files

    Returns:
        Combined text content from all processed files
    """
    if not files:
        return ""

    all_content = []

    for file_info in files:
        file_name = file_info.get("name", "unknown")
        file_type = file_info.get("mimetype", "")
        file_url = file_info.get("url_private")

        logger.info(f"Processing file: {file_name} (type: {file_type})")

        try:
            # Download file content
            if not file_url:
                logger.warning(f"No URL for file: {file_name}")
                continue

            # Use Slack service to download with proper auth
            headers = {"Authorization": f"Bearer {slack_service.bot_token}"}
            response = requests.get(file_url, headers=headers, timeout=30)

            if response.status_code != HTTP_OK:
                logger.error(
                    f"Failed to download file {file_name}: {response.status_code}"
                )
                continue

            content = response.content

            # Extract text based on file type
            extracted_text = ""

            if file_type == "application/pdf" or file_name.lower().endswith(".pdf"):
                extracted_text = await extract_pdf_text(content, file_name)

            elif (
                file_type
                == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                or file_name.lower().endswith(".docx")
            ):
                extracted_text = await extract_office_text(content, file_name, "docx")

            elif (
                file_type
                == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                or file_name.lower().endswith(".xlsx")
            ):
                extracted_text = await extract_office_text(content, file_name, "xlsx")

            elif (
                file_type
                == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                or file_name.lower().endswith(".pptx")
            ):
                extracted_text = await extract_office_text(content, file_name, "pptx")

            elif (
                file_type.startswith("text/")
                or file_name.lower().endswith((".txt", ".vtt", ".srt"))
                or "subrip" in file_type.lower()
            ):
                try:
                    extracted_text = content.decode("utf-8")
                except UnicodeDecodeError:
                    extracted_text = f"[Text file: {file_name} - Encoding error]"

            else:
                logger.info(f"Unsupported file type: {file_type}")
                extracted_text = f"[Unsupported file type: {file_name}]"

            if extracted_text:
                # Add file header (for both successful extraction and errors)
                if not extracted_text.startswith("["):
                    all_content.append(f"\n\n=== Content from {file_name} ===\n")
                    all_content.append(extracted_text)
                else:
                    # Include error messages so users know processing failed
                    all_content.append(f"\n\n{extracted_text}")

        except Exception as e:
            logger.error(f"Error processing file {file_name}: {e}")
            continue

    return "\n".join(all_content) if all_content else ""
