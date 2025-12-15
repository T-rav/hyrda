"""Unit tests for ExternalTaskLoader (external task/job loading system).

All tests are pure unit tests using mocking and temporary directories.
No integration with real external tasks or databases.
"""

import os
from unittest.mock import patch

import pytest

from services.external_task_loader import (
    ExternalTaskLoader,
    get_external_loader,
    reload_external_task,
)


@pytest.fixture
def temp_tasks_dir(tmp_path):
    """Create temporary tasks directory for testing."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    return tasks_dir


@pytest.fixture
def simple_job_code():
    """Simple job code for testing."""
    return '''
from jobs.base_job import BaseJob

class TestJob(BaseJob):
    """Test job."""
    JOB_NAME = "Test Job"
    JOB_DESCRIPTION = "Test job description"

    def __init__(self, settings, **kwargs):
        super().__init__(settings)

    def get_job_id(self) -> str:
        return "test_job"

    async def execute(self) -> dict:
        return {
            "records_processed": 10,
            "records_success": 10,
            "records_failed": 0
        }

# Alias for dynamic loading
Job = TestJob
'''


class TestExternalTaskLoaderInitialization:
    """Test ExternalTaskLoader initialization."""

    def test_initialization_with_path(self):
        """Test initialization with explicit path."""
        loader = ExternalTaskLoader("/custom/path")
        assert loader.external_path == "/custom/path"

    def test_initialization_from_env(self):
        """Test initialization from environment variable."""
        with patch.dict(os.environ, {"EXTERNAL_TASKS_PATH": "/env/path"}):
            loader = ExternalTaskLoader()
            assert loader.external_path == "/env/path"

    def test_initialization_no_path(self):
        """Test initialization without path."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("EXTERNAL_TASKS_PATH", None)
            loader = ExternalTaskLoader()
            assert loader.external_path is None


class TestTaskDiscovery:
    """Test task discovery functionality."""

    def test_discover_tasks_no_path(self):
        """Test discovery with no external path configured - should still load system tasks."""
        loader = ExternalTaskLoader(external_tasks_path=None)
        tasks = loader.discover_tasks()
        # Should load system tasks (slack_user_import, gdrive_ingest)
        assert len(tasks) == 2
        assert "slack_user_import" in tasks
        assert "gdrive_ingest" in tasks

    def test_discover_tasks_missing_directory(self):
        """Test discovery when external directory doesn't exist - should still load system tasks."""
        loader = ExternalTaskLoader("/nonexistent/path")
        tasks = loader.discover_tasks()
        # Should load system tasks even if external path doesn't exist
        assert len(tasks) == 2
        assert "slack_user_import" in tasks
        assert "gdrive_ingest" in tasks

    def test_discover_single_task(self, temp_tasks_dir, simple_job_code):
        """Test discovering a single valid task."""
        # Create task directory and file
        task_dir = temp_tasks_dir / "test_task"
        task_dir.mkdir()
        job_file = task_dir / "job.py"
        job_file.write_text(simple_job_code)

        loader = ExternalTaskLoader(str(temp_tasks_dir))
        tasks = loader.discover_tasks()

        assert "test_task" in tasks
        assert tasks["test_task"].__name__ == "TestJob"

    def test_discover_multiple_tasks(self, temp_tasks_dir, simple_job_code):
        """Test discovering multiple tasks."""
        # Create two tasks
        for task_name in ["task1", "task2"]:
            task_dir = temp_tasks_dir / task_name
            task_dir.mkdir()
            job_file = task_dir / "job.py"
            job_file.write_text(simple_job_code)

        loader = ExternalTaskLoader(str(temp_tasks_dir))
        tasks = loader.discover_tasks()

        # Should have 4 tasks: 2 system + 2 external
        assert len(tasks) == 4
        assert "slack_user_import" in tasks  # system
        assert "gdrive_ingest" in tasks  # system
        assert "task1" in tasks  # external
        assert "task2" in tasks  # external

    def test_skip_directory_without_job_py(self, temp_tasks_dir):
        """Test skipping directories without job.py."""
        # Create directory without job.py
        invalid_dir = temp_tasks_dir / "invalid_task"
        invalid_dir.mkdir()
        (invalid_dir / "other.py").write_text("# Not job.py")

        loader = ExternalTaskLoader(str(temp_tasks_dir))
        tasks = loader.discover_tasks()

        assert "invalid_task" not in tasks

    def test_skip_underscore_directories(self, temp_tasks_dir, simple_job_code):
        """Test skipping directories starting with underscore."""
        # Create _private directory
        private_dir = temp_tasks_dir / "_private"
        private_dir.mkdir()
        (private_dir / "job.py").write_text(simple_job_code)

        loader = ExternalTaskLoader(str(temp_tasks_dir))
        tasks = loader.discover_tasks()

        assert "_private" not in tasks

    def test_handle_invalid_job_code(self, temp_tasks_dir):
        """Test handling of invalid Python code in job.py."""
        task_dir = temp_tasks_dir / "broken_task"
        task_dir.mkdir()
        job_file = task_dir / "job.py"
        job_file.write_text("this is not valid python {{{")

        loader = ExternalTaskLoader(str(temp_tasks_dir))
        tasks = loader.discover_tasks()

        # Should skip broken task and continue
        assert "broken_task" not in tasks

    def test_handle_missing_job_class(self, temp_tasks_dir):
        """Test handling of job.py without Job class."""
        task_dir = temp_tasks_dir / "no_class_task"
        task_dir.mkdir()
        job_file = task_dir / "job.py"
        job_file.write_text("# Valid Python but no Job class\nclass Other: pass")

        loader = ExternalTaskLoader(str(temp_tasks_dir))
        tasks = loader.discover_tasks()

        # Should try to find class ending with "Job"
        assert "no_class_task" not in tasks

    def test_fallback_to_class_ending_with_job(self, temp_tasks_dir):
        """Test fallback to class ending with 'Job' if 'Job' not found."""
        task_dir = temp_tasks_dir / "fallback_task"
        task_dir.mkdir()
        job_file = task_dir / "job.py"
        job_code = '''
from jobs.base_job import BaseJob

class MyCustomJob(BaseJob):
    """Custom job without Job alias."""
    JOB_NAME = "Custom"

    def __init__(self, settings, **kwargs):
        super().__init__(settings)

    def get_job_id(self) -> str:
        return "custom"

    async def execute(self) -> dict:
        return {"records_processed": 1, "records_success": 1, "records_failed": 0}
'''
        job_file.write_text(job_code)

        loader = ExternalTaskLoader(str(temp_tasks_dir))
        tasks = loader.discover_tasks()

        assert "fallback_task" in tasks
        assert tasks["fallback_task"].__name__ == "MyCustomJob"


class TestTaskLoading:
    """Test task loading and module management."""

    def test_load_task_with_relative_imports(self, temp_tasks_dir):
        """Test loading task with relative imports."""
        task_dir = temp_tasks_dir / "complex_task"
        task_dir.mkdir()

        # Create helper module
        (task_dir / "helper.py").write_text("def helper(): return 'helped'")

        # Create job that imports helper
        job_code = """
from helper import helper
from jobs.base_job import BaseJob

class ComplexJob(BaseJob):
    JOB_NAME = "Complex"

    def __init__(self, settings, **kwargs):
        super().__init__(settings)
        self.name = helper()

    def get_job_id(self) -> str:
        return "complex"

    async def execute(self) -> dict:
        return {"records_processed": 1, "records_success": 1, "records_failed": 0}

Job = ComplexJob
"""
        (task_dir / "job.py").write_text(job_code)

        loader = ExternalTaskLoader(str(temp_tasks_dir))
        tasks = loader.discover_tasks()

        assert "complex_task" in tasks

    def test_get_task_class(self, temp_tasks_dir, simple_job_code):
        """Test getting task class by name."""
        task_dir = temp_tasks_dir / "test_task"
        task_dir.mkdir()
        (task_dir / "job.py").write_text(simple_job_code)

        loader = ExternalTaskLoader(str(temp_tasks_dir))
        loader.discover_tasks()

        task_class = loader.get_task_class("test_task")
        assert task_class is not None
        assert task_class.__name__ == "TestJob"

    def test_get_nonexistent_task_class(self, temp_tasks_dir):
        """Test getting non-existent task class."""
        loader = ExternalTaskLoader(str(temp_tasks_dir))
        loader.discover_tasks()

        task_class = loader.get_task_class("nonexistent")
        assert task_class is None

    def test_list_external_tasks(self, temp_tasks_dir, simple_job_code):
        """Test listing all loaded task names."""
        # Create two tasks
        for task_name in ["task1", "task2"]:
            task_dir = temp_tasks_dir / task_name
            task_dir.mkdir()
            (task_dir / "job.py").write_text(simple_job_code)

        loader = ExternalTaskLoader(str(temp_tasks_dir))
        loader.discover_tasks()

        task_names = loader.list_external_tasks()
        # Should include both system and external tasks
        assert sorted(task_names) == ["gdrive_ingest", "slack_user_import", "task1", "task2"]


class TestTaskReload:
    """Test task hot-reload functionality."""

    def test_reload_task_success(self, temp_tasks_dir, simple_job_code):
        """Test successfully reloading a task."""
        task_dir = temp_tasks_dir / "test_task"
        task_dir.mkdir()
        job_file = task_dir / "job.py"
        job_file.write_text(simple_job_code)

        loader = ExternalTaskLoader(str(temp_tasks_dir))
        loader.discover_tasks()

        # Modify job code
        modified_code = simple_job_code.replace('"Test Job"', '"Modified Job"')
        job_file.write_text(modified_code)

        # Reload
        reloaded_class = loader.reload_task("test_task")
        assert reloaded_class is not None

    def test_reload_nonexistent_task(self, temp_tasks_dir):
        """Test reloading non-existent task."""
        loader = ExternalTaskLoader(str(temp_tasks_dir))
        loader.discover_tasks()

        result = loader.reload_task("nonexistent")
        assert result is None

    def test_reload_without_path(self):
        """Test reload fails gracefully without external path."""
        loader = ExternalTaskLoader(external_tasks_path=None)
        result = loader.reload_task("any_task")
        assert result is None

    def test_reload_removes_from_cache(self, temp_tasks_dir, simple_job_code):
        """Test that reload removes task from cache."""
        task_dir = temp_tasks_dir / "test_task"
        task_dir.mkdir()
        (task_dir / "job.py").write_text(simple_job_code)

        loader = ExternalTaskLoader(str(temp_tasks_dir))
        loader.discover_tasks()

        # Verify in cache
        assert "test_task" in loader._loaded_tasks

        # Reload
        loader.reload_task("test_task")

        # Should still be in cache after reload
        assert "test_task" in loader._loaded_tasks


class TestGlobalLoader:
    """Test global loader singleton."""

    def test_get_external_loader_singleton(self):
        """Test that get_external_loader returns same instance."""
        # Reset global
        import services.external_task_loader as loader_module

        loader_module._external_loader = None

        loader1 = get_external_loader()
        loader2 = get_external_loader()

        assert loader1 is loader2

    def test_reload_external_task_function(self, temp_tasks_dir, simple_job_code):
        """Test global reload_external_task function."""
        # Create task
        task_dir = temp_tasks_dir / "test_task"
        task_dir.mkdir()
        (task_dir / "job.py").write_text(simple_job_code)

        # Reset global and set path
        import services.external_task_loader as loader_module

        loader_module._external_loader = ExternalTaskLoader(str(temp_tasks_dir))
        get_external_loader().discover_tasks()

        # Reload via function
        result = reload_external_task("test_task")
        assert result is True

    def test_reload_external_task_failure(self):
        """Test global reload function with non-existent task."""
        import services.external_task_loader as loader_module

        loader_module._external_loader = ExternalTaskLoader()

        result = reload_external_task("nonexistent")
        assert result is False


class TestSystemTaskProtection:
    """Test system task override protection."""

    def test_external_cannot_override_system(self, temp_tasks_dir, simple_job_code):
        """Test that external tasks cannot override system tasks."""
        # Create mock system tasks directory
        system_dir = temp_tasks_dir / "system"
        system_dir.mkdir()

        # Create system task
        system_task_dir = system_dir / "slack_user_import"
        system_task_dir.mkdir()
        (system_task_dir / "job.py").write_text(
            simple_job_code.replace("TestJob", "SystemJob")
        )

        # Create external tasks directory
        external_dir = temp_tasks_dir / "external"
        external_dir.mkdir()

        # Create external task with SAME name (conflict)
        external_task_dir = external_dir / "slack_user_import"
        external_task_dir.mkdir()
        (external_task_dir / "job.py").write_text(
            simple_job_code.replace("TestJob", "ExternalJob")
        )

        # Initialize loader with both paths
        loader = ExternalTaskLoader(str(external_dir))
        loader.system_path = system_dir  # Override system path for testing

        # Discover tasks
        tasks = loader.discover_tasks()

        # Verify system task loaded, external task rejected
        assert "slack_user_import" in tasks
        assert tasks["slack_user_import"].__name__ == "SystemJob"  # System wins!
        # External task should be rejected (not loaded)

    def test_external_loads_when_no_conflict(self, temp_tasks_dir, simple_job_code):
        """Test that external tasks load normally when no conflict."""
        # Create mock system tasks directory
        system_dir = temp_tasks_dir / "system"
        system_dir.mkdir()

        # Create system task
        system_task_dir = system_dir / "slack_user_import"
        system_task_dir.mkdir()
        (system_task_dir / "job.py").write_text(
            simple_job_code.replace("TestJob", "SystemJob")
        )

        # Create external tasks directory
        external_dir = temp_tasks_dir / "external"
        external_dir.mkdir()

        # Create external task with DIFFERENT name (no conflict)
        external_task_dir = external_dir / "metric_sync"
        external_task_dir.mkdir()
        (external_task_dir / "job.py").write_text(
            simple_job_code.replace("TestJob", "ExternalJob")
        )

        # Initialize loader
        loader = ExternalTaskLoader(str(external_dir))
        loader.system_path = system_dir  # Override system path for testing

        # Discover tasks
        tasks = loader.discover_tasks()

        # Verify both loaded
        assert "slack_user_import" in tasks
        assert "metric_sync" in tasks
        assert tasks["slack_user_import"].__name__ == "SystemJob"
        assert tasks["metric_sync"].__name__ == "ExternalJob"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_job_file(self, temp_tasks_dir):
        """Test handling of empty job.py file."""
        task_dir = temp_tasks_dir / "empty_task"
        task_dir.mkdir()
        (task_dir / "job.py").write_text("")

        loader = ExternalTaskLoader(str(temp_tasks_dir))
        tasks = loader.discover_tasks()

        assert "empty_task" not in tasks

    def test_task_with_syntax_errors(self, temp_tasks_dir):
        """Test handling of task with syntax errors."""
        task_dir = temp_tasks_dir / "syntax_error_task"
        task_dir.mkdir()
        (task_dir / "job.py").write_text(
            "class Job:\n    def __init__(self"
        )  # Missing closing

        loader = ExternalTaskLoader(str(temp_tasks_dir))
        tasks = loader.discover_tasks()

        assert "syntax_error_task" not in tasks

    def test_task_with_import_errors(self, temp_tasks_dir):
        """Test handling of task with import errors."""
        task_dir = temp_tasks_dir / "import_error_task"
        task_dir.mkdir()
        job_code = """
import nonexistent_module

class Job:
    pass
"""
        (task_dir / "job.py").write_text(job_code)

        loader = ExternalTaskLoader(str(temp_tasks_dir))
        tasks = loader.discover_tasks()

        # Should fail to load
        assert "import_error_task" not in tasks

    def test_discover_tasks_caches_results(self, temp_tasks_dir, simple_job_code):
        """Test that multiple discoveries don't reload tasks unnecessarily."""
        task_dir = temp_tasks_dir / "test_task"
        task_dir.mkdir()
        (task_dir / "job.py").write_text(simple_job_code)

        loader = ExternalTaskLoader(str(temp_tasks_dir))

        # First discovery
        tasks1 = loader.discover_tasks()

        # Second discovery - should return same classes
        tasks2 = loader.discover_tasks()

        assert tasks1["test_task"] is tasks2["test_task"]
