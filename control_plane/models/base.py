"""Base model configuration for security database (control plane)."""

from contextlib import contextmanager

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Define naming convention for constraints
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Metadata for security database (control plane owns this)
metadata = MetaData(naming_convention=convention)
Base = declarative_base(metadata=metadata)

# Database session management
_engine = None
_SessionLocal = None

# Data database session management (for slack_users, etc.)
_data_engine = None
_DataSessionLocal = None


def init_db(database_url: str):
    """Initialize security database connection."""
    global _engine, _SessionLocal  # noqa: PLW0603
    _engine = create_engine(database_url)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def init_data_db(database_url: str):
    """Initialize data database connection."""
    global _data_engine, _DataSessionLocal  # noqa: PLW0603
    _data_engine = create_engine(database_url)
    _DataSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_data_engine)


@contextmanager
def get_db_session(database_url: str | None = None):
    """Get security database session context manager.

    Args:
        database_url: Optional database URL. If not provided, uses SECURITY_DATABASE_URL from env.

    Yields:
        Database session
    """
    global _SessionLocal  # noqa: PLW0602

    if _SessionLocal is None or database_url:
        # Initialize or reinitialize if database_url is provided
        if database_url is None:
            import os

            database_url = os.getenv("SECURITY_DATABASE_URL")
            if not database_url:
                raise ValueError(
                    "SECURITY_DATABASE_URL environment variable not set and no database_url provided"
                )

        init_db(database_url)

    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def get_data_db_session(database_url: str | None = None):
    """Get data database session context manager (for slack_users, etc.).

    Args:
        database_url: Optional database URL. If not provided, uses DATA_DATABASE_URL from env.

    Yields:
        Database session for data database
    """
    global _DataSessionLocal  # noqa: PLW0602

    if _DataSessionLocal is None or database_url:
        if database_url is None:
            import os

            database_url = os.getenv("DATA_DATABASE_URL")
            if not database_url:
                raise ValueError(
                    "DATA_DATABASE_URL environment variable not set and no database_url provided"
                )

        init_data_db(database_url)

    session = _DataSessionLocal()
    try:
        yield session
    finally:
        session.close()
