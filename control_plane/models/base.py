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


def init_db(database_url: str):
    """Initialize database connection."""
    global _engine, _SessionLocal  # noqa: PLW0603
    _engine = create_engine(database_url)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@contextmanager
def get_db_session(database_url: str | None = None):
    """Get database session context manager.

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
