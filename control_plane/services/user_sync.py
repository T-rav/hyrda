"""User sync service with pluggable identity providers.

Syncs users directly from identity providers (Slack, Google Workspace, etc.)
to the security database users table.
"""

import logging
import os
from datetime import datetime
from typing import Dict

from models import User, get_db_session
from services.user_providers import get_user_provider

logger = logging.getLogger(__name__)


def sync_users_from_provider(provider_type: str | None = None) -> Dict[str, int]:
    """Sync users from identity provider to security database.

    Args:
        provider_type: Type of provider ('slack', 'google'). If None, uses
            USER_MANAGEMENT_PROVIDER environment variable

    Returns:
        Dict with sync statistics (created, updated, skipped, deactivated, errors)

    Raises:
        ValueError: If provider configuration is invalid
    """
    stats = {"created": 0, "updated": 0, "skipped": 0, "deactivated": 0, "errors": 0}

    # Get allowed email domain filter (optional)
    allowed_domain = os.getenv("ALLOWED_EMAIL_DOMAIN", "")
    if allowed_domain:
        logger.info(f"Filtering users by email domain: {allowed_domain}")

    try:
        # Get the configured provider
        provider = get_user_provider(provider_type)
        provider_name = provider_type or os.getenv("USER_MANAGEMENT_PROVIDER", "slack")
        logger.info(f"Syncing users from {provider_name} provider")

        # Fetch users from provider
        provider_users = provider.fetch_users()
        logger.info(f"Fetched {len(provider_users)} users from {provider_name}")

        # Track active user IDs from this sync
        active_user_ids = set()

        # Sync to security database
        with get_db_session() as session:
            for provider_user in provider_users:
                try:
                    # Skip bots and deleted users
                    if provider.is_bot(provider_user):
                        stats["skipped"] += 1
                        continue

                    if provider.is_deleted(provider_user):
                        stats["skipped"] += 1
                        continue

                    # Extract user data
                    user_id = provider.get_user_id(provider_user)
                    email = provider.get_user_email(provider_user)
                    full_name = provider.get_user_name(provider_user)

                    # Skip users without email
                    if not email:
                        logger.debug(f"Skipping user {user_id} (no email)")
                        stats["skipped"] += 1
                        continue

                    # Apply email domain filter if configured
                    if allowed_domain and not email.endswith(allowed_domain):
                        logger.debug(f"Skipping user {email} (doesn't match domain filter)")
                        stats["skipped"] += 1
                        continue

                    # Track this user as active
                    active_user_ids.add(user_id)

                    # Check if user exists in security database
                    existing_user = (
                        session.query(User)
                        .filter(User.slack_user_id == user_id)
                        .first()
                    )

                    if existing_user:
                        # Update existing user
                        existing_user.email = email
                        existing_user.full_name = full_name
                        existing_user.is_active = True
                        existing_user.last_synced_at = datetime.utcnow()
                        stats["updated"] += 1
                        logger.debug(f"Updated user: {email}")
                    else:
                        # Create new user
                        new_user = User(
                            slack_user_id=user_id,
                            email=email,
                            full_name=full_name,
                            is_active=True,
                            is_admin=False,  # TODO: Extract admin status from provider if available
                            last_synced_at=datetime.utcnow(),
                        )
                        session.add(new_user)
                        stats["created"] += 1
                        logger.debug(f"Created user: {email}")

                except Exception as e:
                    logger.error(f"Error syncing user: {e}")
                    stats["errors"] += 1
                    continue

            # Deactivate users no longer in the provider
            all_active_users = session.query(User).filter(User.is_active == True).all()

            for user in all_active_users:
                if user.slack_user_id not in active_user_ids:
                    logger.info(f"Deactivating user: {user.email} (no longer in {provider_name})")
                    user.is_active = False
                    user.last_synced_at = datetime.utcnow()
                    stats["deactivated"] += 1

            # Commit all changes
            session.commit()

    except Exception as e:
        logger.error(f"Error during user sync: {e}", exc_info=True)
        raise

    logger.info(
        f"User sync complete: {stats['created']} created, {stats['updated']} updated, "
        f"{stats['skipped']} skipped, {stats['deactivated']} deactivated, {stats['errors']} errors"
    )

    return stats
