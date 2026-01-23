"""Tests for models/security_base.py"""

from unittest.mock import Mock, patch

import pytest

from models.security_base import (
    SecurityBase,
    get_security_db_session,
    init_security_db,
    security_metadata,
)


class TestSecurityBase:
    """Tests for security database base configuration."""

    def test_security_metadata_naming_convention(self):
        """Test that security metadata has correct naming convention."""
        assert security_metadata.naming_convention is not None
        assert "ix" in security_metadata.naming_convention
        assert "uq" in security_metadata.naming_convention
        assert "pk" in security_metadata.naming_convention

    def test_security_base_declarative_base(self):
        """Test that SecurityBase is properly configured."""
        assert SecurityBase is not None
        assert hasattr(SecurityBase, "metadata")
        assert SecurityBase.metadata == security_metadata


class TestInitSecurityDb:
    """Tests for init_security_db function."""

    @patch("models.security_base.create_engine")
    @patch("models.security_base.sessionmaker")
    def test_init_security_db(self, mock_sessionmaker, mock_create_engine):
        """Test initializing security database."""
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        mock_session_local = Mock()
        mock_sessionmaker.return_value = mock_session_local

        database_url = "sqlite:///test_security.db"
        init_security_db(database_url)

        # Verify engine created with correct params
        mock_create_engine.assert_called_once_with(
            database_url,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
        )

        # Verify sessionmaker created
        mock_sessionmaker.assert_called_once_with(
            autocommit=False, autoflush=False, bind=mock_engine
        )


class TestGetSecurityDbSession:
    """Tests for get_security_db_session context manager."""

    @patch("models.security_base.init_security_db")
    @patch.dict("os.environ", {"SECURITY_DATABASE_URL": "sqlite:///test.db"})
    def test_get_security_db_session_with_env_var(self, mock_init):
        """Test getting session with SECURITY_DATABASE_URL env var."""
        # Mock the session local
        mock_session = Mock()
        mock_session_local = Mock(return_value=mock_session)

        with patch("models.security_base._SecuritySessionLocal", mock_session_local):
            with get_security_db_session() as session:
                assert session == mock_session

            # Verify session was closed
            mock_session.close.assert_called_once()

    @patch("models.security_base.init_security_db")
    def test_get_security_db_session_with_provided_url(self, mock_init):
        """Test getting session with explicitly provided database_url."""
        mock_session = Mock()
        mock_session_local = Mock(return_value=mock_session)

        with patch("models.security_base._SecuritySessionLocal", mock_session_local):
            database_url = "sqlite:///custom.db"
            with get_security_db_session(database_url) as session:
                assert session == mock_session

            mock_init.assert_called_once_with(database_url)
            mock_session.close.assert_called_once()

    @patch("models.security_base._SecuritySessionLocal", None)
    @patch.dict("os.environ", {}, clear=True)
    def test_get_security_db_session_no_url_raises_error(self):
        """Test that missing database URL raises ValueError."""
        with (
            pytest.raises(ValueError, match="SECURITY_DATABASE_URL"),
            get_security_db_session(),
        ):
            pass

    @patch("models.security_base.init_security_db")
    @patch("models.security_base._SecuritySessionLocal", None)
    def test_get_security_db_session_init_failure(self, mock_init):
        """Test that failed initialization raises RuntimeError."""
        # init_security_db doesn't set _SecuritySessionLocal (simulates failure)
        mock_init.return_value = None

        with (
            patch.dict("os.environ", {"SECURITY_DATABASE_URL": "sqlite:///test.db"}),
            patch("models.security_base._SecuritySessionLocal", None),
            pytest.raises(RuntimeError, match="Failed to initialize"),
            get_security_db_session(),
        ):
            pass

    @patch("models.security_base.init_security_db")
    def test_get_security_db_session_closes_on_exception(self, mock_init):
        """Test that session is closed even when exception occurs."""
        mock_session = Mock()
        mock_session_local = Mock(return_value=mock_session)

        with patch("models.security_base._SecuritySessionLocal", mock_session_local):
            with (
                pytest.raises(ValueError),
                get_security_db_session("sqlite:///test.db"),
            ):
                raise ValueError("Test error")

            # Verify session was still closed
            mock_session.close.assert_called_once()
