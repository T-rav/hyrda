"""
Google Drive API Service

Handles raw Google Drive API calls and folder operations.
Separated for better organization and testability.
"""

import logging
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GoogleDriveAPI:
    """Service for Google Drive API operations"""

    def __init__(self, credentials):
        """
        Initialize Google Drive API service.

        Args:
            credentials: Google OAuth2 credentials object
        """
        self.service = build("drive", "v3", credentials=credentials)

    def get_folder_info(self, folder_id: str) -> dict | None:
        """
        Get information about a folder.

        Args:
            folder_id: Google Drive folder ID

        Returns:
            Folder information dictionary or None if error
        """
        try:
            # Try regular access first
            folder_info = (
                self.service.files()
                .get(
                    fileId=folder_id,
                    fields="id,name,mimeType,permissions",
                    supportsAllDrives=True,
                )
                .execute()
            )
            return folder_info
        except HttpError as e:
            logger.error(f"Cannot access folder {folder_id}: {e}")
            return None

    def list_files_in_folder(self, folder_id: str, folder_path: str = "") -> list[dict]:
        """
        List files in a specific folder using various query strategies.

        Args:
            folder_id: Google Drive folder ID
            folder_path: Current folder path for debugging

        Returns:
            List of file items
        """
        try:
            # Always use specific query - it works better for Shared Drives
            # The broad query doesn't reliably return parents field
            return self._list_files_specific_query(folder_id)
        except HttpError as e:
            logger.error(f"Error listing folder contents: {e}")
            return []

    def _list_files_broad_query(self, folder_id: str) -> list[dict]:
        """Use broad query for root folder access"""
        logger.info("🔄 Using broad shared drive query for root folder...")

        all_results = (
            self.service.files()
            .list(
                q="trashed=false",
                pageSize=1000,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, parents, permissions, owners, createdTime, webViewLink)",
            )
            .execute()
        )

        # Filter to only files that have our folder_id as parent
        all_files = all_results.get("files", [])

        # Log file parent checking for debugging
        logger.debug(f"Checking {len(all_files)} files for parent {folder_id}")
        files_with_parents = [f for f in all_files if "parents" in f]
        logger.debug(f"{len(files_with_parents)} files have 'parents' field")

        # Log a few examples for debugging
        for i, f in enumerate(all_files[:3]):
            logger.debug(
                f"Example {i + 1}: {f.get('name')} - parents: {f.get('parents', 'MISSING')}, mimeType: {f.get('mimeType')}"
            )

        filtered_files = [f for f in all_files if folder_id in f.get("parents", [])]

        # Log what was found for debugging
        folders = [
            f
            for f in filtered_files
            if f.get("mimeType") == "application/vnd.google-apps.folder"
        ]
        documents = [
            f
            for f in filtered_files
            if f.get("mimeType") != "application/vnd.google-apps.folder"
        ]
        logger.debug(
            f"Found {len(all_files)} total accessible files, "
            f"{len(filtered_files)} in target folder "
            f"({len(folders)} folders, {len(documents)} documents)"
        )

        # Log the folders found for debugging
        if folders:
            logger.debug("Folders found:")
            for folder in folders:
                logger.debug(f"- {folder.get('name')} ({folder.get('id')})")
        else:
            logger.debug("No folders found in target folder")

        return filtered_files

    def _list_files_specific_query(self, folder_id: str) -> list[dict]:
        """Use specific parent query for subfolders"""
        query = f"'{folder_id}' in parents and trashed=false"

        results = (
            self.service.files()
            .list(
                q=query,
                pageSize=1000,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, parents, permissions, owners, createdTime, webViewLink)",
            )
            .execute()
        )

        return results.get("files", [])

    def get_detailed_permissions(self, file_id: str) -> list[dict]:
        """
        Get detailed permissions for a specific file.

        Uses permissions().list() API since files().get() doesn't include permissions
        for Shared Drive files even when requested with fields="permissions(*)".

        Args:
            file_id: Google Drive file ID

        Returns:
            List of permission dictionaries
        """
        try:
            # Use permissions.list() API - files.get() doesn't return permissions
            # for Shared Drive files even with fields="permissions(*)"
            logger.info(f"🔍 Fetching permissions for file: {file_id}")
            permissions_response = (
                self.service.permissions()
                .list(
                    fileId=file_id,
                    fields="permissions(*)",
                    supportsAllDrives=True,
                )
                .execute()
            )
            perms = permissions_response.get("permissions", [])
            logger.info(f"✅ permissions().list() returned {len(perms)} permissions for {file_id}")
            if perms:
                logger.info(f"   Sample permission: {perms[0]}")
            else:
                logger.warning(f"   ⚠️ EMPTY permissions list returned by API for {file_id}")
            return perms
        except HttpError as e:
            logger.error(f"❌ Could not fetch detailed permissions for {file_id}: {e}")
            return []

    def download_file_content(self, file_id: str, mime_type: str) -> bytes | None:
        """
        Download raw file content from Google Drive with retry logic for transient errors.

        Args:
            file_id: Google Drive file ID
            mime_type: MIME type of the file

        Returns:
            Raw file content as bytes or None if failed
        """
        import time

        max_retries = 3
        base_delay = 1.0  # seconds

        for attempt in range(max_retries):
            try:
                # Handle Google Docs files (need export)
                if mime_type == "application/vnd.google-apps.document":
                    request = self.service.files().export_media(
                        fileId=file_id, mimeType="text/plain"
                    )
                elif mime_type == "application/vnd.google-apps.spreadsheet":
                    request = self.service.files().export_media(
                        fileId=file_id, mimeType="text/csv"
                    )
                elif mime_type == "application/vnd.google-apps.presentation":
                    request = self.service.files().export_media(
                        fileId=file_id, mimeType="text/plain"
                    )
                else:
                    # Handle regular files (need download)
                    request = self.service.files().get_media(fileId=file_id)

                content = request.execute()
                return content

            except HttpError as e:
                error_code = e.resp.status
                is_retryable = error_code in [
                    500,
                    502,
                    503,
                    504,
                    429,
                ]  # Server errors + rate limit

                if is_retryable and attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)  # Exponential backoff
                    logger.warning(
                        f"Retryable error {error_code} for file {file_id}, "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Error downloading file {file_id}: {e}")
                    return None

        # If we get here, all retries failed
        return None

    def debug_folder_access(self, folder_id: str) -> dict[str, Any]:
        """
        Debug folder access issues with detailed logging.

        Args:
            folder_id: Google Drive folder ID

        Returns:
            Debug information dictionary
        """
        debug_info = {
            "folder_id": folder_id,
            "folder_exists": False,
            "folder_info": None,
            "query_methods_tried": [],
            "files_found": 0,
            "errors": [],
        }

        # Try to get folder info
        try:
            folder_info = self.get_folder_info(folder_id)
            if folder_info:
                debug_info["folder_exists"] = True
                debug_info["folder_info"] = folder_info
                logger.info(
                    f"📁 Folder exists: '{folder_info.get('name')}' (Type: {folder_info.get('mimeType')})"
                )
        except Exception as e:
            debug_info["errors"].append(f"Folder info error: {e}")

        # Try different query methods
        try:
            files = self._list_files_specific_query(folder_id)
            debug_info["query_methods_tried"].append("specific_parent_query")
            debug_info["files_found"] = len(files)
        except Exception as e:
            debug_info["errors"].append(f"Specific query error: {e}")

        if debug_info["files_found"] == 0:
            try:
                files = self._list_files_broad_query(folder_id)
                debug_info["query_methods_tried"].append("broad_query")
                debug_info["files_found"] = len(files)
            except Exception as e:
                debug_info["errors"].append(f"Broad query error: {e}")

        return debug_info
