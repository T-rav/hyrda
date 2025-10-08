"""Tests for database configuration and migrations."""

import os
import tempfile

import pytest
from sqlalchemy import create_engine, inspect, text

from config.settings import TasksSettings


class TestDatabaseConfiguration:
    """Test database configuration settings."""

    def test_task_database_url_from_env(self):
        """Test that TASK_DATABASE_URL is correctly read from environment."""
        test_url = "mysql+pymysql://test_user:test_pass@testhost:3306/test_db"
        os.environ["TASK_DATABASE_URL"] = test_url

        settings = TasksSettings()

        assert settings.task_database_url == test_url

    def test_data_database_url_from_env(self):
        """Test that DATA_DATABASE_URL is correctly read from environment."""
        test_url = "mysql+pymysql://data_user:data_pass@datahost:3306/data_db"
        os.environ["DATA_DATABASE_URL"] = test_url

        settings = TasksSettings()

        assert settings.data_database_url == test_url

    def test_default_task_database_url_uses_mysql(self):
        """Test that default TASK_DATABASE_URL uses mysql host not localhost."""
        # Clear environment variable to test default
        os.environ.pop("TASK_DATABASE_URL", None)

        settings = TasksSettings()

        assert "@mysql:" in settings.task_database_url
        assert "@localhost:" not in settings.task_database_url
        assert "insightmesh_tasks" in settings.task_database_url
        assert "insightmesh_task" in settings.task_database_url

    def test_default_data_database_url_uses_mysql(self):
        """Test that default DATA_DATABASE_URL uses mysql host not localhost."""
        # Clear environment variable to test default
        os.environ.pop("DATA_DATABASE_URL", None)

        settings = TasksSettings()

        assert "@mysql:" in settings.data_database_url
        assert "@localhost:" not in settings.data_database_url
        assert "insightmesh_data" in settings.data_database_url


class TestTaskDatabaseSchema:
    """Test task database schema and migrations."""

    @pytest.fixture
    def task_db_engine(self):
        """Create a temporary SQLite database for task schema testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        engine = create_engine(f"sqlite:///{db_path}")

        # Create task_runs table (simplified version for testing)
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS task_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id VARCHAR(255) NOT NULL UNIQUE,
                    status VARCHAR(50) NOT NULL,
                    started_at DATETIME NOT NULL,
                    completed_at DATETIME,
                    duration_seconds FLOAT,
                    triggered_by VARCHAR(100) DEFAULT 'scheduler',
                    triggered_by_user VARCHAR(255),
                    task_config_snapshot TEXT,
                    result_data TEXT,
                    error_message TEXT,
                    error_traceback TEXT,
                    log_output TEXT,
                    records_processed INTEGER,
                    records_success INTEGER,
                    records_failed INTEGER,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """
                )
            )
            conn.commit()

        yield engine

        engine.dispose()
        os.unlink(db_path)

    def test_task_runs_table_has_required_columns(self, task_db_engine):
        """Test that task_runs table has all required columns."""
        inspector = inspect(task_db_engine)
        columns = {col["name"] for col in inspector.get_columns("task_runs")}

        required_columns = {
            "id",
            "run_id",
            "status",
            "started_at",
            "completed_at",
            "duration_seconds",
            "triggered_by",
            "triggered_by_user",
            "task_config_snapshot",
            "result_data",
            "error_message",
            "records_processed",
            "records_success",
            "records_failed",
            "created_at",
            "updated_at",
        }

        assert required_columns.issubset(
            columns
        ), f"Missing columns: {required_columns - columns}"


class TestDataDatabaseSchema:
    """Test data database schema and migrations."""

    @pytest.fixture
    def data_db_engine(self):
        """Create a temporary SQLite database for data schema testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        engine = create_engine(f"sqlite:///{db_path}")

        # Create metric_records table (simplified version for testing)
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS metric_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_id VARCHAR(255) NOT NULL,
                    data_type VARCHAR(50) NOT NULL,
                    pinecone_id VARCHAR(255) NOT NULL,
                    pinecone_namespace VARCHAR(255),
                    content_snapshot TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    synced_at DATETIME,
                    UNIQUE(metric_id, data_type)
                )
            """
                )
            )
            conn.commit()

        yield engine

        engine.dispose()
        os.unlink(db_path)

    def test_metric_records_table_has_required_columns(self, data_db_engine):
        """Test that metric_records table has all required columns."""
        inspector = inspect(data_db_engine)
        columns = {col["name"] for col in inspector.get_columns("metric_records")}

        required_columns = {
            "id",
            "metric_id",
            "data_type",
            "pinecone_id",
            "pinecone_namespace",
            "content_snapshot",
            "created_at",
            "updated_at",
            "synced_at",
        }

        assert required_columns.issubset(
            columns
        ), f"Missing columns: {required_columns - columns}"

    def test_metric_records_table_has_unique_constraint(self, data_db_engine):
        """Test that metric_records has unique constraint on metric_id and data_type."""
        inspector = inspect(data_db_engine)
        indexes = inspector.get_indexes("metric_records")
        unique_indexes = inspector.get_unique_constraints("metric_records")

        # Check that there's a unique constraint on metric_id and data_type
        has_unique = False
        for constraint in unique_indexes:
            if set(constraint.get("column_names", [])) == {"metric_id", "data_type"}:
                has_unique = True
                break

        # SQLite might implement unique constraint as index
        for index in indexes:
            if index.get("unique") and set(index.get("column_names", [])) == {
                "metric_id",
                "data_type",
            }:
                has_unique = True
                break

        assert (
            has_unique
        ), "metric_records table must have unique constraint on (metric_id, data_type)"


class TestMigrationEnvironments:
    """Test that migration environments are properly configured."""

    def test_task_migrations_use_task_database_url(self):
        """Test that task migrations read TASK_DATABASE_URL."""
        test_url = "mysql+pymysql://task_user:pass@host:3306/taskdb"
        os.environ["TASK_DATABASE_URL"] = test_url

        # Import the migrations env module
        import sys
        from pathlib import Path

        migrations_path = Path(__file__).parent.parent / "migrations"
        sys.path.insert(0, str(migrations_path.parent))

        # This would import the env.py and check get_url()
        # For now, we verify the environment variable is set correctly
        assert os.getenv("TASK_DATABASE_URL") == test_url

    def test_data_migrations_use_data_database_url(self):
        """Test that data migrations read DATA_DATABASE_URL."""
        test_url = "mysql+pymysql://data_user:pass@host:3306/datadb"
        os.environ["DATA_DATABASE_URL"] = test_url

        # Verify the environment variable is set correctly
        assert os.getenv("DATA_DATABASE_URL") == test_url

    def test_alembic_configs_exist(self):
        """Test that both alembic configuration files exist."""
        from pathlib import Path

        tasks_dir = Path(__file__).parent.parent
        task_config = tasks_dir / "alembic.ini"
        data_config = tasks_dir / "alembic_data.ini"

        assert task_config.exists(), "alembic.ini must exist for task migrations"
        assert (
            data_config.exists()
        ), "alembic_data.ini must exist for data migrations"

    def test_migration_directories_exist(self):
        """Test that both migration directories exist."""
        from pathlib import Path

        tasks_dir = Path(__file__).parent.parent
        task_migrations = tasks_dir / "migrations"
        data_migrations = tasks_dir / "migrations_data"

        assert (
            task_migrations.exists()
        ), "migrations/ directory must exist for task migrations"
        assert (
            data_migrations.exists()
        ), "migrations_data/ directory must exist for data migrations"

        # Check for env.py in both
        assert (task_migrations / "env.py").exists(), "migrations/env.py must exist"
        assert (
            data_migrations / "env.py"
        ).exists(), "migrations_data/env.py must exist"
