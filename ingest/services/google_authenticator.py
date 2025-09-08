"""
Google Authenticator Service

Handles Google OAuth2 authentication flow for Google Drive API access.
Separated from GoogleDriveClient for better separation of concerns.
"""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


class GoogleAuthenticator:
    """Service for handling Google OAuth2 authentication"""

    # Define the scopes needed for Google Drive API (including shared drives)
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.metadata.readonly'
    ]

    def __init__(self, credentials_file: str | None = None, token_file: str | None = None):
        """
        Initialize the Google authenticator.

        Args:
            credentials_file: Path to Google OAuth2 credentials JSON file
            token_file: Path to store/retrieve OAuth2 token
        """
        self.credentials_file = credentials_file or 'credentials.json'
        self.token_file = token_file or 'auth/token.json'

    def authenticate(self) -> Credentials | None:
        """
        Authenticate with Google Drive API using OAuth2 or environment variables.

        Returns:
            Credentials object if successful, None otherwise
        """
        creds = self._try_environment_auth()

        if not creds:
            creds = self._try_token_file_auth()

        if not creds or not creds.valid:
            creds = self._handle_invalid_credentials(creds)

        if creds and creds.valid:
            self._save_credentials(creds)
            return creds

        return None

    def _try_environment_auth(self) -> Credentials | None:
        """Try authentication using environment variables"""
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
                return creds
            except Exception as e:
                print(f"❌ Environment credentials failed: {e}")

        return None

    def _try_token_file_auth(self) -> Credentials | None:
        """Try authentication using saved token file"""
        if os.path.exists(self.token_file):
            return Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
        return None

    def _handle_invalid_credentials(self, creds: Credentials | None) -> Credentials | None:
        """Handle invalid or expired credentials"""
        if creds and creds.expired and creds.refresh_token:
            return self._try_refresh_credentials(creds)
        else:
            return self._run_oauth_flow()

    def _try_refresh_credentials(self, creds: Credentials) -> Credentials | None:
        """Try to refresh expired credentials"""
        try:
            creds.refresh(Request())
            print("✅ Credentials refreshed successfully")
            return creds
        except Exception as e:
            print(f"Error refreshing credentials: {e}")
            return self._run_oauth_flow()

    def _run_oauth_flow(self) -> Credentials | None:
        """Run the OAuth2 flow for new credentials"""
        if not os.path.exists(self.credentials_file):
            self._print_setup_instructions()
            return None

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_file, self.SCOPES)
            creds = flow.run_local_server(port=0)
            print("✅ OAuth2 flow completed successfully")
            return creds
        except Exception as e:
            print(f"Error during OAuth flow: {e}")
            return None

    def _print_setup_instructions(self):
        """Print setup instructions for new users"""
        print("\n❌ No OAuth2 credentials found.")
        print("📝 To create a login screen like n8n, we need OAuth2 app credentials.")
        print("\n🚀 One-time setup:")
        print("1. Go to: https://console.cloud.google.com/")
        print("2. Create project → Enable Google Drive API → Create OAuth2 Desktop credentials")
        print("3. Download as 'credentials.json' and put it in this folder")
        print("4. After that, this will work like n8n - just login once!")

    def _save_credentials(self, creds: Credentials) -> bool:
        """Save credentials to token file"""
        try:
            # Create auth directory if it doesn't exist
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
            return True
        except Exception as e:
            print(f"Error saving token: {e}")
            return False
