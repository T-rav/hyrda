"""
Google Drive Client Service

Handles Google Drive API authentication and file operations including:
- OAuth2 authentication with environment variable fallback
- File and folder listing with comprehensive metadata
- File content downloading for various formats
- Permission and sharing information extraction
"""

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .document_processor import DocumentProcessor


class GoogleDriveClient:
    """Service for interacting with Google Drive API."""

    # Define the scopes needed for Google Drive API (including shared drives)
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.metadata.readonly'
    ]

    def __init__(self, credentials_file: str | None = None, token_file: str | None = None):
        """
        Initialize the Google Drive client.

        Args:
            credentials_file: Path to Google OAuth2 credentials JSON file
            token_file: Path to store/retrieve OAuth2 token
        """
        self.credentials_file = credentials_file or 'credentials.json'
        self.token_file = token_file or 'auth/token.json'
        self.service = None
        self.document_processor = DocumentProcessor()

    def authenticate(self) -> bool:
        """
        Authenticate with Google Drive API using OAuth2 or environment variables.

        Returns:
            bool: True if authentication successful, False otherwise
        """
        creds = None

        # Try environment variables first
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        refresh_token = os.getenv('GOOGLE_REFRESH_TOKEN')

        if client_id and client_secret and refresh_token:
            print("Using credentials from environment variables...")
            try:
                creds = Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    id_token=None,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=self.SCOPES
                )
                creds.refresh(Request())
                print("✅ Environment credentials authenticated successfully")
            except Exception as e:
                print(f"❌ Environment credentials failed: {e}")
                return False
        else:
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
                    print("\n❌ No OAuth2 credentials found.")
                    print("📝 To create a login screen like n8n, we need OAuth2 app credentials.")
                    print("\n🚀 One-time setup:")
                    print("1. Go to: https://console.cloud.google.com/")
                    print("2. Create project → Enable Google Drive API → Create OAuth2 Desktop credentials")
                    print("3. Download as 'credentials.json' and put it in this folder")
                    print("4. After that, this will work like n8n - just login once!")
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
                # Create auth directory if it doesn't exist
                os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
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

    def list_folder_contents(self, folder_id: str, recursive: bool = True, folder_path: str = "") -> list[dict]:
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

            if folder_path == "":  # Only debug for root folder to avoid spam
                print(f"🔍 Querying Google Drive with: {query}")

            # For shared drives, we need different approaches for root vs subfolders
            results = None
            try:
                if folder_path == "":
                    # For root folder, use the broader query approach
                    print("🔄 Using broad shared drive query for root folder...")
                    all_results = self.service.files().list(
                        q="trashed=false",
                        pageSize=1000,
                        includeItemsFromAllDrives=True,
                        supportsAllDrives=True,
                        fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, parents, permissions, owners, createdTime, webViewLink)"
                    ).execute()

                    # Filter to only files that have our folder_id as parent
                    all_files = all_results.get('files', [])
                    filtered_files = [f for f in all_files if folder_id in f.get('parents', [])]
                    results = {'files': filtered_files}
                else:
                    # For subfolders, use the specific parent query with shared drive support
                    print(f"🔄 Using specific parent query for subfolder: {folder_path}")
                    results = self.service.files().list(
                        q=query,
                        pageSize=1000,
                        includeItemsFromAllDrives=True,
                        supportsAllDrives=True,
                        fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, parents, permissions, owners, createdTime, webViewLink)"
                    ).execute()

                # Get files from results (different handling for root vs subfolder)
                if folder_path == "":
                    # Root folder: we already have filtered_files
                    pass
                else:
                    # Subfolder: get files directly from results
                    filtered_files = results.get('files', [])

                # Debug: if no items found for subfolders
                if len(filtered_files) == 0 and folder_path != "":
                    print(f"🔍 DEBUG: No items found for folder_id '{folder_id}' in folder_path '{folder_path}'")
                    print(f"🔍 DEBUG: Query used: {query}")
                    print("🔍 DEBUG: This suggests the folder may be empty or there's a permissions issue")

                if folder_path == "":
                    print(f"✅ Found {len(all_files)} total accessible files, {len(filtered_files)} in target folder")
                    # Debug: let's see a sample of all accessible files to understand the structure
                    print("🔍 DEBUG: Sample of all accessible files (first 10):")
                    for i, f in enumerate(all_files[:10]):
                        parents_str = ', '.join(f.get('parents', []))
                        print(f"   {i+1}. {f.get('name')} (parents: {parents_str})")
                    if len(all_files) > 10:
                        print(f"   ... and {len(all_files) - 10} more files")
                else:
                    print(f"🔍 Subfolder '{folder_path}': Found {len(filtered_files)} items")

            except HttpError as e:
                # Fallback to original query approach
                if folder_path == "":
                    print(f"⚠️  Broad query failed, trying specific parent query: {e}")

                try:
                    results = self.service.files().list(
                        q=query,
                        pageSize=1000,
                        includeItemsFromAllDrives=True,
                        supportsAllDrives=True,
                        fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, parents, permissions, owners, createdTime, webViewLink)"
                    ).execute()
                    if folder_path == "":
                        print(f"✅ Found {len(results.get('files', []))} items using fallback query")
                except HttpError as e2:
                    if folder_path == "":
                        print(f"❌ All query methods failed: {e2}")
                    raise e2

            items = filtered_files

            if folder_path == "" and not items:  # Only debug for root folder
                print(f"📂 Google Drive API returned 0 items for folder {folder_id}")

                # Try to get folder info to see if it exists
                try:
                    # Try regular access first
                    folder_info = self.service.files().get(fileId=folder_id, fields="id,name,mimeType,permissions").execute()
                    print(f"📁 Folder exists: '{folder_info.get('name')}' (Type: {folder_info.get('mimeType')})")
                    permissions = folder_info.get('permissions', [])
                    print(f"🔐 Folder has {len(permissions)} permission entries")
                except HttpError:
                    # Try with shared drive support
                    try:
                        folder_info = self.service.files().get(
                            fileId=folder_id,
                            fields="id,name,mimeType,permissions",
                            supportsAllDrives=True
                        ).execute()
                        print(f"📁 Shared Drive folder exists: '{folder_info.get('name')}' (Type: {folder_info.get('mimeType')})")
                        permissions = folder_info.get('permissions', [])
                        print(f"🔐 Folder has {len(permissions)} permission entries")
                    except HttpError as e2:
                        print(f"❌ Cannot access folder {folder_id}: {e2}")
                        print("💡 This might be a permission issue, invalid folder ID, or shared drive access issue")
                        print("💡 For shared drives, make sure your OAuth app has domain-wide delegation or proper permissions")

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
                        fields="permissions",
                        supportsAllDrives=True
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

    def download_file_content(self, file_id: str, mime_type: str) -> str | None:
        """
        Download the content of a file from Google Drive and extract text.

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
            # Handle files that need document processing
            elif mime_type in [
                'application/pdf',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation'
            ] or mime_type.startswith('text/'):
                request = self.service.files().get_media(fileId=file_id)
                content = request.execute()
                return self.document_processor.extract_text(content, mime_type)
            else:
                print(f"Unsupported file type: {mime_type}")
                return None

            # Execute request for Google Apps files
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

    @staticmethod
    def format_permissions(permissions: list[dict]) -> dict:
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

    @staticmethod
    def get_permissions_summary(permissions: list[dict]) -> str:
        """
        Get a simple string summary of Google Drive permissions for Pinecone metadata.

        Args:
            permissions: Raw permissions from Google Drive API

        Returns:
            Simple string summary of permissions
        """
        if not permissions:
            return "no_permissions"

        summary_parts = []
        anyone_access = False
        user_count = 0

        for perm in permissions:
            role = perm.get('role', 'reader')
            perm_type = perm.get('type', 'user')

            if perm_type == 'anyone':
                anyone_access = True
                summary_parts.append(f"anyone_{role}")
            elif perm_type in ['user', 'group']:
                user_count += 1

        if anyone_access and user_count > 0:
            return f"public_plus_{user_count}_users"
        elif anyone_access:
            return "public_access"
        elif user_count > 0:
            return f"private_{user_count}_users"
        else:
            return "restricted"

    @staticmethod
    def get_owner_emails(owners: list[dict]) -> str:
        """
        Get a simple string of owner emails for Pinecone metadata.

        Args:
            owners: Raw owners from Google Drive API

        Returns:
            Comma-separated string of owner emails
        """
        if not owners:
            return "unknown"

        emails = []
        for owner in owners:
            email = owner.get('emailAddress', '')
            if email:
                emails.append(email)

        return ', '.join(emails) if emails else "unknown"
