"""
Migration registry - centralized place to register all migrations
"""

from migrations.migration_manager import MigrationManager
from migrations.versions.migration_001_create_user_prompts import CreateUserPromptsTable


def register_migrations(migration_manager: MigrationManager) -> None:
    """Register all migrations with the migration manager"""

    # Register migrations in order
    migration_manager.add_migration(CreateUserPromptsTable())
