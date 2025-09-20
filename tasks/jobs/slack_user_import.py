"""Slack user import job for synchronizing user data."""

import logging
from typing import Any, Dict, List, Optional

import requests
from slack_sdk import WebClient

from config.settings import TasksSettings
from .base_job import BaseJob

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

    def validate_params(self) -> bool:
        """Validate job parameters."""
        super().validate_params()

        if not self.settings.slack_bot_token:
            raise ValueError("SLACK_BOT_TOKEN is required for Slack user import")

        return True

    async def _execute_job(self) -> Dict[str, Any]:
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

            # Send users to main bot API for processing
            result = await self._send_users_to_bot_api(filtered_users)

            return {
                "total_users_fetched": len(users_data),
                "filtered_users_count": len(filtered_users),
                "processed_users_count": result.get("processed_count", 0),
                "users_sample": filtered_users[:5],  # First 5 users for debugging
            }

        except Exception as e:
            logger.error(f"Error in Slack user import: {str(e)}")
            raise

    async def _fetch_slack_users(self, include_deactivated: bool) -> List[Dict[str, Any]]:
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
                    batch_users = [user for user in batch_users if not user.get("deleted", False)]

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

    def _filter_users(self, users: List[Dict[str, Any]], user_types: List[str]) -> List[Dict[str, Any]]:
        """Filter users based on user types and other criteria."""
        filtered = []

        for user in users:
            # Skip bots unless specifically requested
            if user.get("is_bot", False) and "bot" not in user_types:
                continue

            # Check user type
            if user.get("is_admin", False) and "admin" not in user_types:
                continue
            elif user.get("is_owner", False) and "owner" not in user_types:
                continue
            elif not any([user.get("is_admin", False), user.get("is_owner", False)]) and "member" not in user_types:
                continue

            # Extract relevant user data
            user_data = {
                "id": user["id"],
                "name": user.get("name"),
                "real_name": user.get("real_name"),
                "display_name": user.get("profile", {}).get("display_name"),
                "email": user.get("profile", {}).get("email"),
                "is_admin": user.get("is_admin", False),
                "is_owner": user.get("is_owner", False),
                "is_bot": user.get("is_bot", False),
                "deleted": user.get("deleted", False),
                "status": user.get("profile", {}).get("status_text"),
                "timezone": user.get("tz"),
                "last_updated": user.get("updated"),
            }

            filtered.append(user_data)

        logger.info(f"Filtered to {len(filtered)} users")
        return filtered

    async def _send_users_to_bot_api(self, users: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Send users to the main bot API for processing/storage."""
        if not self.settings.slack_bot_api_url:
            logger.warning("No bot API URL configured, users will not be sent to main bot")
            return {"processed_count": 0, "message": "No API endpoint configured"}

        try:
            # Prepare API request
            api_url = f"{self.settings.slack_bot_api_url}/api/users/import"
            headers = {"Content-Type": "application/json"}

            if self.settings.slack_bot_api_key:
                headers["Authorization"] = f"Bearer {self.settings.slack_bot_api_key}"

            # Send users in batches to avoid large payloads
            batch_size = 50
            processed_count = 0

            for i in range(0, len(users), batch_size):
                batch = users[i:i + batch_size]

                response = requests.post(
                    api_url,
                    json={"users": batch, "job_id": self.job_id},
                    headers=headers,
                    timeout=30,
                )

                if response.status_code == 200:
                    batch_result = response.json()
                    processed_count += batch_result.get("processed_count", len(batch))
                    logger.info(f"Processed batch {i//batch_size + 1}: {len(batch)} users")
                else:
                    logger.error(
                        f"API request failed for batch {i//batch_size + 1}: "
                        f"{response.status_code} - {response.text}"
                    )

            return {
                "processed_count": processed_count,
                "total_batches": (len(users) + batch_size - 1) // batch_size,
                "api_endpoint": api_url,
            }

        except requests.RequestException as e:
            logger.error(f"Error sending users to bot API: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in API communication: {str(e)}")
            raise