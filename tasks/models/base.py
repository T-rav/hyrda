"""Base model configuration."""

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

# Data database session management (for sec_documents_data, etc.)
_data_engine = None
_DataSessionLocal = None


def init_db(database_url: str) -> None:
    """Initialize database connection with connection pooling."""
    global _engine, _SessionLocal

    # SQLite doesn't support connection pooling parameters
    if database_url.startswith("sqlite"):
        _engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},  # Allow multi-threading for SQLite
        )
    else:
        _engine = create_engine(
            database_url,
            pool_size=20,  # Max persistent connections
            max_overflow=10,  # Additional connections when pool exhausted
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,  # Recycle connections after 1 hour
        )
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def init_data_db(database_url: str) -> None:
    """Initialize data database connection with connection pooling."""
    global _data_engine, _DataSessionLocal

    # SQLite doesn't support connection pooling parameters
    if database_url.startswith("sqlite"):
        _data_engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},  # Allow multi-threading for SQLite
        )
    else:
        _data_engine = create_engine(
            database_url,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    _DataSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=_data_engine
    )


@contextmanager
def get_db_session():
    """Get database session context manager (task database)."""
    if _SessionLocal is None:
        from config.settings import get_settings

        settings = get_settings()
        init_db(settings.task_database_url)
    elif _engine:
        # Debug: Check if tables exist
        from sqlalchemy import inspect
        inspector = inspect(_engine)
        tables = inspector.get_table_names()
        if not tables:
            # Tables missing - reinitialize and create
            from config.settings import get_settings
            from models.task_metadata import TaskMetadata  # noqa: F401
            from models.task_run import TaskRun  # noqa: F401
            from models.oauth_credential import OAuthCredential  # noqa: F401
            Base.metadata.create_all(bind=_engine)

    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def get_data_db_session():
    """Get database session context manager (data database for SEC documents, etc.)."""
    if _DataSessionLocal is None:
        from config.settings import get_settings

        settings = get_settings()
        init_data_db(settings.data_database_url)

    session = _DataSessionLocal()
    try:
        yield session
    finally:
        session.close()
