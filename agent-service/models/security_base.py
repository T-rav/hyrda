"""Base model configuration for security database."""

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

# Separate metadata for security database
security_metadata = MetaData(naming_convention=convention)
SecurityBase = declarative_base(metadata=security_metadata)

# Security database session management
_security_engine = None
_SecuritySessionLocal = None


def init_security_db(database_url: str):
    """Initialize security database connection."""
    global _security_engine, _SecuritySessionLocal  # noqa: PLW0603
    _security_engine = create_engine(database_url)
    _SecuritySessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=_security_engine
    )


@contextmanager
def get_security_db_session(database_url: str | None = None):
    """Get security database session context manager.

    Args:
        database_url: Optional database URL. If not provided, uses SECURITY_DATABASE_URL from settings.

    Yields:
        Database session for security database
    """
    global _SecuritySessionLocal  # noqa: PLW0602

    if _SecuritySessionLocal is None or database_url:
        # Initialize or reinitialize if database_url is provided
        if database_url is None:
            import os

            database_url = os.getenv("SECURITY_DATABASE_URL")
            if not database_url:
                raise ValueError(
                    "SECURITY_DATABASE_URL environment variable not set and no database_url provided"
                )

        init_security_db(database_url)

    session = _SecuritySessionLocal()
    try:
        yield session
    finally:
        session.close()
