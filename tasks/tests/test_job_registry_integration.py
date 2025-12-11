"""Integration tests for JobRegistry with external task loading.

Tests the full integration between JobRegistry and ExternalTaskLoader.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from config.settings import TasksSettings
from jobs.job_registry import JobRegistry, execute_job_by_type
from services.external_task_loader import ExternalTaskLoader
from services.scheduler_service import SchedulerService


@pytest.fixture
def temp_tasks_dir(tmp_path):
    """Create temporary tasks directory for testing."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    return tasks_dir


@pytest.fixture
def mock_settings():
    """Mock TasksSettings."""
    settings = MagicMock(spec=TasksSettings)
    settings.task_database_url = "sqlite:///:memory:"
    return settings


@pytest.fixture
def mock_scheduler():
    """Mock SchedulerService."""
    scheduler = MagicMock(spec=SchedulerService)
    scheduler.add_job = MagicMock(return_value=MagicMock(id="test_job_id"))
    return scheduler


@pytest.fixture
def simple_job_code():
    """Simple job code for testing."""
    return '''
class TestJob:
    """Test job."""
    JOB_NAME = "Test Job"
    JOB_DESCRIPTION = "Test job description"
    REQUIRED_PARAMS = []
    OPTIONAL_PARAMS = []
    PARAM_GROUPS = []

    def __init__(self, settings, **kwargs):
        self.settings = settings

    def get_job_id(self) -> str:
        return "test_job"

    async def execute(self) -> dict:
        return {
            "records_processed": 10,
            "records_success": 10,
            "records_failed": 0
        }

Job = TestJob
'''


class TestJobRegistryWithExternalLoader:
    """Test JobRegistry integration with ExternalTaskLoader."""

    def test_job_registry_loads_external_tasks(
        self, temp_tasks_dir, simple_job_code, mock_settings, mock_scheduler
    ):
        """Test that JobRegistry loads tasks from external directory."""
        # Create a test task
        task_dir = temp_tasks_dir / "test_task"
        task_dir.mkdir()
        (task_dir / "job.py").write_text(simple_job_code)

        # Mock the external loader to use our temp directory
        with patch("services.external_task_loader.get_external_loader") as mock_get_loader:
            loader = ExternalTaskLoader(str(temp_tasks_dir))
            loader.discover_tasks()
            mock_get_loader.return_value = loader

            # Create registry
            registry = JobRegistry(mock_settings, mock_scheduler)

            # Verify task was loaded
            assert "test_task" in registry.job_types
            assert registry.job_types["test_task"].__name__ == "TestJob"

    def test_job_registry_with_no_external_tasks(self, mock_settings, mock_scheduler):
        """Test JobRegistry with no external tasks configured."""
        with patch("services.external_task_loader.get_external_loader") as mock_get_loader:
            loader = ExternalTaskLoader(external_tasks_path=None)
            loader.discover_tasks()
            mock_get_loader.return_value = loader

            registry = JobRegistry(mock_settings, mock_scheduler)

            # Should have no job types
            assert len(registry.job_types) == 0

    def test_job_registry_get_available_job_types(
        self, temp_tasks_dir, simple_job_code, mock_settings, mock_scheduler
    ):
        """Test getting available job types with metadata."""
        # Create a test task
        task_dir = temp_tasks_dir / "test_task"
        task_dir.mkdir()
        (task_dir / "job.py").write_text(simple_job_code)

        with patch("services.external_task_loader.get_external_loader") as mock_get_loader:
            loader = ExternalTaskLoader(str(temp_tasks_dir))
            loader.discover_tasks()
            mock_get_loader.return_value = loader

            registry = JobRegistry(mock_settings, mock_scheduler)
            job_types = registry.get_available_job_types()

            assert len(job_types) == 1
            assert job_types[0]["type"] == "test_task"
            assert job_types[0]["name"] == "Test Job"
            assert job_types[0]["description"] == "Test job description"

    def test_job_registry_register_additional_job(
        self, temp_tasks_dir, simple_job_code, mock_settings, mock_scheduler
    ):
        """Test registering additional job type manually."""
        # Create initial task
        task_dir = temp_tasks_dir / "test_task"
        task_dir.mkdir()
        (task_dir / "job.py").write_text(simple_job_code)

        with patch("services.external_task_loader.get_external_loader") as mock_get_loader:
            loader = ExternalTaskLoader(str(temp_tasks_dir))
            loader.discover_tasks()
            mock_get_loader.return_value = loader

            registry = JobRegistry(mock_settings, mock_scheduler)

            # Register additional job manually
            from jobs.base_job import BaseJob

            class ManualJob(BaseJob):
                JOB_NAME = "Manual Job"

                def get_job_id(self) -> str:
                    return "manual"

                async def execute(self) -> dict:
                    return {"records_processed": 1, "records_success": 1, "records_failed": 0}

            registry.register_job_type("manual_job", ManualJob)

            assert "manual_job" in registry.job_types
            assert len(registry.job_types) == 2


class TestExecuteJobByType:
    """Test execute_job_by_type with external loader."""

    def test_execute_job_by_type_loads_from_external(
        self, temp_tasks_dir, simple_job_code
    ):
        """Test that execute_job_by_type loads job from external directory."""
        # Create a test task
        task_dir = temp_tasks_dir / "test_task"
        task_dir.mkdir()
        (task_dir / "job.py").write_text(simple_job_code)

        # Mock the external loader
        with patch("services.external_task_loader.get_external_loader") as mock_get_loader:
            loader = ExternalTaskLoader(str(temp_tasks_dir))
            loader.discover_tasks()
            mock_get_loader.return_value = loader

            # Mock TaskRun database operations
            with patch("models.base.get_db_session") as mock_db:
                mock_session = MagicMock()
                mock_db.return_value.__enter__.return_value = mock_session

                # Execute job
                result = execute_job_by_type(
                    job_type="test_task",
                    job_params={},
                    triggered_by="test",
                )

                # Verify result
                assert result["records_processed"] == 10
                assert result["records_success"] == 10
                assert result["records_failed"] == 0

    def test_execute_job_by_type_unknown_job_error(self):
        """Test execute_job_by_type with unknown job type."""
        with patch("services.external_task_loader.get_external_loader") as mock_get_loader:
            loader = ExternalTaskLoader(external_tasks_path=None)
            loader.discover_tasks()
            mock_get_loader.return_value = loader

            with pytest.raises(ValueError, match="Unknown job type: nonexistent"):
                execute_job_by_type(
                    job_type="nonexistent",
                    job_params={},
                    triggered_by="test",
                )

    def test_execute_job_by_type_with_params(self, temp_tasks_dir):
        """Test execute_job_by_type passes parameters correctly."""
        # Create a test task that accepts parameters
        job_code = '''
class ParamJob:
    JOB_NAME = "Param Job"

    def __init__(self, settings, count: int = 5, **kwargs):
        self.settings = settings
        self.count = count

    def get_job_id(self) -> str:
        return "param_job"

    async def execute(self) -> dict:
        return {
            "records_processed": self.count,
            "records_success": self.count,
            "records_failed": 0
        }

Job = ParamJob
'''
        task_dir = temp_tasks_dir / "param_task"
        task_dir.mkdir()
        (task_dir / "job.py").write_text(job_code)

        with patch("services.external_task_loader.get_external_loader") as mock_get_loader:
            loader = ExternalTaskLoader(str(temp_tasks_dir))
            loader.discover_tasks()
            mock_get_loader.return_value = loader

            with patch("models.base.get_db_session") as mock_db:
                mock_session = MagicMock()
                mock_db.return_value.__enter__.return_value = mock_session

                # Execute with custom parameter
                result = execute_job_by_type(
                    job_type="param_task",
                    job_params={"count": 42},
                    triggered_by="test",
                )

                assert result["records_processed"] == 42


class TestJobRegistryCreateJob:
    """Test JobRegistry.create_job with external tasks."""

    def test_create_job_schedules_external_task(
        self, temp_tasks_dir, simple_job_code, mock_settings, mock_scheduler
    ):
        """Test that create_job works with externally loaded tasks."""
        # Create a test task
        task_dir = temp_tasks_dir / "test_task"
        task_dir.mkdir()
        (task_dir / "job.py").write_text(simple_job_code)

        with patch("services.external_task_loader.get_external_loader") as mock_get_loader:
            loader = ExternalTaskLoader(str(temp_tasks_dir))
            loader.discover_tasks()
            mock_get_loader.return_value = loader

            registry = JobRegistry(mock_settings, mock_scheduler)

            # Create job with schedule
            job = registry.create_job(
                job_type="test_task",
                schedule={"trigger": "interval", "hours": 1},
            )

            # Verify scheduler was called
            mock_scheduler.add_job.assert_called_once()
            assert job.id == "test_job_id"

    def test_create_job_unknown_type_error(self, mock_settings, mock_scheduler):
        """Test create_job with unknown job type."""
        with patch("services.external_task_loader.get_external_loader") as mock_get_loader:
            loader = ExternalTaskLoader(external_tasks_path=None)
            loader.discover_tasks()
            mock_get_loader.return_value = loader

            registry = JobRegistry(mock_settings, mock_scheduler)

            with pytest.raises(ValueError, match="Unknown job type: nonexistent"):
                registry.create_job(job_type="nonexistent")
