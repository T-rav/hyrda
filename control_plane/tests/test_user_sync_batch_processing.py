"""Integration tests for user sync batch processing.

Tests verify that batch processing correctly handles:
- Batch boundaries (100, 101, 250 users)
- Session management between batches
- Error handling within batches
- Proper commit behavior per batch
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock, patch

from models import Base, User
from services.user_sync import sync_users_from_provider


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def create_mock_provider_users(count: int) -> list[dict]:
    """Create mock provider users for testing."""
    return [
        {
            "id": f"U{i:05d}",
            "profile": {
                "email": f"user{i}@8thlight.com",
                "real_name": f"Test User {i}",
            },
            "is_bot": False,
            "deleted": False,
        }
        for i in range(count)
    ]


class TestBatchProcessing:
    """Test batch processing with various user counts."""

    def test_batch_processing_exactly_100_users(self, db_session):
        """Test batch processing with exactly 100 users (single batch)."""
        mock_users = create_mock_provider_users(100)
        mock_provider = MagicMock()
        mock_provider.fetch_users.return_value = mock_users
        mock_provider.is_bot.return_value = False
        mock_provider.is_deleted.return_value = False
        mock_provider.get_user_id = lambda u: u["id"]
        mock_provider.get_user_email = lambda u: u["profile"]["email"]
        mock_provider.get_user_name = lambda u: u["profile"]["real_name"]

        with patch("services.user_sync.get_user_provider", return_value=mock_provider):
            with patch("services.user_sync.get_db_session") as mock_get_session:
                mock_get_session.return_value.__enter__.return_value = db_session

                stats = sync_users_from_provider()

                # Verify all users were created
                assert stats["created"] == 100
                assert stats["identities_created"] == 100

                # Verify users exist in database
                user_count = db_session.query(User).count()
                assert user_count == 100

    def test_batch_processing_101_users_crosses_boundary(self, db_session):
        """Test batch processing with 101 users (2 batches: 100 + 1)."""
        mock_users = create_mock_provider_users(101)
        mock_provider = MagicMock()
        mock_provider.fetch_users.return_value = mock_users
        mock_provider.is_bot.return_value = False
        mock_provider.is_deleted.return_value = False
        mock_provider.get_user_id = lambda u: u["id"]
        mock_provider.get_user_email = lambda u: u["profile"]["email"]
        mock_provider.get_user_name = lambda u: u["profile"]["real_name"]

        with patch("services.user_sync.get_user_provider", return_value=mock_provider):
            with patch("services.user_sync.get_db_session") as mock_get_session:
                mock_get_session.return_value.__enter__.return_value = db_session

                stats = sync_users_from_provider()

                # Verify all users were created across both batches
                assert stats["created"] == 101
                assert stats["identities_created"] == 101

                # Verify users exist in database
                user_count = db_session.query(User).count()
                assert user_count == 101

    def test_batch_processing_250_users_multiple_batches(self, db_session):
        """Test batch processing with 250 users (3 batches: 100 + 100 + 50)."""
        mock_users = create_mock_provider_users(250)
        mock_provider = MagicMock()
        mock_provider.fetch_users.return_value = mock_users
        mock_provider.is_bot.return_value = False
        mock_provider.is_deleted.return_value = False
        mock_provider.get_user_id = lambda u: u["id"]
        mock_provider.get_user_email = lambda u: u["profile"]["email"]
        mock_provider.get_user_name = lambda u: u["profile"]["real_name"]

        with patch("services.user_sync.get_user_provider", return_value=mock_provider):
            with patch("services.user_sync.get_db_session") as mock_get_session:
                mock_get_session.return_value.__enter__.return_value = db_session

                stats = sync_users_from_provider()

                # Verify all users were created across all batches
                assert stats["created"] == 250
                assert stats["identities_created"] == 250

                # Verify users exist in database
                user_count = db_session.query(User).count()
                assert user_count == 250

    def test_session_management_across_batches(self, db_session):
        """Test that sessions are properly opened/closed between batches."""
        mock_users = create_mock_provider_users(150)  # 2 batches
        mock_provider = MagicMock()
        mock_provider.fetch_users.return_value = mock_users
        mock_provider.is_bot.return_value = False
        mock_provider.is_deleted.return_value = False
        mock_provider.get_user_id = lambda u: u["id"]
        mock_provider.get_user_email = lambda u: u["profile"]["email"]
        mock_provider.get_user_name = lambda u: u["profile"]["real_name"]

        session_enter_count = 0

        def mock_context_manager():
            nonlocal session_enter_count
            session_enter_count += 1
            return MagicMock(
                __enter__=lambda self: db_session, __exit__=lambda *args: None
            )()

        with patch("services.user_sync.get_user_provider", return_value=mock_provider):
            with patch(
                "services.user_sync.get_db_session", side_effect=mock_context_manager
            ):
                sync_users_from_provider()

                # Verify session context manager was entered multiple times
                # 2 batches + 1 deactivation pass + 1 add_all_users pass = at least 4
                assert session_enter_count >= 4

    def test_error_handling_within_batch(self, db_session):
        """Test that errors in one user don't fail entire batch."""
        mock_users = create_mock_provider_users(10)
        mock_provider = MagicMock()
        mock_provider.fetch_users.return_value = mock_users
        mock_provider.is_bot.return_value = False
        mock_provider.is_deleted.return_value = False
        mock_provider.get_user_id = lambda u: u["id"]
        mock_provider.get_user_name = lambda u: u["profile"]["real_name"]

        # Make get_user_email fail for user 5
        def get_email_with_error(user):
            if user["id"] == "U00005":
                raise ValueError("Email fetch failed")
            return user["profile"]["email"]

        mock_provider.get_user_email = get_email_with_error

        with patch("services.user_sync.get_user_provider", return_value=mock_provider):
            with patch("services.user_sync.get_db_session") as mock_get_session:
                mock_get_session.return_value.__enter__.return_value = db_session

                stats = sync_users_from_provider()

                # Verify 9 users created (1 failed) and 1 error recorded
                assert stats["created"] == 9
                assert stats["errors"] == 1

                # Verify 9 users exist in database
                user_count = db_session.query(User).count()
                assert user_count == 9


class TestBatchCommitBehavior:
    """Test that commits happen per-batch."""

    def test_commits_happen_per_batch(self, db_session):
        """Test that database commits occur after each batch."""
        mock_users = create_mock_provider_users(150)  # 2 batches
        mock_provider = MagicMock()
        mock_provider.fetch_users.return_value = mock_users
        mock_provider.is_bot.return_value = False
        mock_provider.is_deleted.return_value = False
        mock_provider.get_user_id = lambda u: u["id"]
        mock_provider.get_user_email = lambda u: u["profile"]["email"]
        mock_provider.get_user_name = lambda u: u["profile"]["real_name"]

        commit_count = 0
        original_commit = db_session.commit

        def count_commits():
            nonlocal commit_count
            commit_count += 1
            return original_commit()

        # Patch the commit method on the actual session
        db_session.commit = count_commits

        with patch("services.user_sync.get_user_provider", return_value=mock_provider):
            with patch("services.user_sync.get_db_session") as mock_get_session:
                mock_get_session.return_value.__enter__.return_value = db_session
                mock_get_session.return_value.__exit__.return_value = None

                sync_users_from_provider()

                # Verify at least 2 commits for 2 batches (plus cleanup commits)
                assert commit_count >= 2
