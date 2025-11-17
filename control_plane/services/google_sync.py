"""User sync service for control plane.

Syncs users from slack_users table (data database) to users table (security database).
Filters by email domain (configurable), excludes bots, and only includes active users.

TODO: Replace with Google Workspace sync once credentials are configured.
"""

import logging
import os
from datetime import datetime

from sqlalchemy import text

from models import User, get_data_db_session, get_db_session

logger = logging.getLogger(__name__)


def sync_users_to_database() -> dict:
    """Sync users from slack_users table to security database.

    Filters:
    - Only emails matching ALLOWED_EMAIL_DOMAIN (default: @8thlight.com)
    - Excludes bots (is_bot = 0 AND user_type != 'bot')
    - Only active users (is_active = 1)

    Returns:
        Dict with sync statistics
    """
    stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

    # Get allowed email domain from environment (default to @8thlight.com)
    allowed_domain = os.getenv("ALLOWED_EMAIL_DOMAIN", "@8thlight.com")
    logger.info(f"Syncing users with email domain: {allowed_domain}")

    try:
        # Fetch users from slack_users table in data database
        with get_data_db_session() as data_session:
            result = data_session.execute(
                text("""
                    SELECT
                        slack_user_id,
                        email_address,
                        real_name,
                        display_name,
                        is_admin
                    FROM slack_users
                    WHERE is_bot = 0
                    AND user_type != 'bot'
                    AND is_active = 1
                    AND email_address LIKE :domain_pattern
                    ORDER BY email_address
                """),
                {"domain_pattern": f"%{allowed_domain}"}
            )

            slack_users = result.fetchall()
            logger.info(f"Found {len(slack_users)} users matching {allowed_domain} in slack_users table")

            # Sync to security database
            with get_db_session() as security_session:
                for slack_user in slack_users:
                    try:
                        slack_user_id = slack_user[0]
                        email = slack_user[1]
                        real_name = slack_user[2]
                        display_name = slack_user[3]
                        is_admin = bool(slack_user[4])

                        # Use real_name if available, otherwise display_name
                        full_name = real_name or display_name or email

                        # Check if user exists in security database
                        existing_user = (
                            security_session.query(User)
                            .filter(User.slack_user_id == slack_user_id)
                            .first()
                        )

                        if existing_user:
                            # Update existing user
                            existing_user.email = email
                            existing_user.full_name = full_name
                            existing_user.is_active = True
                            existing_user.is_admin = is_admin
                            existing_user.last_synced_at = datetime.utcnow()
                            stats["updated"] += 1
                            logger.debug(f"Updated user: {email}")
                        else:
                            # Create new user
                            new_user = User(
                                slack_user_id=slack_user_id,
                                email=email,
                                full_name=full_name,
                                is_active=True,
                                is_admin=is_admin,
                                last_synced_at=datetime.utcnow(),
                            )
                            security_session.add(new_user)
                            stats["created"] += 1
                            logger.debug(f"Created user: {email}")

                    except Exception as e:
                        logger.error(f"Error syncing user {slack_user[1]}: {e}")
                        stats["errors"] += 1
                        continue

                # Commit all changes
                security_session.commit()

    except Exception as e:
        logger.error(f"Error during user sync: {e}", exc_info=True)
        raise

    logger.info(
        f"User sync complete: {stats['created']} created, {stats['updated']} updated, "
        f"{stats['skipped']} skipped, {stats['errors']} errors"
    )

    return stats


def sync_users_from_google() -> dict:
    """Sync users from slack_users table to security database.

    This function name is kept for backward compatibility with the API endpoint.
    Currently syncs from slack_users table with @8thlight.com filter.

    TODO: Replace with actual Google Workspace sync once credentials are configured.

    Returns:
        Dict with sync statistics
    """
    return sync_users_to_database()
