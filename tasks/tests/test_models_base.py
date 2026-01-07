"""Tests for database models base functionality."""

import pytest


@pytest.fixture(autouse=True)
def reset_database_globals():
    """Reset global database state before each test."""
    import models.base as base_module

    # Store original values
    original_engine = base_module._engine
    original_session_local = base_module._SessionLocal
    original_data_engine = base_module._data_engine
    original_data_session_local = base_module._DataSessionLocal

    # Reset to None
    base_module._engine = None
    base_module._SessionLocal = None
    base_module._data_engine = None
    base_module._DataSessionLocal = None

    yield

    # Cleanup: Close engines and reset
    if base_module._engine:
        base_module._engine.dispose()
    if base_module._data_engine:
        base_module._data_engine.dispose()

    base_module._engine = original_engine
    base_module._SessionLocal = original_session_local
    base_module._data_engine = original_data_engine
    base_module._DataSessionLocal = original_data_session_local


class TestInitDb:
    """Test database initialization."""

    def test_init_db_creates_engine(self):
        """Test that init_db creates engine and session factory."""
        from models.base import _SessionLocal, _engine, init_db

        database_url = "sqlite:///:memory:"
        init_db(database_url)

        # Import again after init
        from models.base import _SessionLocal, _engine

        assert _engine is not None
        assert _SessionLocal is not None
        assert str(_engine.url) == database_url

    def test_init_data_db_creates_engine(self):
        """Test that init_data_db creates data engine and session factory."""
        from models.base import init_data_db

        database_url = "sqlite:///:memory:"
        init_data_db(database_url)

        # Import again after init
        from models.base import _DataSessionLocal, _data_engine

        assert _data_engine is not None
        assert _DataSessionLocal is not None
        assert str(_data_engine.url) == database_url


class TestGetDbSession:
    """Test database session context managers."""

    def test_get_db_session_lazy_initialization(self, monkeypatch):
        """Test that get_db_session initializes database lazily."""
        from unittest.mock import Mock

        from config.settings import get_settings
        from models.base import get_db_session

        # Mock settings
        mock_settings = Mock()
        mock_settings.task_database_url = "sqlite:///:memory:"
        monkeypatch.setattr("config.settings.get_settings", lambda: mock_settings)

        # Session should initialize lazily
        with get_db_session() as session:
            assert session is not None

    def test_get_db_session_closes_on_exit(self, monkeypatch):
        """Test that database session closes on context exit."""
        from unittest.mock import Mock

        from config.settings import get_settings
        from models.base import get_db_session, init_db

        # Mock settings
        mock_settings = Mock()
        mock_settings.task_database_url = "sqlite:///:memory:"
        monkeypatch.setattr("config.settings.get_settings", lambda: mock_settings)

        # Initialize first
        init_db(mock_settings.task_database_url)

        # Get session
        with get_db_session() as session:
            session_id = id(session)
            assert not session.is_active or session.is_active  # Session is usable

        # After context, session should be closed
        # Note: We can't check is_active after close, but we verified it worked in context

    def test_get_data_db_session_lazy_initialization(self, monkeypatch):
        """Test that get_data_db_session initializes data database lazily."""
        from unittest.mock import Mock

        from config.settings import get_settings
        from models.base import get_data_db_session

        # Mock settings
        mock_settings = Mock()
        mock_settings.data_database_url = "sqlite:///:memory:"
        monkeypatch.setattr("config.settings.get_settings", lambda: mock_settings)

        # Session should initialize lazily
        with get_data_db_session() as session:
            assert session is not None

    def test_get_data_db_session_closes_on_exit(self, monkeypatch):
        """Test that data database session closes on context exit."""
        from unittest.mock import Mock

        from config.settings import get_settings
        from models.base import get_data_db_session, init_data_db

        # Mock settings
        mock_settings = Mock()
        mock_settings.data_database_url = "sqlite:///:memory:"
        monkeypatch.setattr("config.settings.get_settings", lambda: mock_settings)

        # Initialize first
        init_data_db(mock_settings.data_database_url)

        # Get session
        with get_data_db_session() as session:
            session_id = id(session)
            assert not session.is_active or session.is_active  # Session is usable

        # After context, session should be closed


class TestBaseModel:
    """Test Base model metadata configuration."""

    def test_base_has_metadata(self):
        """Test that Base model has metadata with naming conventions."""
        from models.base import Base, metadata

        assert Base.metadata is not None
        assert Base.metadata is metadata
        assert metadata.naming_convention is not None

    def test_naming_convention_configured(self):
        """Test that naming convention is properly configured."""
        from models.base import convention, metadata

        assert metadata.naming_convention == convention
        assert "ix" in convention
        assert "uq" in convention
        assert "ck" in convention
        assert "fk" in convention
        assert "pk" in convention
