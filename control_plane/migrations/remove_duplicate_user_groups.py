"""Migration to remove duplicate user group memberships and add unique constraint.

This migration:
1. Removes duplicate entries in user_groups table
2. Adds unique constraint on (slack_user_id, group_name)

Run with: python migrations/remove_duplicate_user_groups.py
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import UserGroup, get_db_session
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def remove_duplicates():
    """Remove duplicate user group memberships, keeping the oldest entry."""
    with get_db_session() as session:
        # Find duplicates
        duplicate_query = text("""
            SELECT slack_user_id, group_name, COUNT(*) as count
            FROM user_groups
            GROUP BY slack_user_id, group_name
            HAVING COUNT(*) > 1
        """)

        duplicates = session.execute(duplicate_query).fetchall()

        if not duplicates:
            logger.info("No duplicates found")
            return 0

        logger.info(f"Found {len(duplicates)} duplicate user-group combinations")

        total_removed = 0
        for slack_user_id, group_name, count in duplicates:
            logger.info(
                f"Removing {count - 1} duplicate entries for user={slack_user_id}, group={group_name}"
            )

            # Get all entries for this user-group combination
            entries = (
                session.query(UserGroup)
                .filter(
                    UserGroup.slack_user_id == slack_user_id,
                    UserGroup.group_name == group_name,
                )
                .order_by(UserGroup.created_at.asc())  # Keep the oldest
                .all()
            )

            # Delete all but the first (oldest) entry
            for entry in entries[1:]:
                session.delete(entry)
                total_removed += 1

        session.commit()
        logger.info(f"Removed {total_removed} duplicate entries")
        return total_removed


def add_unique_constraint():
    """Add unique constraint to user_groups table."""
    with get_db_session() as session:
        try:
            # Check if constraint already exists
            check_query = text("""
                SELECT COUNT(*)
                FROM information_schema.table_constraints
                WHERE table_name = 'user_groups'
                AND constraint_name = 'uq_user_group'
            """)

            result = session.execute(check_query).scalar()

            if result > 0:
                logger.info("Unique constraint already exists")
                return

            # Add unique constraint
            logger.info("Adding unique constraint...")
            alter_query = text("""
                ALTER TABLE user_groups
                ADD CONSTRAINT uq_user_group UNIQUE (slack_user_id, group_name)
            """)

            session.execute(alter_query)
            session.commit()
            logger.info("Unique constraint added successfully")

        except Exception as e:
            logger.error(f"Error adding unique constraint: {e}")
            logger.info(
                "Constraint might already exist or there might be remaining duplicates"
            )
            session.rollback()


def main():
    """Run the migration."""
    logger.info("Starting migration: remove duplicate user groups")

    try:
        # Step 1: Remove duplicates
        removed_count = remove_duplicates()
        logger.info(f"Migration complete: removed {removed_count} duplicates")

        # Step 2: Add unique constraint
        add_unique_constraint()
        logger.info("Migration successful!")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
