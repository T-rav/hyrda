"""Google Workspace sync service for user management."""

import logging
import os
from datetime import datetime
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build

from models import User, get_db_session

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
        """Map Google email to Slack user ID.

        Args:
            google_email: Google Workspace email

        Returns:
            Slack user ID or None if not found

        Note:
            This is a placeholder. You'll need to implement the actual mapping logic:
            - Option 1: Query Slack API by email
            - Option 2: Use a mapping table
            - Option 3: Use email as slack_user_id (if emails match)
        """
        # TODO: Implement actual Slack user lookup
        # For now, use email as slack_user_id
        return google_email

    def sync_users_to_database(self) -> dict:
        """Sync all Google Workspace users to security database.

        Returns:
            Dict with sync statistics
        """
        google_users = self.fetch_all_users()

        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

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

                    # Map to Slack user ID
                    slack_user_id = self.map_google_to_slack(email)
                    if not slack_user_id:
                        logger.warning(f"No Slack user found for {email}, skipping")
                        stats["skipped"] += 1
                        continue

                    # Check if user exists
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

                except Exception as e:
                    logger.error(f"Error syncing user {google_user.get('primaryEmail')}: {e}")
                    stats["errors"] += 1
                    continue

            # Commit all changes
            session.commit()

        logger.info(
            f"User sync complete: {stats['created']} created, {stats['updated']} updated, "
            f"{stats['skipped']} skipped, {stats['errors']} errors"
        )

        return stats


def sync_users_from_google() -> dict:
    """Convenience function to sync users from Google Workspace.

    Returns:
        Dict with sync statistics
    """
    sync_service = GoogleWorkspaceSync()
    return sync_service.sync_users_to_database()
