"""
Test script to verify what Google Drive API actually returns for permissions.

Replicates the exact credential retrieval flow from gdrive_ingest.py.
"""

import json
import logging
import os
import sys

import pytest

# Skip this entire test file - requires database with valid OAuth credentials
pytestmark = pytest.mark.skip(reason="Requires database with test credentials")
import tempfile
from pathlib import Path

# Add tasks to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_permissions_api():
    """Test what the Google Drive API actually returns for permissions."""
    from datetime import UTC, datetime, timedelta

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    from models.base import get_db_session
    from models.oauth_credential import OAuthCredential
    from services.encryption_service import get_encryption_service

    # Use the actual credential_id from the database
    credential_id = "e447a6e9-386b-4c6c-b66d-ad13b1da07e8"

    logger.info(f"Loading credential: {credential_id}")
    encryption_service = get_encryption_service()

    with get_db_session() as db_session:
        credential = (
            db_session.query(OAuthCredential)
            .filter(OAuthCredential.credential_id == credential_id)
            .first()
        )

        if not credential:
            raise FileNotFoundError(
                f"Credential not found in database: {credential_id}"
            )

        logger.info(f"Found credential: {credential.credential_name}")
        logger.info(f"Provider: {credential.provider}")
        logger.info(f"Token metadata: {credential.token_metadata}")

        # Decrypt token
        token_json = encryption_service.decrypt(credential.encrypted_token)
        token_data = json.loads(token_json)

        logger.info(f"Token scopes: {token_data.get('scopes', [])}")

        # Check if token needs refresh
        should_refresh = False
        if token_data.get("expiry"):
            try:
                expiry = datetime.fromisoformat(
                    token_data["expiry"].replace("Z", "+00:00")
                )
                now = datetime.now(UTC)
                if expiry <= now + timedelta(minutes=5):
                    should_refresh = True
                    logger.info("Token expired or expiring soon, refreshing...")
            except Exception as e:
                logger.warning(f"Could not parse token expiry: {e}")

        # Refresh if needed
        if should_refresh and token_data.get("refresh_token"):
            try:
                creds = Credentials.from_authorized_user_info(token_data)
                creds.refresh(Request())
                token_json = creds.to_json()
                token_data = json.loads(token_json)
                logger.info("Token refreshed successfully")
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")

    # Create temporary token file (same as job does)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(token_json)
        token_file = f.name

    try:
        # Create Google Drive API service (same way the job does via authenticator)
        creds = Credentials.from_authorized_user_file(token_file)
        service = build("drive", "v3", credentials=creds)

        logger.info("=" * 80)
        logger.info("Testing Google Drive API permissions field")
        logger.info("=" * 80)

        # Test folder ID from production
        folder_id = "0AMXFYdnvxhbpUk9PVA"

        # Get folder info
        logger.info(f"\n1. Getting folder info for: {folder_id}")
        folder_info = (
            service.files()
            .get(
                fileId=folder_id,
                fields="id,name,mimeType,permissions",
                supportsAllDrives=True,
            )
            .execute()
        )

        logger.info(f"   Folder: {folder_info.get('name')}")
        logger.info(f"   Type: {folder_info.get('mimeType')}")
        logger.info(f"   Permissions in basic request: {folder_info.get('permissions', 'MISSING')}")

        # List files in folder
        logger.info(f"\n2. Listing files in folder...")
        query = f"'{folder_id}' in parents and trashed=false"
        results = (
            service.files()
            .list(
                q=query,
                pageSize=5,  # Just first 5 files
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                fields="files(id, name, mimeType, owners, permissions)",
            )
            .execute()
        )

        files = results.get("files", [])
        logger.info(f"   Found {len(files)} files")

        if not files:
            logger.warning("   No files found in folder!")
            return

        # Test detailed permissions call on first file
        test_file = files[0]
        logger.info(f"\n3. Testing detailed permissions on file: {test_file['name']}")
        logger.info(f"   File ID: {test_file['id']}")
        logger.info(f"   From list() call:")
        logger.info(f"     - owners: {test_file.get('owners', 'MISSING')}")
        logger.info(
            f"     - permissions: {test_file.get('permissions', 'MISSING')}"
        )

        # Make the detailed permissions call (what google_drive_api.py does)
        logger.info(f"\n4. Calling get() with fields='permissions(*)'")
        file_permissions = (
            service.files()
            .get(
                fileId=test_file["id"],
                fields="permissions(*)",
                supportsAllDrives=True,
            )
            .execute()
        )

        # Also try getting full file info with ALL fields
        logger.info(f"\n5. Trying to get ALL available fields...")
        try:
            full_file_info = (
                service.files()
                .get(
                    fileId=test_file["id"],
                    fields="*",
                    supportsAllDrives=True,
                )
                .execute()
            )
            logger.info(f"   Available fields: {list(full_file_info.keys())}")
            logger.info(f"   'permissions' field present: {'permissions' in full_file_info}")
            logger.info(f"   'owners' field: {full_file_info.get('owners', 'MISSING')}")
            logger.info(f"   'permissionIds' field: {full_file_info.get('permissionIds', 'MISSING')}")

            # Check if we need to use permissions.list() instead
            logger.info(f"\n6. Trying permissions.list() API...")
            try:
                perms_list = (
                    service.permissions()
                    .list(
                        fileId=test_file["id"],
                        fields="permissions(*)",
                        supportsAllDrives=True,
                    )
                    .execute()
                )
                perm_items = perms_list.get("permissions", [])
                logger.info(f"   permissions.list() returned: {len(perm_items)} permissions")
                if perm_items:
                    logger.info(f"   Sample permission: {perm_items[0]}")
            except Exception as e:
                logger.error(f"   permissions.list() failed: {e}")

        except Exception as e:
            logger.error(f"   Full file info failed: {e}")

        detailed_perms = file_permissions.get("permissions", [])
        logger.info(f"   RESULT: {len(detailed_perms)} permissions returned")

        if detailed_perms:
            logger.info("\n5. Detailed permissions structure:")
            for i, perm in enumerate(detailed_perms[:3]):  # Show first 3
                logger.info(f"\n   Permission {i + 1}:")
                logger.info(f"     - type: {perm.get('type')}")
                logger.info(f"     - role: {perm.get('role')}")
                logger.info(f"     - emailAddress: {perm.get('emailAddress', 'N/A')}")
                logger.info(f"     - displayName: {perm.get('displayName', 'N/A')}")
                logger.info(f"     - domain: {perm.get('domain', 'N/A')}")
                logger.info(f"     - full structure: {perm}")
        else:
            logger.error("\n   ❌ NO PERMISSIONS RETURNED!")
            logger.error(
                "   This explains why owner_emails shows 'unknown'!"
            )

        logger.info("\n" + "=" * 80)
        logger.info("SUMMARY:")
        logger.info("=" * 80)
        logger.info(f"Token scopes: {token_data.get('scopes', [])}")
        logger.info(f"Folder ID: {folder_id}")
        logger.info(f"Files found: {len(files)}")
        logger.info(f"Permissions returned: {len(detailed_perms)}")

        if detailed_perms:
            logger.info("\n✅ SUCCESS: API is returning permissions!")
            logger.info("   The code fix should work once deployed correctly.")
        else:
            logger.error("\n❌ FAILURE: API is NOT returning permissions!")
            logger.error("   Possible causes:")
            logger.error("   - OAuth scopes insufficient")
            logger.error("   - Shared Drive permission structure")
            logger.error("   - API field specification issue")

    finally:
        # Clean up temp file
        if os.path.exists(token_file):
            os.unlink(token_file)
            logger.debug(f"Cleaned up temp token file: {token_file}")


if __name__ == "__main__":
    test_permissions_api()
