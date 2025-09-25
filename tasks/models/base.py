"""Base model configuration."""

from contextlib import contextmanager

from sqlalchemy import MetaData, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

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


def init_db(database_url: str):
    """Initialize database connection."""
    global _engine, _SessionLocal
    _engine = create_engine(database_url)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@contextmanager
def get_db_session():
    """Get database session context manager."""
    if _SessionLocal is None:
        from config.settings import get_settings

        settings = get_settings()
        init_db(settings.database_url)

    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
