"""Database migration smoke tests.

Verifies all migrations are applied and schema matches expected state.
"""

import os

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, inspect

DATABASE_URL = os.getenv(
    "SECURITY_DATABASE_URL",
    "mysql+pymysql://root:password@mysql:3306/insightmesh_security"
)


@pytest.mark.smoke
class TestMigrationsApplied:
    """Verify database schema is up to date."""

    @pytest.fixture
    def engine(self):
        """Create database engine."""
        return create_engine(DATABASE_URL)

    def test_alembic_version_exists(self, engine):
        """Alembic version table exists."""
        inspector = inspect(engine)
        assert "alembic_version" in inspector.get_table_names()

    def test_agent_metadata_table_exists(self, engine):
        """Agent metadata table exists."""
        inspector = inspect(engine)
        assert "agent_metadata" in inspector.get_table_names()

    def test_agent_metadata_has_all_columns(self, engine):
        """All expected columns exist in agent_metadata."""
        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("agent_metadata")}

        expected_columns = {
            "id",
            "agent_name",
            "display_name",
            "description",
            "aliases",
            "langgraph_assistant_id",
            "langgraph_url",
            "endpoint_url",
            "is_enabled",
            "is_slack_visible",
            "requires_admin",
            "is_system",
            "is_deleted",
            "aliases_customized",
            "created_at",
            "updated_at",
        }

        missing = expected_columns - columns
        assert not missing, f"Missing columns: {missing}"

    def test_users_table_exists(self, engine):
        """Users table exists."""
        inspector = inspect(engine)
        assert "users" in inspector.get_table_names()

    def test_permission_groups_table_exists(self, engine):
        """Permission groups table exists."""
        inspector = inspect(engine)
        assert "permission_groups" in inspector.get_table_names()

    def test_service_accounts_table_exists(self, engine):
        """Service accounts table exists."""
        inspector = inspect(engine)
        assert "service_accounts" in inspector.get_table_names()


@pytest.mark.smoke
class TestDataDatabase:
    """Verify data database schema."""

    @pytest.fixture
    def data_engine(self):
        """Create data database engine."""
        data_url = os.getenv(
            "DATA_DATABASE_URL",
            "mysql+pymysql://root:password@mysql:3306/insightmesh_data"
        )
        return create_engine(data_url)

    def test_metric_records_table_exists(self, data_engine):
        """Metric records table exists."""
        inspector = inspect(data_engine)
        assert "metric_records" in inspector.get_table_names()

    def test_slack_usage_table_exists(self, data_engine):
        """Slack usage table exists."""
        inspector = inspect(data_engine)
        assert "slack_usage" in inspector.get_table_names()
