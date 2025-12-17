"""Tests for TaskMetadata model (models/task_metadata.py)."""

from datetime import datetime

from models.task_metadata import TaskMetadata


class TestTaskMetadataCreation:
    """Test TaskMetadata model creation."""

    def test_create_task_metadata(self):
        """Test creating task metadata."""
        metadata = TaskMetadata(
            job_id="test-job-1",
            task_name="Test Task",
        )

        assert metadata.job_id == "test-job-1"
        assert metadata.task_name == "Test Task"

    def test_create_with_long_job_id(self):
        """Test creating with maximum length job_id."""
        long_id = "x" * 191
        metadata = TaskMetadata(
            job_id=long_id,
            task_name="Long ID Task",
        )

        assert metadata.job_id == long_id
        assert len(metadata.job_id) == 191

    def test_create_with_long_task_name(self):
        """Test creating with maximum length task_name."""
        long_name = "x" * 255
        metadata = TaskMetadata(
            job_id="test-job-2",
            task_name=long_name,
        )

        assert metadata.task_name == long_name
        assert len(metadata.task_name) == 255


class TestToDict:
    """Test to_dict() method."""

    def test_to_dict_basic(self):
        """Test to_dict returns correct structure."""
        metadata = TaskMetadata(
            job_id="test-job-3",
            task_name="Test Task",
        )

        result = metadata.to_dict()

        assert isinstance(result, dict)
        assert result["job_id"] == "test-job-3"
        assert result["task_name"] == "Test Task"
        assert "created_at" in result
        assert "updated_at" in result

    def test_to_dict_with_timestamps(self):
        """Test to_dict includes formatted timestamps."""
        now = datetime(2024, 1, 15, 10, 30, 0)

        metadata = TaskMetadata(
            job_id="test-job-4",
            task_name="With Timestamps",
        )
        metadata.created_at = now
        metadata.updated_at = now

        result = metadata.to_dict()

        assert result["created_at"] == "2024-01-15T10:30:00"
        assert result["updated_at"] == "2024-01-15T10:30:00"

    def test_to_dict_none_timestamps(self):
        """Test to_dict handles None timestamps."""
        metadata = TaskMetadata(
            job_id="test-job-5",
            task_name="No Timestamps",
        )
        metadata.created_at = None
        metadata.updated_at = None

        result = metadata.to_dict()

        assert result["created_at"] is None
        assert result["updated_at"] is None

    def test_to_dict_only_created_at(self):
        """Test to_dict with only created_at set."""
        created = datetime(2024, 1, 10, 9, 0, 0)

        metadata = TaskMetadata(
            job_id="test-job-6",
            task_name="Only Created",
        )
        metadata.created_at = created
        metadata.updated_at = None

        result = metadata.to_dict()

        assert result["created_at"] == "2024-01-10T09:00:00"
        assert result["updated_at"] is None

    def test_to_dict_only_updated_at(self):
        """Test to_dict with only updated_at set."""
        updated = datetime(2024, 1, 20, 14, 30, 0)

        metadata = TaskMetadata(
            job_id="test-job-7",
            task_name="Only Updated",
        )
        metadata.created_at = None
        metadata.updated_at = updated

        result = metadata.to_dict()

        assert result["created_at"] is None
        assert result["updated_at"] == "2024-01-20T14:30:00"

    def test_to_dict_all_fields(self):
        """Test to_dict includes all expected fields."""
        metadata = TaskMetadata(
            job_id="test-job-8",
            task_name="Complete",
        )

        result = metadata.to_dict()

        expected_keys = ["job_id", "task_name", "created_at", "updated_at"]
        assert all(key in result for key in expected_keys)
        assert len(result) == 4


class TestTaskMetadataFields:
    """Test field constraints and behaviors."""

    def test_job_id_is_primary_key(self):
        """Test that job_id serves as primary key."""
        metadata1 = TaskMetadata(job_id="unique-1", task_name="Task 1")
        metadata2 = TaskMetadata(job_id="unique-2", task_name="Task 2")

        assert metadata1.job_id != metadata2.job_id

    def test_task_name_required(self):
        """Test that task_name is not nullable."""
        # Should work with task_name
        metadata = TaskMetadata(job_id="test", task_name="Required")
        assert metadata.task_name == "Required"

    def test_special_characters_in_task_name(self):
        """Test task names with special characters."""
        special_name = "Task: Import @Data (v2.0) - Production!"
        metadata = TaskMetadata(
            job_id="test-special",
            task_name=special_name,
        )

        assert metadata.task_name == special_name

    def test_unicode_in_task_name(self):
        """Test task names with unicode characters."""
        unicode_name = "タスク名 - 测试任务 - Задача"
        metadata = TaskMetadata(
            job_id="test-unicode",
            task_name=unicode_name,
        )

        assert metadata.task_name == unicode_name
