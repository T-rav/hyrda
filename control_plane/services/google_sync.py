"""Google Workspace sync service for user management.

Syncs users from Google Workspace to the security database and links them
to the slack_users table in the data database via slack_user_id.
"""

import logging
import os
from datetime import datetime
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from sqlalchemy import text

from models import User, get_data_db_session, get_db_session

logger = logging.getLogger(__name__)


class GoogleWorkspaceSync:
    """Sync users from Google Workspace to security database."""

    SCOPES = ["https://www.googleapis.com/auth/admin.directory.user.readonly"]

    def __init__(self, credentials_path: Optional[str] = None):
        """Initialize Google Workspace sync.

        Args:
            credentials_path: Path to service account JSON file.
                             If not provided, uses GOOGLE_SERVICE_ACCOUNT_FILE env var.
        """
        self.credentials_path = credentials_path or os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_FILE"
        )
        if not self.credentials_path:
            raise ValueError(
                "Google service account credentials required. Set GOOGLE_SERVICE_ACCOUNT_FILE or pass credentials_path."
            )

        # Admin email for delegated access (required for Admin SDK)
        self.admin_email = os.getenv("GOOGLE_ADMIN_EMAIL")
        if not self.admin_email:
            raise ValueError(
                "GOOGLE_ADMIN_EMAIL environment variable required for delegated access"
            )

        self.service = None

    def _get_service(self):
        """Get Google Admin SDK service with delegated credentials."""
        if self.service:
            return self.service

        credentials = service_account.Credentials.from_service_account_file(
            self.credentials_path, scopes=self.SCOPES
        )

        # Delegate to admin user
        delegated_credentials = credentials.with_subject(self.admin_email)

        self.service = build("admin", "directory_v1", credentials=delegated_credentials)
        return self.service

    def fetch_all_users(self) -> list[dict]:
        """Fetch all users from Google Workspace.

        Returns:
            List of user dicts with Google Workspace data
        """
        service = self._get_service()
        users = []

        try:
            # Fetch all users (paginated)
            request = service.users().list(
                customer="my_customer", maxResults=500, orderBy="email"
            )

            while request is not None:
                response = request.execute()
                users.extend(response.get("users", []))
                request = service.users().list_next(request, response)

            logger.info(f"Fetched {len(users)} users from Google Workspace")
            return users

        except Exception as e:
            logger.error(f"Error fetching users from Google: {e}", exc_info=True)
            raise

    def map_google_to_slack(self, google_email: str) -> Optional[str]:
        """Map Google email to Slack user ID via slack_users table in data database.

        Args:
            google_email: Google Workspace email

        Returns:
            Slack user ID or None if not found
        """
        try:
            with get_data_db_session() as session:
                # Query slack_users table in data database
                result = session.execute(
                    text(
                        """
                        SELECT slack_user_id
                        FROM slack_users
                        WHERE email_address = :email
                        AND is_bot = 0
                        AND user_type != 'bot'
                        LIMIT 1
                        """
                    ),
                    {"email": google_email},
                )

                row = result.fetchone()
                if row:
                    slack_user_id = row[0]
                    logger.debug(f"Mapped {google_email} → {slack_user_id}")
                    return slack_user_id
                else:
                    logger.warning(f"No Slack user found for {google_email}")
                    return None

        except Exception as e:
            logger.error(f"Error mapping {google_email} to Slack: {e}")
            return None

    def sync_users_to_database(self) -> dict:
        """Sync all Google Workspace users to security database.

        Links users to slack_users table in data database via slack_user_id.

        Returns:
            Dict with sync statistics
        """
        google_users = self.fetch_all_users()

        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0, "deactivated": 0}

        # Track Google IDs we've seen to detect deletions
        synced_google_ids = set()

        with get_db_session() as session:
            for google_user in google_users:
                try:
                    # Extract Google data
                    google_id = google_user.get("id")
                    email = google_user["primaryEmail"]
                    full_name = google_user.get("name", {}).get("fullName", email)
                    given_name = google_user.get("name", {}).get("givenName")
                    family_name = google_user.get("name", {}).get("familyName")
                    is_active = not google_user.get("suspended", False)
                    is_admin = google_user.get("isAdmin", False)

                    # Map to Slack user ID from data database
                    slack_user_id = self.map_google_to_slack(email)
                    if not slack_user_id:
                        logger.warning(f"No Slack user found for {email}, skipping")
                        stats["skipped"] += 1
                        continue

                    # Check if user exists in security database
                    existing_user = (
                        session.query(User)
                        .filter(User.slack_user_id == slack_user_id)
                        .first()
                    )

                    if existing_user:
                        # Update existing user
                        existing_user.google_id = google_id
                        existing_user.email = email
                        existing_user.full_name = full_name
                        existing_user.given_name = given_name
                        existing_user.family_name = family_name
                        existing_user.is_active = is_active
                        existing_user.is_admin = is_admin
                        existing_user.last_synced_at = datetime.utcnow()
                        stats["updated"] += 1
                    else:
                        # Create new user
                        new_user = User(
                            slack_user_id=slack_user_id,
                            google_id=google_id,
                            email=email,
                            full_name=full_name,
                            given_name=given_name,
                            family_name=family_name,
                            is_active=is_active,
                            is_admin=is_admin,
                            last_synced_at=datetime.utcnow(),
                        )
                        session.add(new_user)
                        stats["created"] += 1

                    # Track this Google ID
                    if google_id:
                        synced_google_ids.add(google_id)

                except Exception as e:
                    logger.error(f"Error syncing user {google_user.get('primaryEmail')}: {e}")
                    stats["errors"] += 1
                    continue

            # Deactivate users no longer in Google Workspace
            db_users = session.query(User).filter(User.google_id.isnot(None)).all()
            for db_user in db_users:
                if db_user.google_id not in synced_google_ids and db_user.is_active:
                    logger.info(f"Deactivating user {db_user.email} (no longer in Google)")
                    db_user.is_active = False
                    db_user.last_synced_at = datetime.utcnow()
                    stats["deactivated"] += 1

            # Commit all changes
            session.commit()

        logger.info(
            f"User sync complete: {stats['created']} created, {stats['updated']} updated, "
            f"{stats['skipped']} skipped, {stats['deactivated']} deactivated, {stats['errors']} errors"
        )

        return stats


def sync_users_from_google() -> dict:
    """Convenience function to sync users from Google Workspace.

    Returns:
        Dict with sync statistics
    """
    sync_service = GoogleWorkspaceSync()
    return sync_service.sync_users_to_database()
