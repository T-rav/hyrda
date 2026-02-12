"""Comprehensive tests for Task Runs API (api/task_runs.py).

Phase 2 refactoring: Replaced create_mock_task_run helper with TaskRunBuilder
and database mocks with DatabaseMockFactory.
"""

from unittest.mock import MagicMock, Mock, patch

# Phase 2: Use builders and factories
from tests.utils.builders import TaskRunBuilder
from tests.utils.mocks import DatabaseMockFactory


class TestListTaskRunsEndpoint:
    """Test GET /api/task-runs endpoint."""

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_success(self, mock_db_session, authenticated_client):
        """Test listing task runs successfully."""
        # Phase 2: Use TaskRunBuilder instead of create_mock_task_run
        mock_runs = [
            TaskRunBuilder().with_id(1).with_type("slack_user_import").build(),
            TaskRunBuilder().with_id(2).with_type("google_drive_ingest").build(),
        ]

        # Phase 2: Setup database mock with proper chaining
        mock_query = MagicMock()
        mock_query.order_by().count.return_value = 2
        mock_query.order_by().offset().limit().all.return_value = mock_runs

        mock_session = MagicMock()
        mock_session.query.return_value = mock_query
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None
        mock_db_session.return_value = mock_context

        response = authenticated_client.get("/api/task-runs")

        assert response.status_code == 200
        data = response.json()
        assert "task_runs" in data
        assert "pagination" in data
        assert len(data["task_runs"]) == 2
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["total"] == 2

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_empty(self, mock_db_session, authenticated_client):
        """Test listing task runs when none exist."""
        # Phase 2: Use DatabaseMockFactory for empty results
        mock_db_session.return_value = DatabaseMockFactory.create_session_context([])

        response = authenticated_client.get("/api/task-runs")

        assert response.status_code == 200
        data = response.json()
        assert data["task_runs"] == []
        assert data["pagination"]["total"] == 0
        assert data["pagination"]["total_pages"] == 0

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_with_pagination(
        self, mock_db_session, authenticated_client
    ):
        """Test pagination parameters."""
        # Phase 2: Use TaskRunBuilder for test data
        mock_runs = [TaskRunBuilder().with_id(i).build() for i in range(25)]

        # Phase 2: Setup mock query chain properly (order_by returns ordered_query)
        mock_ordered_query = MagicMock()
        mock_ordered_query.count.return_value = 150
        mock_ordered_query.offset.return_value = mock_ordered_query
        mock_ordered_query.limit.return_value = mock_ordered_query
        mock_ordered_query.all.return_value = mock_runs

        mock_base_query = MagicMock()
        mock_base_query.order_by.return_value = mock_ordered_query

        mock_session = DatabaseMockFactory.create_session_with_custom_query(
            mock_base_query
        )
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None
        mock_db_session.return_value = mock_context

        response = authenticated_client.get("/api/task-runs?page=2&per_page=25")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["per_page"] == 25
        assert data["pagination"]["total"] == 150
        assert data["pagination"]["total_pages"] == 6
        assert data["pagination"]["has_prev"] is True
        assert data["pagination"]["has_next"] is True

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_max_page_size_cap(
        self, mock_db_session, authenticated_client
    ):
        """Test that per_page is capped at MAX_PAGE_SIZE."""
        # Phase 2: Setup mock query chain properly
        mock_ordered_query = MagicMock()
        mock_ordered_query.count.return_value = 200
        mock_ordered_query.offset.return_value = mock_ordered_query
        mock_ordered_query.limit.return_value = mock_ordered_query
        mock_ordered_query.all.return_value = []

        mock_base_query = MagicMock()
        mock_base_query.order_by.return_value = mock_ordered_query

        mock_session = DatabaseMockFactory.create_session_with_custom_query(
            mock_base_query
        )
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None
        mock_db_session.return_value = mock_context

        # Request 1000 items per page (should be capped at 500)
        response = authenticated_client.get("/api/task-runs?per_page=1000")

        assert response.status_code == 200
        data = response.json()
        # Should be silently capped at MAX_PAGE_SIZE (500)
        assert data["pagination"]["per_page"] == 500

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_with_custom_task_name(
        self, mock_db_session, authenticated_client
    ):
        """Test task runs with custom task names."""
        # Phase 2: Use TaskRunBuilder with fluent API
        mock_run = (
            TaskRunBuilder()
            .with_id(1)
            .with_type("slack_user_import")
            .with_job_id("job-1")
            .with_task_name("Daily User Sync")
            .build()
        )

        # Phase 2: Setup mock query chain properly
        mock_ordered_query = MagicMock()
        mock_ordered_query.count.return_value = 1
        mock_ordered_query.offset.return_value = mock_ordered_query
        mock_ordered_query.limit.return_value = mock_ordered_query
        mock_ordered_query.all.return_value = [mock_run]

        mock_base_query = MagicMock()
        mock_base_query.order_by.return_value = mock_ordered_query

        mock_session = DatabaseMockFactory.create_session_with_custom_query(
            mock_base_query
        )
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None
        mock_db_session.return_value = mock_context

        response = authenticated_client.get("/api/task-runs")

        assert response.status_code == 200
        data = response.json()
        assert data["task_runs"][0]["job_name"] == "Daily User Sync"

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_with_metadata_fallback(
        self, mock_db_session, authenticated_client
    ):
        """Test task runs fall back to metadata for job name."""
        from models.task_metadata import TaskMetadata

        # Phase 2: Use TaskRunBuilder (no task_name in snapshot)
        mock_run = (
            TaskRunBuilder()
            .with_id(1)
            .with_type("slack_user_import")
            .with_job_id("job-1")
            .build()
        )

        # Create metadata mock
        mock_metadata = Mock(spec=TaskMetadata)
        mock_metadata.job_id = "job-1"
        mock_metadata.task_name = "Metadata Task Name"

        # Phase 2: Mock both queries - TaskRun query chain
        mock_ordered_run_query = MagicMock()
        mock_ordered_run_query.count.return_value = 1
        mock_ordered_run_query.offset.return_value = mock_ordered_run_query
        mock_ordered_run_query.limit.return_value = mock_ordered_run_query
        mock_ordered_run_query.all.return_value = [mock_run]

        mock_base_run_query = MagicMock()
        mock_base_run_query.order_by.return_value = mock_ordered_run_query

        # TaskMetadata query chain
        mock_metadata_query = MagicMock()
        mock_metadata_query.filter.return_value = mock_metadata_query
        mock_metadata_query.all.return_value = [mock_metadata]

        mock_session = MagicMock()
        # query() is called twice: once for TaskRun, once for TaskMetadata
        mock_session.query.side_effect = [mock_base_run_query, mock_metadata_query]

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None
        mock_db_session.return_value = mock_context

        response = authenticated_client.get("/api/task-runs")

        assert response.status_code == 200
        data = response.json()
        assert data["task_runs"][0]["job_name"] == "Metadata Task Name"

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_with_job_type_fallback(
        self, mock_db_session, authenticated_client
    ):
        """Test task runs fall back to job type names."""
        # Phase 2: Use TaskRunBuilder (no task_name or metadata)
        mock_run = TaskRunBuilder().with_id(1).with_type("slack_user_import").build()

        # Phase 2: Mock TaskRun query chain
        mock_ordered_run_query = MagicMock()
        mock_ordered_run_query.count.return_value = 1
        mock_ordered_run_query.offset.return_value = mock_ordered_run_query
        mock_ordered_run_query.limit.return_value = mock_ordered_run_query
        mock_ordered_run_query.all.return_value = [mock_run]

        mock_base_run_query = MagicMock()
        mock_base_run_query.order_by.return_value = mock_ordered_run_query

        # No metadata found
        mock_metadata_query = MagicMock()
        mock_metadata_query.filter.return_value = mock_metadata_query
        mock_metadata_query.all.return_value = []

        mock_session = MagicMock()
        mock_session.query.side_effect = [mock_base_run_query, mock_metadata_query]

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None
        mock_db_session.return_value = mock_context

        response = authenticated_client.get("/api/task-runs")

        assert response.status_code == 200
        data = response.json()
        # Should use job_type_names mapping
        assert data["task_runs"][0]["job_name"] == "Slack User Import"

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_with_unknown_job_type(
        self, mock_db_session, authenticated_client
    ):
        """Test task runs with unknown job type."""
        # Phase 2: Use TaskRunBuilder with unknown job type
        mock_run = TaskRunBuilder().with_id(1).with_type("unknown_job_type").build()

        # Phase 2: Mock TaskRun query chain
        mock_ordered_run_query = MagicMock()
        mock_ordered_run_query.count.return_value = 1
        mock_ordered_run_query.offset.return_value = mock_ordered_run_query
        mock_ordered_run_query.limit.return_value = mock_ordered_run_query
        mock_ordered_run_query.all.return_value = [mock_run]

        mock_base_run_query = MagicMock()
        mock_base_run_query.order_by.return_value = mock_ordered_run_query

        mock_metadata_query = MagicMock()
        mock_metadata_query.filter.return_value = mock_metadata_query
        mock_metadata_query.all.return_value = []

        mock_session = MagicMock()
        mock_session.query.side_effect = [mock_base_run_query, mock_metadata_query]

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None
        mock_db_session.return_value = mock_context

        response = authenticated_client.get("/api/task-runs")

        assert response.status_code == 200
        data = response.json()
        # Should convert to title case
        assert data["task_runs"][0]["job_name"] == "Unknown Job Type"

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_with_failed_status(
        self, mock_db_session, authenticated_client
    ):
        """Test task runs with failed status."""
        # Phase 2: Use TaskRunBuilder with fluent API for failed status
        mock_run = (
            TaskRunBuilder().with_id(1).failed("Database connection timeout").build()
        )

        # Phase 2: Setup mock query chain properly
        mock_ordered_query = MagicMock()
        mock_ordered_query.count.return_value = 1
        mock_ordered_query.offset.return_value = mock_ordered_query
        mock_ordered_query.limit.return_value = mock_ordered_query
        mock_ordered_query.all.return_value = [mock_run]

        mock_base_query = MagicMock()
        mock_base_query.order_by.return_value = mock_ordered_query

        mock_session = DatabaseMockFactory.create_session_with_custom_query(
            mock_base_query
        )
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None
        mock_db_session.return_value = mock_context

        response = authenticated_client.get("/api/task-runs")

        assert response.status_code == 200
        data = response.json()
        assert data["task_runs"][0]["status"] == "failed"
        assert data["task_runs"][0]["error_message"] == "Database connection timeout"

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_pagination_edge_cases(
        self, mock_db_session, authenticated_client
    ):
        """Test pagination edge cases."""
        # Phase 2: Setup mock query chain properly
        mock_ordered_query = MagicMock()
        mock_ordered_query.count.return_value = 55  # Not evenly divisible
        mock_ordered_query.offset.return_value = mock_ordered_query
        mock_ordered_query.limit.return_value = mock_ordered_query
        mock_ordered_query.all.return_value = []

        mock_base_query = MagicMock()
        mock_base_query.order_by.return_value = mock_ordered_query

        mock_session = DatabaseMockFactory.create_session_with_custom_query(
            mock_base_query
        )
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None
        mock_db_session.return_value = mock_context

        response = authenticated_client.get("/api/task-runs?per_page=10")

        assert response.status_code == 200
        data = response.json()
        # 55 items / 10 per page = 6 pages (ceiling division)
        assert data["pagination"]["total_pages"] == 6

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_metadata_error_handling(
        self, mock_db_session, authenticated_client
    ):
        """Test graceful handling of metadata loading errors."""
        # Phase 2: Use TaskRunBuilder
        mock_run = TaskRunBuilder().with_id(1).with_job_id("job-1").build()

        # Phase 2: Mock TaskRun query chain
        mock_ordered_run_query = MagicMock()
        mock_ordered_run_query.count.return_value = 1
        mock_ordered_run_query.offset.return_value = mock_ordered_run_query
        mock_ordered_run_query.limit.return_value = mock_ordered_run_query
        mock_ordered_run_query.all.return_value = [mock_run]

        mock_base_run_query = MagicMock()
        mock_base_run_query.order_by.return_value = mock_ordered_run_query

        # Metadata query raises error
        mock_metadata_query = MagicMock()
        mock_metadata_query.filter.return_value = mock_metadata_query
        mock_metadata_query.all.side_effect = Exception("Database error")

        mock_session = MagicMock()
        mock_session.query.side_effect = [mock_base_run_query, mock_metadata_query]

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None
        mock_db_session.return_value = mock_context

        response = authenticated_client.get("/api/task-runs")

        # Should still succeed, just without metadata
        assert response.status_code == 200
        data = response.json()
        assert len(data["task_runs"]) == 1

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_database_error(self, mock_db_session, authenticated_client):
        """Test handling of database errors."""
        mock_db_session.side_effect = Exception("Database connection failed")

        response = authenticated_client.get("/api/task-runs")

        # Should raise HTTPException with 500 status
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Database connection failed" in data["detail"]

    @patch("api.task_runs.get_db_session")
    def test_list_task_runs_all_fields_present(
        self, mock_db_session, authenticated_client
    ):
        """Test that all expected fields are present in response."""
        # Phase 2: Use TaskRunBuilder
        mock_run = TaskRunBuilder().with_id(1).build()
        mock_run.triggered_by_user = "user@example.com"

        # Phase 2: Setup mock query chain properly
        mock_ordered_query = MagicMock()
        mock_ordered_query.count.return_value = 1
        mock_ordered_query.offset.return_value = mock_ordered_query
        mock_ordered_query.limit.return_value = mock_ordered_query
        mock_ordered_query.all.return_value = [mock_run]

        mock_base_query = MagicMock()
        mock_base_query.order_by.return_value = mock_ordered_query

        mock_session = DatabaseMockFactory.create_session_with_custom_query(
            mock_base_query
        )
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None
        mock_db_session.return_value = mock_context

        response = authenticated_client.get("/api/task-runs")

        assert response.status_code == 200
        data = response.json()
        run = data["task_runs"][0]

        # Verify all fields are present
        assert "id" in run
        assert "run_id" in run
        assert "job_type" in run
        assert "job_name" in run
        assert "status" in run
        assert "started_at" in run
        assert "completed_at" in run
        assert "duration_seconds" in run
        assert "triggered_by" in run
        assert "triggered_by_user" in run
        assert "error_message" in run
        assert "records_processed" in run
        assert "records_success" in run
        assert "records_failed" in run
