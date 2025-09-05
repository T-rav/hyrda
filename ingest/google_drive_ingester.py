#!/usr/bin/env python3
"""
Google Drive Document Ingester - THE ONLY SUPPORTED INGESTION METHOD

This is the sole document ingestion system for the RAG pipeline.
It authenticates with Google Drive, scans folders, and upserts documents
with comprehensive metadata including file paths and permissions.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Google Drive API imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import requests

# Local imports (assuming we'll use the existing ingestion logic)
sys.path.append(str(Path(__file__).parent.parent / "bot"))
from services.vector_service import get_vector_service
from config.settings import Settings


class GoogleDriveIngester:
    """Handles Google Drive authentication and document ingestion."""

    # Define the scopes needed for Google Drive API
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

    def __init__(self, credentials_file: Optional[str] = None, token_file: Optional[str] = None):
        """
        Initialize the Google Drive ingester.

        Args:
            credentials_file: Path to Google OAuth2 credentials JSON file
            token_file: Path to store/retrieve OAuth2 token
        """
        self.credentials_file = credentials_file or 'credentials.json'
        self.token_file = token_file or 'token.json'
        self.service = None
        self.vector_service = None

    def authenticate(self) -> bool:
        """
        Authenticate with Google Drive API using OAuth2.

        Returns:
            bool: True if authentication successful, False otherwise
        """
        creds = None

        # Load existing token if available
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)

        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing credentials: {e}")
                    return False
            else:
                if not os.path.exists(self.credentials_file):
                    print(f"Credentials file not found: {self.credentials_file}")
                    print("Please download OAuth2 credentials from Google Cloud Console")
                    return False

                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"Error during OAuth flow: {e}")
                    return False

            # Save the credentials for the next run
            try:
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                print(f"Error saving token: {e}")
                return False

        try:
            self.service = build('drive', 'v3', credentials=creds)
            return True
        except Exception as e:
            print(f"Error building Drive service: {e}")
            return False

    def list_folder_contents(self, folder_id: str, recursive: bool = True, folder_path: str = "") -> List[Dict]:
        """
        List all files in a Google Drive folder with comprehensive metadata.

        Args:
            folder_id: Google Drive folder ID
            recursive: Whether to include subfolders
            folder_path: Current folder path for building full paths

        Returns:
            List of file metadata dictionaries with paths and permissions
        """
        if not self.service:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        files = []

        try:
            # Query for files in the specified folder
            query = f"'{folder_id}' in parents and trashed=false"

            results = self.service.files().list(
                q=query,
                pageSize=1000,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, parents, permissions, owners, createdTime, webViewLink)"
            ).execute()

            items = results.get('files', [])

            for item in items:
                # Build full path
                current_path = f"{folder_path}/{item['name']}" if folder_path else item['name']

                # Add comprehensive metadata
                item['folder_id'] = folder_id
                item['full_path'] = current_path
                item['folder_path'] = folder_path

                # Get detailed permissions for this file
                try:
                    file_permissions = self.service.files().get(
                        fileId=item['id'],
                        fields="permissions"
                    ).execute()
                    item['detailed_permissions'] = file_permissions.get('permissions', [])
                except HttpError as perm_error:
                    print(f"Warning: Could not fetch detailed permissions for {item['name']}: {perm_error}")
                    item['detailed_permissions'] = []

                files.append(item)

                # If it's a folder and recursive is enabled, get its contents
                if recursive and item['mimeType'] == 'application/vnd.google-apps.folder':
                    subfolder_files = self.list_folder_contents(
                        item['id'],
                        recursive=True,
                        folder_path=current_path
                    )
                    files.extend(subfolder_files)

        except HttpError as error:
            print(f"An error occurred while listing folder contents: {error}")

        return files

    def download_file_content(self, file_id: str, mime_type: str) -> Optional[str]:
        """
        Download the content of a file from Google Drive.

        Args:
            file_id: Google Drive file ID
            mime_type: MIME type of the file

        Returns:
            File content as string, or None if failed
        """
        if not self.service:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        try:
            # Handle Google Docs files
            if mime_type == 'application/vnd.google-apps.document':
                request = self.service.files().export_media(
                    fileId=file_id, mimeType='text/plain')
            elif mime_type == 'application/vnd.google-apps.spreadsheet':
                request = self.service.files().export_media(
                    fileId=file_id, mimeType='text/csv')
            elif mime_type == 'application/vnd.google-apps.presentation':
                request = self.service.files().export_media(
                    fileId=file_id, mimeType='text/plain')
            # Handle regular files
            elif mime_type.startswith('text/') or mime_type == 'application/pdf':
                request = self.service.files().get_media(fileId=file_id)
            else:
                print(f"Unsupported file type: {mime_type}")
                return None

            content = request.execute()

            # Decode content based on type
            if isinstance(content, bytes):
                try:
                    return content.decode('utf-8')
                except UnicodeDecodeError:
                    return content.decode('latin-1', errors='ignore')
            else:
                return str(content)

        except HttpError as error:
            print(f"An error occurred downloading file {file_id}: {error}")
            return None

    def _format_permissions(self, permissions: List[Dict]) -> Dict:
        """
        Format Google Drive permissions into a structured format.

        Args:
            permissions: Raw permissions from Google Drive API

        Returns:
            Formatted permissions dictionary
        """
        formatted = {
            'readers': [],
            'writers': [],
            'owners': [],
            'is_public': False,
            'anyone_can_read': False,
            'anyone_can_write': False
        }

        for perm in permissions:
            role = perm.get('role', 'reader')
            perm_type = perm.get('type', 'user')
            email_address = perm.get('emailAddress', '')
            display_name = perm.get('displayName', email_address)

            # Check for public access
            if perm_type == 'anyone':
                formatted['is_public'] = True
                if role in ['reader', 'commenter']:
                    formatted['anyone_can_read'] = True
                elif role in ['writer', 'editor']:
                    formatted['anyone_can_write'] = True
                    formatted['anyone_can_read'] = True  # Writers can also read

            # Categorize by role
            permission_info = {
                'type': perm_type,
                'email': email_address,
                'display_name': display_name,
                'role': role
            }

            if role == 'owner':
                formatted['owners'].append(permission_info)
            elif role in ['writer', 'editor']:
                formatted['writers'].append(permission_info)
            else:  # reader, commenter
                formatted['readers'].append(permission_info)

        return formatted

    async def init_vector_service(self):
        """Initialize the vector service for document storage."""
        if not self.vector_service:
            settings = Settings()
            self.vector_service = await get_vector_service(settings)

    async def ingest_files(self, files: List[Dict], metadata: Optional[Dict] = None) -> Tuple[int, int]:
        """
        Ingest files into the vector database.

        Args:
            files: List of file metadata from Google Drive
            metadata: Additional metadata to add to each document

        Returns:
            Tuple of (success_count, error_count)
        """
        await self.init_vector_service()

        success_count = 0
        error_count = 0

        for file_info in files:
            try:
                # Skip folders and unsupported file types
                if file_info['mimeType'] == 'application/vnd.google-apps.folder':
                    continue

                print(f"Processing: {file_info['name']}")

                # Download file content
                content = self.download_file_content(file_info['id'], file_info['mimeType'])
                if not content:
                    print(f"Failed to download: {file_info['name']}")
                    error_count += 1
                    continue

                # Prepare comprehensive document metadata
                doc_metadata = {
                    'source': 'google_drive',
                    'file_id': file_info['id'],
                    'file_name': file_info['name'],
                    'full_path': file_info.get('full_path', file_info['name']),
                    'folder_path': file_info.get('folder_path', ''),
                    'mime_type': file_info['mimeType'],
                    'modified_time': file_info.get('modifiedTime'),
                    'created_time': file_info.get('createdTime'),
                    'size': file_info.get('size'),
                    'web_view_link': file_info.get('webViewLink'),
                    'owners': file_info.get('owners', []),
                    'permissions': self._format_permissions(file_info.get('detailed_permissions', [])),
                    'ingested_at': datetime.utcnow().isoformat()
                }

                # Add any additional metadata provided
                if metadata:
                    doc_metadata.update(metadata)

                # Upsert document to vector database
                await self.vector_service.upsert_document(
                    doc_id=file_info['id'],
                    content=content,
                    metadata=doc_metadata
                )

                print(f" Successfully ingested: {file_info['name']}")
                success_count += 1

            except Exception as e:
                print(f"L Error processing {file_info.get('name', 'unknown')}: {e}")
                error_count += 1

        return success_count, error_count

    async def ingest_folder(self, folder_id: str, recursive: bool = True,
                          metadata: Optional[Dict] = None) -> Tuple[int, int]:
        """
        Ingest all files from a Google Drive folder.

        Args:
            folder_id: Google Drive folder ID
            recursive: Whether to include subfolders
            metadata: Additional metadata to add to each document

        Returns:
            Tuple of (success_count, error_count)
        """
        print(f"Scanning folder: {folder_id}")
        files = self.list_folder_contents(folder_id, recursive, folder_path="")
        print(f"Found {len(files)} items")

        return await self.ingest_files(files, metadata)


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Ingest documents from Google Drive")
    parser.add_argument("--folder-id", required=True, help="Google Drive folder ID")
    parser.add_argument("--credentials", help="Path to Google OAuth2 credentials JSON file")
    parser.add_argument("--token", help="Path to store OAuth2 token")
    parser.add_argument("--recursive", action="store_true", default=True,
                       help="Include subfolders (default: True)")
    parser.add_argument("--metadata", help="Additional metadata as JSON string")

    args = parser.parse_args()

    # Parse metadata if provided
    metadata = None
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError as e:
            print(f"Error parsing metadata JSON: {e}")
            sys.exit(1)

    # Initialize ingester
    ingester = GoogleDriveIngester(args.credentials, args.token)

    # Authenticate
    print("Authenticating with Google Drive...")
    if not ingester.authenticate():
        print("L Authentication failed")
        sys.exit(1)

    print(" Authentication successful")

    # Ingest folder
    try:
        success_count, error_count = await ingester.ingest_folder(
            args.folder_id,
            recursive=args.recursive,
            metadata=metadata
        )

        print(f"\n=� Ingestion Summary:")
        print(f" Successfully processed: {success_count}")
        print(f"L Errors: {error_count}")
        print(f"=� Total items: {success_count + error_count}")

    except Exception as e:
        print(f"L Ingestion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
