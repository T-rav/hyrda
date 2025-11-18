"""Integration tests for user sync with identity linking.

Tests the complete sync flow including:
- Creating users and identities
- Linking multiple provider identities
- Migration scenarios (Slack → Google)
- Deactivation logic
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, User, UserIdentity
from services.user_sync import sync_users_from_provider


@pytest.fixture
def test_engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def test_session(test_engine):
    """Create test database session."""
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def mock_slack_provider():
    """Mock Slack provider with test users."""
    mock = MagicMock()
    mock.fetch_users.return_value = [
        {
            "id": "U123",
            "profile": {"email": "alice@example.com", "real_name": "Alice Smith"},
            "is_bot": False,
            "deleted": False,
        },
        {
            "id": "U456",
            "profile": {"email": "bob@example.com", "real_name": "Bob Jones"},
            "is_bot": False,
            "deleted": False,
        },
    ]
    mock.get_user_id = lambda user: user["id"]
    mock.get_user_email = lambda user: user["profile"]["email"]
    mock.get_user_name = lambda user: user["profile"]["real_name"]
    mock.is_bot = lambda user: user["is_bot"]
    mock.is_deleted = lambda user: user["deleted"]
    return mock


class TestUserSyncIntegration:
    """Integration tests for user sync with identity linking."""

    @patch("services.user_sync.get_db_session")
    @patch("services.user_sync.get_user_provider")
    def test_sync_creates_new_users_with_identities(
        self, mock_get_provider, mock_get_session, test_session, mock_slack_provider
    ):
        """Test syncing creates new users and their primary identities."""
        mock_get_provider.return_value = mock_slack_provider
        mock_get_session.return_value.__enter__.return_value = test_session

        stats = sync_users_from_provider("slack")

        assert stats["created"] == 2
        assert stats["identities_created"] == 2
        assert stats["updated"] == 0
        assert stats["errors"] == 0

        # Verify users created
        users = test_session.query(User).all()
        assert len(users) == 2

        # Verify identities created
        identities = test_session.query(UserIdentity).all()
        assert len(identities) == 2

        # Verify identity linking
        alice_user = test_session.query(User).filter(User.email == "alice@example.com").first()
        assert alice_user is not None
        assert alice_user.primary_provider == "slack"
        assert len(alice_user.identities) == 1
        assert alice_user.identities[0].provider_type == "slack"
        assert alice_user.identities[0].provider_user_id == "U123"
        assert alice_user.identities[0].is_primary is True

    @patch("services.user_sync.get_db_session")
    @patch("services.user_sync.get_user_provider")
    def test_sync_links_new_provider_to_existing_user(
        self, mock_get_provider, mock_get_session, test_session
    ):
        """Test syncing with new provider links identity to existing user."""
        # Create existing user with Slack identity
        user = User(
            slack_user_id="U123",
            email="alice@example.com",
            full_name="Alice Smith",
            primary_provider="slack",
            is_active=True,
            is_admin=False,
            last_synced_at=datetime.utcnow(),
        )
        test_session.add(user)
        test_session.flush()

        slack_identity = UserIdentity(
            user_id=user.id,
            provider_type="slack",
            provider_user_id="U123",
            provider_email="alice@example.com",
            display_name="Alice Smith",
            is_primary=True,
            is_active=True,
            last_synced_at=datetime.utcnow(),
        )
        test_session.add(slack_identity)
        test_session.commit()

        # Mock Google provider with same email
        mock_google = MagicMock()
        mock_google.fetch_users.return_value = [
            {
                "id": "google-123",
                "primaryEmail": "alice@example.com",
                "name": {"fullName": "Alice Smith"},
            }
        ]
        mock_google.get_user_id = lambda user: user["id"]
        mock_google.get_user_email = lambda user: user["primaryEmail"]
        mock_google.get_user_name = lambda user: user["name"]["fullName"]
        mock_google.is_bot = lambda user: False
        mock_google.is_deleted = lambda user: False

        mock_get_provider.return_value = mock_google
        mock_get_session.return_value.__enter__.return_value = test_session

        stats = sync_users_from_provider("google")

        assert stats["created"] == 0  # No new user
        assert stats["identities_created"] == 1  # New identity linked
        assert stats["updated"] == 0

        # Verify identity was linked
        user = test_session.query(User).filter(User.email == "alice@example.com").first()
        assert len(user.identities) == 2

        google_identity = [i for i in user.identities if i.provider_type == "google"][0]
        assert google_identity.provider_user_id == "google-123"
        assert google_identity.is_primary is False  # Slack is still primary

    @patch("services.user_sync.get_db_session")
    @patch("services.user_sync.get_user_provider")
    def test_sync_updates_existing_identities(
        self, mock_get_provider, mock_get_session, test_session, mock_slack_provider
    ):
        """Test syncing updates existing identities."""
        # Create existing user with identity
        user = User(
            slack_user_id="U123",
            email="alice@old-email.com",  # Old email
            full_name="Alice Old Name",
            primary_provider="slack",
            is_active=True,
            is_admin=False,
            last_synced_at=datetime.utcnow(),
        )
        test_session.add(user)
        test_session.flush()

        identity = UserIdentity(
            user_id=user.id,
            provider_type="slack",
            provider_user_id="U123",
            provider_email="alice@old-email.com",
            display_name="Alice Old Name",
            is_primary=True,
            is_active=True,
            last_synced_at=datetime.utcnow(),
        )
        test_session.add(identity)
        test_session.commit()

        mock_get_provider.return_value = mock_slack_provider
        mock_get_session.return_value.__enter__.return_value = test_session

        stats = sync_users_from_provider("slack")

        assert stats["created"] == 1  # Bob is new
        assert stats["identities_updated"] == 1  # Alice updated
        assert stats["updated"] == 1  # Alice user updated

        # Verify user was updated
        user = test_session.query(User).filter(User.slack_user_id == "U123").first()
        assert user.email == "alice@example.com"  # Updated
        assert user.full_name == "Alice Smith"  # Updated

    @patch("services.user_sync.get_db_session")
    @patch("services.user_sync.get_user_provider")
    @patch.dict("os.environ", {"ALLOWED_EMAIL_DOMAIN": "@example.com"})
    def test_sync_filters_by_email_domain(
        self, mock_get_provider, mock_get_session, test_session
    ):
        """Test syncing respects email domain filter."""
        mock = MagicMock()
        mock.fetch_users.return_value = [
            {
                "id": "U123",
                "profile": {"email": "alice@example.com", "real_name": "Alice"},
                "is_bot": False,
                "deleted": False,
            },
            {
                "id": "U456",
                "profile": {"email": "bob@other.com", "real_name": "Bob"},
                "is_bot": False,
                "deleted": False,
            },
        ]
        mock.get_user_id = lambda user: user["id"]
        mock.get_user_email = lambda user: user["profile"]["email"]
        mock.get_user_name = lambda user: user["profile"]["real_name"]
        mock.is_bot = lambda user: user["is_bot"]
        mock.is_deleted = lambda user: user["deleted"]

        mock_get_provider.return_value = mock
        mock_get_session.return_value.__enter__.return_value = test_session

        stats = sync_users_from_provider("slack")

        assert stats["created"] == 1  # Only alice@example.com
        assert stats["skipped"] == 1  # bob@other.com skipped

        users = test_session.query(User).all()
        assert len(users) == 1
        assert users[0].email == "alice@example.com"

    @patch("services.user_sync.get_db_session")
    @patch("services.user_sync.get_user_provider")
    def test_sync_deactivates_removed_identities(
        self, mock_get_provider, mock_get_session, test_session, mock_slack_provider
    ):
        """Test syncing deactivates identities no longer in provider."""
        # Create user with identity
        user = User(
            slack_user_id="U999",
            email="removed@example.com",
            full_name="Removed User",
            primary_provider="slack",
            is_active=True,
            is_admin=False,
            last_synced_at=datetime.utcnow(),
        )
        test_session.add(user)
        test_session.flush()

        identity = UserIdentity(
            user_id=user.id,
            provider_type="slack",
            provider_user_id="U999",
            provider_email="removed@example.com",
            display_name="Removed User",
            is_primary=True,
            is_active=True,
            last_synced_at=datetime.utcnow(),
        )
        test_session.add(identity)
        test_session.commit()

        mock_get_provider.return_value = mock_slack_provider  # Doesn't include U999
        mock_get_session.return_value.__enter__.return_value = test_session

        stats = sync_users_from_provider("slack")

        assert stats["deactivated"] == 1

        # Verify identity and user deactivated
        identity = test_session.query(UserIdentity).filter(
            UserIdentity.provider_user_id == "U999"
        ).first()
        assert identity.is_active is False

        user = test_session.query(User).filter(User.email == "removed@example.com").first()
        assert user.is_active is False


class TestMigrationScenarios:
    """Test migration scenarios (Slack → Google, etc.)."""

    @patch("services.user_sync.get_db_session")
    @patch("services.user_sync.get_user_provider")
    def test_migration_slack_to_google(
        self, mock_get_provider, mock_get_session, test_session
    ):
        """Test migrating from Slack to Google while maintaining both."""
        # Step 1: Initial sync with Slack
        mock_slack = MagicMock()
        mock_slack.fetch_users.return_value = [
            {
                "id": "U123",
                "profile": {"email": "alice@example.com", "real_name": "Alice Smith"},
                "is_bot": False,
                "deleted": False,
            }
        ]
        mock_slack.get_user_id = lambda user: user["id"]
        mock_slack.get_user_email = lambda user: user["profile"]["email"]
        mock_slack.get_user_name = lambda user: user["profile"]["real_name"]
        mock_slack.is_bot = lambda user: user["is_bot"]
        mock_slack.is_deleted = lambda user: user["deleted"]

        mock_get_provider.return_value = mock_slack
        mock_get_session.return_value.__enter__.return_value = test_session

        stats1 = sync_users_from_provider("slack")
        assert stats1["created"] == 1

        # Verify Slack identity is primary
        user = test_session.query(User).filter(User.email == "alice@example.com").first()
        assert user.primary_provider == "slack"
        assert len(user.identities) == 1

        # Step 2: Add Google identity
        mock_google = MagicMock()
        mock_google.fetch_users.return_value = [
            {
                "id": "google-123",
                "primaryEmail": "alice@example.com",
                "name": {"fullName": "Alice Smith"},
            }
        ]
        mock_google.get_user_id = lambda user: user["id"]
        mock_google.get_user_email = lambda user: user["primaryEmail"]
        mock_google.get_user_name = lambda user: user["name"]["fullName"]
        mock_google.is_bot = lambda user: False
        mock_google.is_deleted = lambda user: False

        mock_get_provider.return_value = mock_google

        stats2 = sync_users_from_provider("google")
        assert stats2["created"] == 0
        assert stats2["identities_created"] == 1

        # Verify both identities exist
        user = test_session.query(User).first()
        assert len(user.identities) == 2
        assert user.primary_provider == "slack"  # Still Slack

        slack_identity = [i for i in user.identities if i.provider_type == "slack"][0]
        google_identity = [i for i in user.identities if i.provider_type == "google"][0]

        assert slack_identity.is_primary is True
        assert google_identity.is_primary is False
        assert slack_identity.is_active is True
        assert google_identity.is_active is True
