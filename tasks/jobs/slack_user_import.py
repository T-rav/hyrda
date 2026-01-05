"""Slack user import job for synchronizing user data."""

import logging
from typing import Any

from slack_sdk import WebClient

# Define SlackUser model locally since we're in a separate container
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    create_engine,
    func,
    select,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config.settings import TasksSettings

from .base_job import BaseJob

Base = declarative_base()


class SlackUser(Base):
    """Slack user model for cross-container compatibility."""

    __tablename__ = "slack_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slack_user_id = Column(String(50), unique=True, nullable=False)
    email_address = Column(String(255))
    display_name = Column(String(255))
    real_name = Column(String(255))
    is_active = Column(Boolean, nullable=False, default=True)
    user_type = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


logger = logging.getLogger(__name__)


class SlackUserImportJob(BaseJob):
    """Job to import/sync Slack users to database."""

    JOB_NAME = "Slack User Import"
    JOB_DESCRIPTION = "Import and synchronize Slack user data to database"
    REQUIRED_PARAMS = []
    OPTIONAL_PARAMS = ["workspace_filter", "user_types", "include_deactivated"]

    def __init__(self, settings: TasksSettings, **kwargs: Any):
        """Initialize the Slack user import job."""
        super().__init__(settings, **kwargs)
        self.validate_params()

        # Initialize Slack client if token is available
        self.slack_client = None
        if self.settings.slack_bot_token:
            self.slack_client = WebClient(token=self.settings.slack_bot_token)

        # Store data database URL for later use (don't create engine in __init__)
        self.data_db_url = self.settings.data_database_url

    def validate_params(self) -> bool:
        """Validate job parameters."""
        super().validate_params()

        if not self.settings.slack_bot_token:
            raise ValueError("SLACK_BOT_TOKEN is required for Slack user import")

        return True

    def _get_data_session(self):
        """Create database session for data database when needed."""
        data_engine = create_engine(self.data_db_url)
        DataSession = sessionmaker(bind=data_engine)
        return DataSession()

    async def _execute_job(self) -> dict[str, Any]:
        """Execute the Slack user import job."""
        if not self.slack_client:
            raise RuntimeError("Slack client not initialized")

        # Get job parameters
        workspace_filter = self.params.get("workspace_filter")
        user_types = self.params.get("user_types", ["member", "admin"])
        include_deactivated = self.params.get("include_deactivated", False)

        logger.info(f"Starting Slack user import for workspace: {workspace_filter}")

        try:
            # Fetch users from Slack
            users_data = await self._fetch_slack_users(include_deactivated)

            # Filter users based on parameters
            filtered_users = self._filter_users(users_data, user_types)

            # Store users directly in database
            result = await self._store_users_in_database(filtered_users)

            # Standardized result structure
            processed_count = result.get("processed_count", 0)
            new_count = result.get("new_users_count", 0)
            updated_count = result.get("updated_users_count", 0)
            success_count = new_count + updated_count
            failed_count = max(0, processed_count - success_count)

            return {
                # Standardized fields for task run tracking
                "records_processed": processed_count,
                "records_success": success_count,
                "records_failed": failed_count,
                # Job-specific details for debugging/logging
                "total_users_fetched": len(users_data),
                "filtered_users_count": len(filtered_users),
                "new_users_count": new_count,
                "updated_users_count": updated_count,
                "users_sample": filtered_users[:5],  # First 5 users for debugging
            }

        except Exception as e:
            logger.error(f"Error in Slack user import: {str(e)}")
            raise

    async def _fetch_slack_users(
        self, include_deactivated: bool
    ) -> list[dict[str, Any]]:
        """Fetch users from Slack API."""
        users = []
        cursor = None

        try:
            while True:
                # Call Slack users.list API
                response = self.slack_client.users_list(
                    cursor=cursor, limit=200, include_locale=True
                )

                if not response["ok"]:
                    raise RuntimeError(f"Slack API error: {response['error']}")

                batch_users = response["members"]

                # Filter out deactivated users if not included
                if not include_deactivated:
                    batch_users = [
                        user for user in batch_users if not user.get("deleted", False)
                    ]

                users.extend(batch_users)

                # Check for next page
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            logger.info(f"Fetched {len(users)} users from Slack")
            return users

        except Exception as e:
            logger.error(f"Error fetching users from Slack: {str(e)}")
            raise

    def _filter_users(
        self, users: list[dict[str, Any]], user_types: list[str]
    ) -> list[dict[str, Any]]:
        """Filter users based on user types and other criteria."""
        filtered = []

        for user in users:
            # Skip bots unless specifically requested
            if user.get("is_bot", False) and "bot" not in user_types:
                continue

            # Check user type
            if (
                user.get("is_admin", False)
                and "admin" not in user_types
                or user.get("is_owner", False)
                and "owner" not in user_types
                or (
                    not any([user.get("is_admin", False), user.get("is_owner", False)])
                    and "member" not in user_types
                )
            ):
                continue

            # Extract relevant user data
            deleted_status = user.get("deleted", False)
            is_active_status = not deleted_status
            is_bot_status = user.get("is_bot", False)
            is_admin_status = user.get("is_admin", False)
            is_owner_status = user.get("is_owner", False)

            # Determine user type based on Slack flags (priority order: bot > owner > admin > member)
            if is_bot_status:
                user_type = "bot"
            elif is_owner_status:
                user_type = "owner"
            elif is_admin_status:
                user_type = "admin"
            else:
                user_type = "member"

            user_data = {
                "id": user["id"],
                "name": user.get("name"),
                "real_name": user.get("real_name"),
                "display_name": user.get("profile", {}).get("display_name"),
                "email": user.get("profile", {}).get("email"),
                "deleted": deleted_status,
                "is_active": is_active_status,  # Active = not deleted
                "user_type": user_type,
                "status": user.get("profile", {}).get("status_text"),
                "timezone": user.get("tz"),
                "last_updated": user.get("updated"),
            }

            # Debug logging for inactive users and bots
            if not is_active_status:
                logger.info(
                    f"Processing inactive user: {user_data['id']} - {user_data.get('name')} - deleted: {deleted_status}"
                )
            elif user_type == "bot":
                logger.info(
                    f"Processing bot user: {user_data['id']} - {user_data.get('name')} - type: {user_type}"
                )

            # Debug print to see what's in user_data
            print(f"DEBUG: user_data keys: {list(user_data.keys())}")
            print(
                f"DEBUG: user_data for {user_data['id']}: is_active={user_data.get('is_active')}, user_type={user_data.get('user_type')}"
            )

            filtered.append(user_data)

        logger.info(f"Filtered to {len(filtered)} users")
        return filtered

    async def _store_users_in_database(
        self, users: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Store users directly in the bot database."""
        processed_count = 0
        new_users_count = 0
        updated_users_count = 0

        try:
            with self._get_data_session() as session:
                for user_data in users:
                    # Check if user already exists
                    existing_user = session.execute(
                        select(SlackUser).where(
                            SlackUser.slack_user_id == user_data["id"]
                        )
                    ).scalar_one_or_none()

                    if existing_user:
                        # Update existing user
                        existing_user.email_address = user_data.get("email")
                        existing_user.display_name = user_data.get("display_name")
                        existing_user.real_name = user_data.get("real_name")
                        existing_user.is_active = user_data.get("is_active", True)
                        existing_user.user_type = user_data.get("user_type")
                        updated_users_count += 1
                        print(
                            f"DEBUG: Updating user {user_data['id']} with is_active={user_data.get('is_active')} user_type={user_data.get('user_type')}"
                        )
                        logger.info(
                            f"Updated user: {user_data['id']} (active: {existing_user.is_active}, type: {existing_user.user_type})"
                        )
                    else:
                        # Create new user
                        print(
                            f"DEBUG: Creating new user {user_data['id']} with is_active={user_data.get('is_active')} user_type={user_data.get('user_type')}"
                        )
                        new_user = SlackUser(
                            slack_user_id=user_data["id"],
                            email_address=user_data.get("email"),
                            display_name=user_data.get("display_name"),
                            real_name=user_data.get("real_name"),
                            is_active=user_data.get("is_active", True),
                            user_type=user_data.get("user_type"),
                        )
                        session.add(new_user)
                        new_users_count += 1
                        logger.info(
                            f"Created new user: {user_data['id']} (active: {new_user.is_active}, type: {new_user.user_type})"
                        )

                    processed_count += 1

                # Commit all changes
                session.commit()
                logger.info(f"Successfully stored {processed_count} users in database")

            return {
                "processed_count": processed_count,
                "new_users_count": new_users_count,
                "updated_users_count": updated_users_count,
            }

        except Exception as e:
            logger.error(f"Error storing users in database: {str(e)}")
            raise
