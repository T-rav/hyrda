"""Base model configuration."""

import os
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

metadata = MetaData(naming_convention=convention)
Base = declarative_base(metadata=metadata)

# Database session management
_engine = None
_SessionLocal = None


def init_db(database_url: str) -> None:
    """Initialize database connection with connection pooling."""
    global _engine, _SessionLocal
    _engine = create_engine(
        database_url,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@contextmanager
def get_db_session():
    """Get database session context manager for agent metrics storage.

    Uses SYSTEM_DATABASE_URL to connect to the insightmesh_system database
    where operational metrics like agent_usage are stored. This separates
    system metrics from application data.
    """
    if _SessionLocal is None:
        # Get SYSTEM_DATABASE_URL from environment
        database_url = os.getenv("SYSTEM_DATABASE_URL")
        if not database_url:
            raise ValueError("SYSTEM_DATABASE_URL environment variable not set")
        init_db(database_url)

    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
