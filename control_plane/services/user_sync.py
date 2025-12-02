"""User sync service with pluggable identity providers.

Syncs users directly from identity providers (Slack, Google Workspace, etc.)
to the security database users table. Supports linking multiple provider
identities to a single user account.
"""

import logging
import os
from datetime import UTC, datetime
from typing import Dict

from sqlalchemy.orm import joinedload

from models import User, UserIdentity, get_db_session
from services.user_providers import get_user_provider

logger = logging.getLogger(__name__)


def sync_users_from_provider(provider_type: str | None = None) -> Dict[str, int]:
    """Sync users from identity provider to security database with identity linking.

    Matches users by email across providers and links multiple identities to
    the same user account. Supports migration scenarios (e.g., start with Slack,
    add Google later).

    Args:
        provider_type: Type of provider ('slack', 'google'). If None, uses
            USER_MANAGEMENT_PROVIDER environment variable

    Returns:
        Dict with sync statistics (created, updated, skipped, deactivated, errors,
                                   identities_created, identities_updated)

    Raises:
        ValueError: If provider configuration is invalid
    """
    stats = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "deactivated": 0,
        "identities_created": 0,
        "identities_updated": 0,
        "errors": 0,
    }

    # Get allowed email domain filter (optional)
    # Use "*" to allow all domains
    allowed_domain = os.getenv("ALLOWED_EMAIL_DOMAIN", "")
    if allowed_domain and allowed_domain != "*":
        logger.info(f"Filtering users by email domain: {allowed_domain}")
    elif allowed_domain == "*":
        logger.info("Accepting users from all email domains (ALLOWED_EMAIL_DOMAIN=*)")
        allowed_domain = ""  # Disable filtering

    try:
        # Get the configured provider
        provider = get_user_provider(provider_type)
        provider_name = provider_type or os.getenv("USER_MANAGEMENT_PROVIDER", "slack")
        logger.info(f"Syncing users from {provider_name} provider")

        # Fetch users from provider
        provider_users = provider.fetch_users()
        logger.info(f"Fetched {len(provider_users)} users from {provider_name}")

        # Track active provider IDs from this sync
        active_provider_ids = set()

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
                    provider_user_id = provider.get_user_id(provider_user)
                    email = provider.get_user_email(provider_user)
                    full_name = provider.get_user_name(provider_user)

                    # Skip users without email
                    if not email:
                        logger.debug(f"Skipping user {provider_user_id} (no email)")
                        stats["skipped"] += 1
                        continue

                    # Apply email domain filter if configured
                    if allowed_domain and not email.endswith(allowed_domain):
                        logger.debug(f"Skipping user {email} (doesn't match domain filter)")
                        stats["skipped"] += 1
                        continue

                    # Track this provider ID as active
                    active_provider_ids.add(provider_user_id)

                    # Check if identity already exists for this provider
                    existing_identity = (
                        session.query(UserIdentity)
                        .filter(
                            UserIdentity.provider_type == provider_name,
                            UserIdentity.provider_user_id == provider_user_id,
                        )
                        .first()
                    )

                    if existing_identity:
                        # Update existing identity
                        existing_identity.provider_email = email
                        existing_identity.display_name = full_name
                        existing_identity.is_active = True
                        existing_identity.last_synced_at = datetime.now(UTC)
                        stats["identities_updated"] += 1

                        # Update parent user if this is the primary identity
                        if existing_identity.is_primary:
                            user = existing_identity.user
                            user.email = email
                            user.full_name = full_name
                            user.is_active = True
                            user.last_synced_at = datetime.now(UTC)
                            stats["updated"] += 1
                            logger.debug(f"Updated user: {email}")

                    else:
                        # Check if user already exists (by email or legacy ID)
                        existing_user = (
                            session.query(User)
                            .filter(User.email == email)
                            .first()
                        )

                        if not existing_user and provider_name == "slack":
                            # For backward compatibility, check slack_user_id
                            existing_user = (
                                session.query(User)
                                .filter(User.slack_user_id == provider_user_id)
                                .first()
                            )

                        if existing_user:
                            # User exists, add new identity
                            new_identity = UserIdentity(
                                user_id=existing_user.id,
                                provider_type=provider_name,
                                provider_user_id=provider_user_id,
                                provider_email=email,
                                display_name=full_name,
                                is_primary=False,  # Existing user keeps their primary
                                is_active=True,
                                last_synced_at=datetime.now(UTC),
                            )
                            session.add(new_identity)
                            stats["identities_created"] += 1
                            logger.debug(f"Linked {provider_name} identity to existing user: {email}")

                        else:
                            # Create new user with identity
                            new_user = User(
                                slack_user_id=provider_user_id if provider_name == "slack" else "",
                                email=email,
                                full_name=full_name,
                                primary_provider=provider_name,
                                is_active=True,
                                is_admin=False,
                                last_synced_at=datetime.now(UTC),
                            )
                            session.add(new_user)
                            session.flush()  # Get user ID

                            # Create primary identity
                            new_identity = UserIdentity(
                                user_id=new_user.id,
                                provider_type=provider_name,
                                provider_user_id=provider_user_id,
                                provider_email=email,
                                display_name=full_name,
                                is_primary=True,
                                is_active=True,
                                last_synced_at=datetime.now(UTC),
                            )
                            session.add(new_identity)
                            stats["created"] += 1
                            stats["identities_created"] += 1
                            logger.debug(f"Created user with {provider_name} identity: {email}")

                except Exception as e:
                    logger.error(f"Error syncing user: {e}", exc_info=True)
                    stats["errors"] += 1
                    continue

            # Deactivate identities no longer in the provider
            # Use joinedload to prevent N+1 query when accessing identity.user
            all_active_identities = (
                session.query(UserIdentity)
                .options(joinedload(UserIdentity.user))
                .filter(
                    UserIdentity.provider_type == provider_name,
                    UserIdentity.is_active,
                )
                .all()
            )

            for identity in all_active_identities:
                if identity.provider_user_id not in active_provider_ids:
                    logger.info(
                        f"Deactivating {provider_name} identity: {identity.provider_email}"
                    )
                    identity.is_active = False
                    identity.last_synced_at = datetime.now(UTC)

                    # If this was the primary identity, deactivate the user
                    if identity.is_primary:
                        identity.user.is_active = False
                        identity.user.last_synced_at = datetime.now(UTC)
                        stats["deactivated"] += 1

            # Commit all changes
            session.commit()

        # Add all active users to the "All Users" system group
        add_all_users_to_system_group()

    except Exception as e:
        logger.error(f"Error during user sync: {e}", exc_info=True)
        raise

    logger.info(
        f"User sync complete: {stats['created']} users created, {stats['updated']} users updated, "
        f"{stats['identities_created']} identities created, {stats['identities_updated']} identities updated, "
        f"{stats['skipped']} skipped, {stats['deactivated']} deactivated, {stats['errors']} errors"
    )

    return stats


def add_all_users_to_system_group() -> None:
    """Add all active users to the 'All Users' system group."""
    try:
        from models import UserGroup, PermissionGroup

        with get_db_session() as session:
            # Get the "all_users" group
            all_users_group = session.query(PermissionGroup).filter(
                PermissionGroup.group_name == "all_users"
            ).first()

            if not all_users_group:
                logger.warning("'All Users' system group not found, skipping auto-assignment")
                return

            # Get all active users
            active_users = session.query(User).filter(User.is_active).all()

            # Get existing memberships
            existing_memberships = session.query(UserGroup).filter(
                UserGroup.group_name == "all_users"
            ).all()
            existing_user_ids = {m.slack_user_id for m in existing_memberships}

            # Add missing users to the group
            added_count = 0
            for user in active_users:
                if user.slack_user_id not in existing_user_ids:
                    new_membership = UserGroup(
                        slack_user_id=user.slack_user_id,
                        group_name="all_users",
                        added_by="system"
                    )
                    session.add(new_membership)
                    added_count += 1

            # Remove inactive users from the group
            removed_count = 0
            active_user_ids = {user.slack_user_id for user in active_users}
            for membership in existing_memberships:
                if membership.slack_user_id not in active_user_ids:
                    session.delete(membership)
                    removed_count += 1

            session.commit()

            if added_count > 0 or removed_count > 0:
                logger.info(
                    f"Updated 'All Users' group: {added_count} users added, {removed_count} users removed"
                )

    except Exception as e:
        logger.error(f"Error adding users to 'All Users' group: {e}", exc_info=True)
