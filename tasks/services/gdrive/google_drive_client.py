"""
Google Drive Client Service - Refactored

Orchestrates Google Drive operations using focused service classes:
- GoogleAuthenticator: Handles OAuth2 authentication
- GoogleDriveAPI: Handles raw API calls
- GoogleMetadataParser: Handles metadata processing
- DocumentProcessor: Handles content processing
"""

import logging
from typing import Any

from .document_processor import DocumentProcessor
from .google_authenticator import GoogleAuthenticator
from .google_drive_api import GoogleDriveAPI
from .google_metadata_parser import GoogleMetadataParser

logger = logging.getLogger(__name__)


class GoogleDriveClient:
    """Main orchestrator for Google Drive operations."""

    def __init__(
        self, credentials_file: str | None = None, token_file: str | None = None
    ):
        """
        Initialize the Google Drive client.

        Args:
            credentials_file: Path to Google OAuth2 credentials JSON file
            token_file: Path to store/retrieve OAuth2 token
        """
        self.authenticator = GoogleAuthenticator(credentials_file, token_file)
        self.api_service = None
        self.metadata_parser = GoogleMetadataParser()
        self.document_processor = DocumentProcessor()

    def authenticate(self) -> bool:
        """
        Authenticate with Google Drive API.

        Returns:
            bool: True if authentication successful, False otherwise
        """
        try:
            credentials = self.authenticator.authenticate()
            if credentials:
                self.api_service = GoogleDriveAPI(credentials)
                logger.info("✅ Google Drive client authenticated successfully")
                return True
            else:
                logger.error("❌ Authentication failed")
                return False
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    def list_folder_contents(
        self, folder_id: str, recursive: bool = True, folder_path: str = ""
    ) -> list[dict]:
        """
        List all files in a Google Drive folder with comprehensive metadata.

        Args:
            folder_id: Google Drive folder ID
            recursive: Whether to include subfolders
            folder_path: Current folder path for building full paths

        Returns:
            List of file metadata dictionaries with paths and permissions
        """
        if not self.api_service:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        logger.info(f"📂 Listing contents of folder: {folder_id}")

        # Get folder info for validation
        if folder_path == "":  # Only for root folder
            folder_info = self.api_service.get_folder_info(folder_id)
            if not folder_info:
                logger.warning(f"Could not access folder {folder_id}")
                return []

        # Get files in folder
        items = self.api_service.list_files_in_folder(folder_id, folder_path)

        if not items and folder_path == "":
            # Debug empty root folder
            debug_info = self.api_service.debug_folder_access(folder_id)
            logger.warning(f"Empty folder debug info: {debug_info}")

        # Process each item
        files = []
        for item in items:
            try:
                processed_item = self._process_folder_item(
                    item, folder_id, folder_path, recursive
                )
                if processed_item:
                    files.extend(processed_item)
            except Exception as e:
                logger.error(
                    f"Error processing item {item.get('name', 'unknown')}: {e}"
                )

        logger.info(f"✅ Found {len(files)} items in folder")
        return files

    def _process_folder_item(
        self, item: dict, folder_id: str, folder_path: str, recursive: bool
    ) -> list[dict]:
        """
        Process a single folder item (file or subfolder).

        Args:
            item: Raw item from Google Drive API
            folder_id: Parent folder ID
            folder_path: Current folder path
            recursive: Whether to recurse into subfolders

        Returns:
            List of processed items (may include subfolder contents)
        """
        # Enrich metadata
        item["folder_id"] = folder_id

        # Get detailed permissions BEFORE enrichment
        detailed_permissions = self.api_service.get_detailed_permissions(item["id"])
        item["detailed_permissions"] = detailed_permissions

        # DEBUG logging
        logger.info(f"🔍 File: {item['name']}")
        logger.info(f"   owners field: {item.get('owners', [])}")
        logger.info(f"   detailed_permissions count: {len(detailed_permissions)}")
        if detailed_permissions:
            logger.info(f"   detailed_permissions sample: {detailed_permissions[:2]}")

        enriched_item = self.metadata_parser.enrich_file_metadata(item, folder_path)

        files = [enriched_item]

        # If it's a folder and recursive is enabled, get its contents
        if recursive and item["mimeType"] == "application/vnd.google-apps.folder":
            try:
                subfolder_files = self.list_folder_contents(
                    item["id"], recursive=True, folder_path=enriched_item["full_path"]
                )
                files.extend(subfolder_files)
            except Exception as e:
                logger.error(f"Error processing subfolder {item['name']}: {e}")

        return files

    def download_file_content(self, file_id: str, mime_type: str) -> str | None:  # noqa: PLR0911
        """
        Download the content of a file from Google Drive and extract text.

        Args:
            file_id: Google Drive file ID
            mime_type: MIME type of the file

        Returns:
            File content as string, or None if failed
        """
        if not self.api_service:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Check if file type is supported
        if not self.metadata_parser.is_supported_file_type(mime_type):
            logger.warning(f"Unsupported file type: {mime_type}")
            return None

        try:
            # Download raw content
            raw_content = self.api_service.download_file_content(file_id, mime_type)
            if not raw_content:
                return None

            # Process content based on type
            if isinstance(raw_content, bytes):
                # Handle Google Apps files (usually come as bytes)
                if mime_type.startswith("application/vnd.google-apps"):
                    try:
                        return raw_content.decode("utf-8")
                    except UnicodeDecodeError:
                        return raw_content.decode("latin-1", errors="ignore")
                else:
                    # Use document processor for other file types
                    return self.document_processor.extract_text(raw_content, mime_type)
            else:
                return str(raw_content)

        except Exception as e:
            logger.error(f"Error processing file content {file_id}: {e}")
            return None

    def get_client_status(self) -> dict[str, Any]:
        """
        Get status information about the Google Drive client.

        Returns:
            Status information dictionary
        """
        return {
            "authenticated": self.api_service is not None,
            "services": {
                "authenticator": "initialized",
                "api_service": "initialized"
                if self.api_service
                else "not_authenticated",
                "metadata_parser": "initialized",
                "document_processor": "initialized",
            },
        }

    # Backward compatibility - delegate to metadata parser
    @staticmethod
    def format_permissions(permissions: list[dict]) -> dict:
        """Format Google Drive permissions (backward compatibility)"""
        return GoogleMetadataParser.format_permissions(permissions)

    @staticmethod
    def get_permissions_summary(permissions: list[dict]) -> str:
        """Get permissions summary (backward compatibility)"""
        return GoogleMetadataParser.get_permissions_summary(permissions)

    @staticmethod
    def get_owner_emails(owners: list[dict]) -> str:
        """Get owner emails (backward compatibility)"""
        return GoogleMetadataParser.get_owner_emails(owners)
