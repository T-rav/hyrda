"""Alembic environment configuration for security database (insightmesh_security)."""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import security metadata from bot models
# We need to add bot to sys.path
bot_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "bot"
)
sys.path.insert(0, bot_path)

from models.security_base import security_metadata  # noqa: E402

# Import all security models to ensure they're registered
from models.agent_metadata import AgentMetadata  # noqa: E402, F401
from models.agent_permission import AgentPermission  # noqa: E402, F401
from models.permission_group import (  # noqa: E402, F401
    AgentGroupPermission,
    PermissionGroup,
    UserGroup,
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Define metadata for security database tables
target_metadata = security_metadata


def get_url():
    """Get database URL from environment or config."""
    url = os.getenv("SECURITY_DATABASE_URL")
    if url:
        return url
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
