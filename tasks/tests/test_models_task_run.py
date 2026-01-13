"""Tests for TaskRun model (models/task_run.py)."""

from datetime import UTC, datetime, timedelta

from models.task_run import TaskRun


class TestTaskRunProperties:
    """Test TaskRun property methods."""

    def test_is_running_when_status_running(self):
        """Test is_running returns True when status is 'running'."""
        task_run = TaskRun(
            run_id="test-run-1", status="running", started_at=datetime.now(UTC)
        )
        assert task_run.is_running is True

    def test_is_running_when_status_success(self):
        """Test is_running returns False when status is 'success'."""
        task_run = TaskRun(
            run_id="test-run-2", status="success", started_at=datetime.now(UTC)
        )
        assert task_run.is_running is False

    def test_is_running_when_status_failed(self):
        """Test is_running returns False when status is 'failed'."""
        task_run = TaskRun(
            run_id="test-run-3", status="failed", started_at=datetime.now(UTC)
        )
        assert task_run.is_running is False

    def test_is_running_when_status_cancelled(self):
        """Test is_running returns False when status is 'cancelled'."""
        task_run = TaskRun(
            run_id="test-run-4", status="cancelled", started_at=datetime.now(UTC)
        )
        assert task_run.is_running is False

    def test_is_completed_when_status_success(self):
        """Test is_completed returns True when status is 'success'."""
        task_run = TaskRun(
            run_id="test-run-5", status="success", started_at=datetime.now(UTC)
        )
        assert task_run.is_completed is True

    def test_is_completed_when_status_failed(self):
        """Test is_completed returns True when status is 'failed'."""
        task_run = TaskRun(
            run_id="test-run-6", status="failed", started_at=datetime.now(UTC)
        )
        assert task_run.is_completed is True

    def test_is_completed_when_status_cancelled(self):
        """Test is_completed returns True when status is 'cancelled'."""
        task_run = TaskRun(
            run_id="test-run-7", status="cancelled", started_at=datetime.now(UTC)
        )
        assert task_run.is_completed is True

    def test_is_completed_when_status_running(self):
        """Test is_completed returns False when status is 'running'."""
        task_run = TaskRun(
            run_id="test-run-8", status="running", started_at=datetime.now(UTC)
        )
        assert task_run.is_completed is False


class TestCalculateDuration:
    """Test calculate_duration method."""

    def test_calculate_duration_both_times_aware(self):
        """Test duration calculation with timezone-aware datetimes."""
        start = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        end = datetime(2024, 1, 1, 10, 5, 30, tzinfo=UTC)

        task_run = TaskRun(
            run_id="test-run-9",
            status="success",
            started_at=start,
            completed_at=end,
        )

        task_run.calculate_duration()

        # 5 minutes 30 seconds = 330 seconds
        assert task_run.duration_seconds == 330.0

    def test_calculate_duration_both_times_naive(self):
        """Test duration calculation with timezone-naive datetimes."""
        start = datetime(2024, 1, 1, 10, 0, 0)
        end = datetime(2024, 1, 1, 11, 30, 0)

        task_run = TaskRun(
            run_id="test-run-10",
            status="success",
            started_at=start,
            completed_at=end,
        )

        task_run.calculate_duration()

        # 1 hour 30 minutes = 5400 seconds
        assert task_run.duration_seconds == 5400.0

    def test_calculate_duration_start_aware_end_naive(self):
        """Test duration with start aware and end naive (assumes UTC)."""
        start = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        end = datetime(2024, 1, 1, 10, 15, 0)  # Naive

        task_run = TaskRun(
            run_id="test-run-11",
            status="success",
            started_at=start,
            completed_at=end,
        )

        task_run.calculate_duration()

        # 15 minutes = 900 seconds
        assert task_run.duration_seconds == 900.0

    def test_calculate_duration_start_naive_end_aware(self):
        """Test duration with start naive and end aware (assumes UTC)."""
        start = datetime(2024, 1, 1, 10, 0, 0)  # Naive
        end = datetime(2024, 1, 1, 10, 20, 0, tzinfo=UTC)

        task_run = TaskRun(
            run_id="test-run-12",
            status="success",
            started_at=start,
            completed_at=end,
        )

        task_run.calculate_duration()

        # 20 minutes = 1200 seconds
        assert task_run.duration_seconds == 1200.0

    def test_calculate_duration_zero_seconds(self):
        """Test duration calculation when times are identical."""
        time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)

        task_run = TaskRun(
            run_id="test-run-13",
            status="success",
            started_at=time,
            completed_at=time,
        )

        task_run.calculate_duration()

        assert task_run.duration_seconds == 0.0

    def test_calculate_duration_with_microseconds(self):
        """Test duration calculation preserves microsecond precision."""
        start = datetime(2024, 1, 1, 10, 0, 0, 123456, tzinfo=UTC)
        end = datetime(2024, 1, 1, 10, 0, 1, 654321, tzinfo=UTC)

        task_run = TaskRun(
            run_id="test-run-14",
            status="success",
            started_at=start,
            completed_at=end,
        )

        task_run.calculate_duration()

        # Should be approximately 1.530865 seconds
        assert 1.53 < task_run.duration_seconds < 1.54

    def test_calculate_duration_missing_start_time(self):
        """Test calculate_duration with missing start time."""
        task_run = TaskRun(
            run_id="test-run-15",
            status="running",
            started_at=None,
            completed_at=datetime.now(UTC),
        )

        task_run.calculate_duration()

        # Should not set duration
        assert task_run.duration_seconds is None

    def test_calculate_duration_missing_end_time(self):
        """Test calculate_duration with missing end time."""
        task_run = TaskRun(
            run_id="test-run-16",
            status="running",
            started_at=datetime.now(UTC),
            completed_at=None,
        )

        task_run.calculate_duration()

        # Should not set duration
        assert task_run.duration_seconds is None

    def test_calculate_duration_both_times_missing(self):
        """Test calculate_duration with both times missing."""
        task_run = TaskRun(
            run_id="test-run-17",
            status="running",
            started_at=None,
            completed_at=None,
        )

        task_run.calculate_duration()

        # Should not set duration
        assert task_run.duration_seconds is None


class TestTaskRunRepr:
    """Test __repr__ method."""

    def test_repr_format(self):
        """Test __repr__ returns correct format."""
        task_run = TaskRun(
            id=123,
            run_id="test-run-18",
            status="success",
            started_at=datetime.now(UTC),
        )

        repr_str = repr(task_run)

        assert "<TaskRun(" in repr_str
        assert "id=123" in repr_str
        assert "run_id=test-run-18" in repr_str
        assert "status=success" in repr_str

    def test_repr_with_none_id(self):
        """Test __repr__ when id is None (not yet persisted)."""
        task_run = TaskRun(
            run_id="test-run-19",
            status="running",
            started_at=datetime.now(UTC),
        )

        repr_str = repr(task_run)

        assert "<TaskRun(" in repr_str
        assert "id=None" in repr_str


class TestTaskRunCreation:
    """Test TaskRun creation and initialization."""

    def test_create_minimal_task_run(self):
        """Test creating task run with minimal required fields."""
        task_run = TaskRun(
            run_id="test-run-20",
            status="running",
            started_at=datetime.now(UTC),
        )

        assert task_run.run_id == "test-run-20"
        assert task_run.status == "running"
        assert task_run.started_at is not None

    def test_create_complete_task_run(self):
        """Test creating task run with all fields."""
        start = datetime.now(UTC)
        end = start + timedelta(minutes=5)

        task_run = TaskRun(
            run_id="test-run-21",
            status="success",
            started_at=start,
            completed_at=end,
            duration_seconds=300.0,
            triggered_by="scheduler",
            triggered_by_user="U123456",
            result_data={"records": 100},
            log_output="Task completed successfully",
            error_message=None,
            error_traceback=None,
            records_processed=100,
            records_success=98,
            records_failed=2,
            task_config_snapshot={"job_id": "test-job"},
            environment_info={"python": "3.11"},
        )

        assert task_run.run_id == "test-run-21"
        assert task_run.status == "success"
        assert task_run.duration_seconds == 300.0
        assert task_run.triggered_by == "scheduler"
        assert task_run.records_processed == 100
        assert task_run.records_success == 98
        assert task_run.records_failed == 2


class TestTaskRunStatuses:
    """Test different task run statuses."""

    def test_status_variants(self):
        """Test that different status values are handled correctly."""
        statuses = ["running", "success", "failed", "cancelled"]

        for status in statuses:
            task_run = TaskRun(
                run_id=f"test-run-{status}",
                status=status,
                started_at=datetime.now(UTC),
            )

            assert task_run.status == status

            # Check property behaviors
            if status == "running":
                assert task_run.is_running is True
                assert task_run.is_completed is False
            else:
                assert task_run.is_running is False
                assert task_run.is_completed is True
