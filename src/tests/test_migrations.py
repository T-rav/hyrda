import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the parent directory to sys.path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from migrations.migration_manager import Migration, MigrationHistory, MigrationManager
from migrations.registry import register_migrations
from migrations.versions.migration_001_create_user_prompts import CreateUserPromptsTable


@pytest.fixture
def mock_database_url():
    """Mock database URL for testing"""
    return "postgresql+asyncpg://test:test@localhost:5432/test"


@pytest.fixture
def mock_migration_manager():
    """Create mock MigrationManager for testing"""
    manager = MagicMock(spec=MigrationManager)

    # Mock async methods
    manager.initialize = AsyncMock()
    manager.get_applied_migrations = AsyncMock()
    manager.apply_migrations = AsyncMock()
    manager.rollback_migration = AsyncMock()
    manager.get_migration_status = AsyncMock()
    manager.close = AsyncMock()

    return manager


class TestMigration(Migration):
    """Test migration class for testing"""

    def __init__(self):
        super().__init__("999", "Test Migration")
        self.up_called = False
        self.down_called = False

    async def up(self, session):
        """Test up migration"""
        self.up_called = True

    async def down(self, session):
        """Test down migration"""
        self.down_called = True


class TestMigrationManager:
    """Tests for MigrationManager and migration system"""

    @pytest.mark.asyncio
    async def test_migration_manager_initialization(self, mock_database_url):
        """Test MigrationManager initialization"""
        with (
            patch("migrations.migration_manager.create_async_engine") as mock_engine,
            patch("migrations.migration_manager.async_sessionmaker"),
        ):
            manager = MigrationManager(mock_database_url)
            await manager.initialize()

            mock_engine.assert_called_once_with(mock_database_url, echo=False)
            assert len(manager.migrations) == 0  # No migrations added yet

    @pytest.mark.asyncio
    async def test_add_migration(self, mock_database_url):
        """Test adding migrations to manager"""
        with (
            patch("migrations.migration_manager.create_async_engine"),
            patch("migrations.migration_manager.async_sessionmaker"),
        ):
            manager = MigrationManager(mock_database_url)
            test_migration = TestMigration()

            manager.add_migration(test_migration)

            assert len(manager.migrations) == 1
            assert manager.migrations[0] == test_migration
            assert manager.migrations[0].version == "999"

    @pytest.mark.asyncio
    async def test_get_applied_migrations_empty(self, mock_migration_manager):
        """Test getting applied migrations when none exist"""
        mock_migration_manager.get_applied_migrations.return_value = []

        applied = await mock_migration_manager.get_applied_migrations()

        assert applied == []
        mock_migration_manager.get_applied_migrations.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_applied_migrations_with_data(self, mock_migration_manager):
        """Test getting applied migrations when some exist"""
        expected_applied = ["001", "002", "003"]
        mock_migration_manager.get_applied_migrations.return_value = expected_applied

        applied = await mock_migration_manager.get_applied_migrations()

        assert applied == expected_applied
        assert len(applied) == 3
        mock_migration_manager.get_applied_migrations.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_migrations_no_pending(self, mock_migration_manager):
        """Test applying migrations when none are pending"""
        mock_migration_manager.get_applied_migrations.return_value = ["001"]

        await mock_migration_manager.apply_migrations()

        mock_migration_manager.apply_migrations.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_migrations_with_pending(self, mock_migration_manager):
        """Test applying migrations when some are pending"""
        mock_migration_manager.get_applied_migrations.return_value = (
            []
        )  # No applied migrations

        await mock_migration_manager.apply_migrations()

        mock_migration_manager.apply_migrations.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_migration(self, mock_migration_manager):
        """Test rolling back a specific migration"""
        version = "001"

        await mock_migration_manager.rollback_migration(version)

        mock_migration_manager.rollback_migration.assert_called_once_with(version)

    @pytest.mark.asyncio
    async def test_get_migration_status(self, mock_migration_manager):
        """Test getting migration status"""
        expected_status = {
            "total_migrations": 1,
            "applied_count": 1,
            "pending_count": 0,
            "applied_migrations": ["001"],
            "pending_migrations": [],
            "latest_applied": "001",
        }

        mock_migration_manager.get_migration_status.return_value = expected_status

        status = await mock_migration_manager.get_migration_status()

        assert status == expected_status
        assert status["total_migrations"] == 1
        assert status["applied_count"] == 1
        assert status["pending_count"] == 0
        assert status["latest_applied"] == "001"
        mock_migration_manager.get_migration_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_manager(self, mock_migration_manager):
        """Test closing migration manager"""
        await mock_migration_manager.close()

        mock_migration_manager.close.assert_called_once()

    def test_migration_base_class(self):
        """Test Migration base class"""
        test_migration = TestMigration()

        assert test_migration.version == "999"
        assert test_migration.name == "Test Migration"
        assert test_migration.up_called is False
        assert test_migration.down_called is False

    @pytest.mark.asyncio
    async def test_migration_up_execution(self):
        """Test migration up method execution"""
        test_migration = TestMigration()
        mock_session = AsyncMock()

        await test_migration.up(mock_session)

        assert test_migration.up_called is True

    @pytest.mark.asyncio
    async def test_migration_down_execution(self):
        """Test migration down method execution"""
        test_migration = TestMigration()
        mock_session = AsyncMock()

        await test_migration.down(mock_session)

        assert test_migration.down_called is True


class TestCreateUserPromptsTable:
    """Tests for the initial user_prompts migration"""

    def test_migration_properties(self):
        """Test migration 001 properties"""
        migration = CreateUserPromptsTable()

        assert migration.version == "001"
        assert migration.name == "Create user_prompts table"

    @pytest.mark.asyncio
    async def test_migration_up_sql(self):
        """Test migration 001 up method"""
        migration = CreateUserPromptsTable()
        mock_session = AsyncMock()

        await migration.up(mock_session)

        # Should execute 3 SQL statements (CREATE TABLE + 2 CREATE INDEX)
        assert mock_session.execute.call_count == 3

        # Verify SQL statements contain expected keywords
        call_args = [call[0][0] for call in mock_session.execute.call_args_list]

        # First call should be CREATE TABLE
        assert "CREATE TABLE" in str(call_args[0])
        assert "user_prompts" in str(call_args[0])

        # Second and third calls should be CREATE INDEX
        assert "CREATE INDEX" in str(call_args[1])
        assert "CREATE INDEX" in str(call_args[2])

    @pytest.mark.asyncio
    async def test_migration_down_sql(self):
        """Test migration 001 down method"""
        migration = CreateUserPromptsTable()
        mock_session = AsyncMock()

        await migration.down(mock_session)

        # Should execute 1 SQL statement (DROP TABLE)
        assert mock_session.execute.call_count == 1

        call_args = mock_session.execute.call_args[0][0]
        assert "DROP TABLE" in str(call_args)
        assert "user_prompts" in str(call_args)


class TestMigrationRegistry:
    """Tests for migration registry"""

    def test_register_migrations(self, mock_database_url):
        """Test registering migrations from registry"""
        with (
            patch("migrations.migration_manager.create_async_engine"),
            patch("migrations.migration_manager.async_sessionmaker"),
        ):
            manager = MigrationManager(mock_database_url)
            register_migrations(manager)

            # Should have registered the user_prompts migration
            assert len(manager.migrations) == 1
            assert manager.migrations[0].version == "001"
            assert manager.migrations[0].name == "Create user_prompts table"
            assert isinstance(manager.migrations[0], CreateUserPromptsTable)

    def test_migration_ordering(self, mock_database_url):
        """Test that migrations are ordered by version"""
        with (
            patch("migrations.migration_manager.create_async_engine"),
            patch("migrations.migration_manager.async_sessionmaker"),
        ):
            manager = MigrationManager(mock_database_url)

            # Add migrations out of order
            migration_003 = TestMigration()
            migration_003.version = "003"
            migration_002 = TestMigration()
            migration_002.version = "002"
            migration_001 = CreateUserPromptsTable()

            manager.add_migration(migration_003)
            manager.add_migration(migration_002)
            manager.add_migration(migration_001)

            # Should be sorted by version
            assert len(manager.migrations) == 3
            assert manager.migrations[0].version == "001"
            assert manager.migrations[1].version == "002"
            assert manager.migrations[2].version == "003"


class TestMigrationHistory:
    """Tests for MigrationHistory model"""

    def test_migration_history_model_fields(self):
        """Test MigrationHistory model has expected fields"""
        expected_fields = ["id", "version", "name", "applied_at"]

        actual_fields = list(MigrationHistory.__annotations__.keys())
        for field in expected_fields:
            assert field in actual_fields

    def test_migration_history_table_name(self):
        """Test MigrationHistory table name"""
        assert MigrationHistory.__tablename__ == "migration_history"


class TestMigrationErrorHandling:
    """Tests for migration error scenarios"""

    @pytest.mark.asyncio
    async def test_migration_execution_error(self, mock_migration_manager):
        """Test handling migration execution errors"""
        mock_migration_manager.apply_migrations.side_effect = Exception(
            "Migration failed"
        )

        with pytest.raises(Exception, match="Migration failed"):
            await mock_migration_manager.apply_migrations()

    @pytest.mark.asyncio
    async def test_rollback_error(self, mock_migration_manager):
        """Test handling rollback errors"""
        mock_migration_manager.rollback_migration.side_effect = Exception(
            "Rollback failed"
        )

        with pytest.raises(Exception, match="Rollback failed"):
            await mock_migration_manager.rollback_migration("001")

    @pytest.mark.asyncio
    async def test_database_connection_error(self, mock_migration_manager):
        """Test handling database connection errors"""
        mock_migration_manager.initialize.side_effect = Exception("Connection failed")

        with pytest.raises(Exception, match="Connection failed"):
            await mock_migration_manager.initialize()
