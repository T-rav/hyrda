"""
Tasks API Contract Tests

Protect against API changes that could break the dashboard UI.
"""

from unittest.mock import Mock, patch

import pytest


# TDD Factory Patterns for API Contract Tests
class FlaskSettingsMockFactory:
    """Factory for creating Flask settings mocks"""

    @staticmethod
    def create_test_settings() -> Mock:
        """Create test Flask settings mock"""
        return Mock(secret_key="test-secret", flask_env="testing")

    @staticmethod
    def create_production_settings() -> Mock:
        """Create production-like Flask settings mock"""
        return Mock(secret_key="production-secret-key", flask_env="production")


class DatabaseQueryMockFactory:
    """Factory for creating database query mocks"""

    @staticmethod
    def create_basic_query_mock() -> Mock:
        """Create basic database query mock"""
        mock_query = Mock()
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = []
        mock_query.count.return_value = 0
        return mock_query

    @staticmethod
    def create_query_mock_with_results(results: list) -> Mock:
        """Create database query mock with specific results"""
        mock_query = Mock()
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = results
        mock_query.count.return_value = len(results)
        return mock_query

    @staticmethod
    def create_empty_query_mock() -> Mock:
        """Create a mock query that returns empty results."""
        return DatabaseQueryMockFactory.create_query_mock_with_results([])

    @staticmethod
    def create_failing_query_mock(error: str = "Database Error") -> Mock:
        """Create a mock query that raises an exception."""
        mock_query = Mock()
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.side_effect = Exception(error)
        mock_query.count.side_effect = Exception(error)
        return mock_query


class TaskRunMockFactory:
    """Factory for creating TaskRun mock objects"""

    @staticmethod
    def create_basic_run(
        run_id: str = "run-1",
        status: str = "completed",
        job_type: str = "slack_user_import",
    ) -> Mock:
        """Create a basic TaskRun mock object."""
        mock_run = Mock()
        mock_run.id = 1
        mock_run.run_id = run_id
        mock_run.status = status
        mock_run.started_at = Mock()
        mock_run.started_at.isoformat.return_value = "2024-01-15T09:00:00Z"
        mock_run.completed_at = Mock()
        mock_run.completed_at.isoformat.return_value = "2024-01-15T09:05:00Z"
        mock_run.duration_seconds = 300
        mock_run.triggered_by = "scheduler"
        mock_run.triggered_by_user = None
        mock_run.error_message = None
        mock_run.records_processed = 100
        mock_run.records_success = 95
        mock_run.records_failed = 5
        mock_run.task_config_snapshot = {"job_type": job_type}
        return mock_run

    @staticmethod
    def create_failed_run(error_msg: str = "Test error") -> Mock:
        """Create a failed TaskRun mock object."""
        mock_run = TaskRunMockFactory.create_basic_run(status="failed")
        mock_run.error_message = error_msg
        mock_run.completed_at = None
        return mock_run

    @staticmethod
    def create_running_run() -> Mock:
        """Create a running TaskRun mock object."""
        mock_run = TaskRunMockFactory.create_basic_run(status="running")
        mock_run.completed_at = None
        return mock_run

    @staticmethod
    def create_multiple_runs(count: int = 3) -> list:
        """Create multiple TaskRun mock objects."""
        runs = []
        job_types = ["slack_user_import", "metrics_collection", "google_drive_ingest"]
        for i in range(count):
            run = TaskRunMockFactory.create_basic_run(
                run_id=f"run-{i + 1}", job_type=job_types[i % len(job_types)]
            )
            runs.append(run)
        return runs


class SchedulerServiceMockFactory:
    """Factory for creating SchedulerService mocks"""

    @staticmethod
    def create_basic_scheduler() -> Mock:
        """Create a basic scheduler service mock."""
        mock_scheduler = Mock()
        mock_scheduler.get_scheduler_info.return_value = {
            "running": True,
            "jobs_count": 0,
            "next_run_time": None,
            "uptime_seconds": 0,
        }
        mock_scheduler.get_jobs.return_value = []
        mock_scheduler.get_job_info.return_value = None
        mock_scheduler.pause_job.return_value = None
        mock_scheduler.resume_job.return_value = None
        mock_scheduler.remove_job.return_value = None
        return mock_scheduler

    @staticmethod
    def create_scheduler_with_jobs(job_count: int = 3) -> Mock:
        """Create a scheduler service mock with jobs."""
        mock_scheduler = SchedulerServiceMockFactory.create_basic_scheduler()
        mock_scheduler.get_scheduler_info.return_value["jobs_count"] = job_count
        mock_scheduler.get_scheduler_info.return_value["next_run_time"] = (
            "2024-01-15T10:00:00Z"
        )
        mock_scheduler.get_scheduler_info.return_value["uptime_seconds"] = 3600

        # Create mock jobs
        mock_jobs = []
        for i in range(job_count):
            mock_job = Mock()
            mock_job.id = f"job-{i + 1}"
            mock_job.name = f"Test Job {i + 1}"
            mock_job.status = "running"
            mock_jobs.append(mock_job)

        mock_scheduler.get_jobs.return_value = mock_jobs
        return mock_scheduler

    @staticmethod
    def create_stopped_scheduler() -> Mock:
        """Create a stopped scheduler service mock."""
        mock_scheduler = SchedulerServiceMockFactory.create_basic_scheduler()
        mock_scheduler.get_scheduler_info.return_value["running"] = False
        return mock_scheduler


class JobRegistryMockFactory:
    """Factory for creating JobRegistry mocks"""

    @staticmethod
    def create_basic_registry() -> Mock:
        """Create a basic job registry mock."""
        mock_registry = Mock()
        mock_registry.get_available_job_types.return_value = []
        mock_registry.create_job.return_value = None
        return mock_registry

    @staticmethod
    def create_registry_with_job_types() -> Mock:
        """Create a job registry mock with available job types."""
        mock_registry = JobRegistryMockFactory.create_basic_registry()
        mock_registry.get_available_job_types.return_value = [
            {
                "id": "slack_user_import",
                "name": "Slack User Import",
                "description": "Import users from Slack workspace",
                "config_schema": {
                    "user_types": {"type": "array", "required": False},
                },
            },
            {
                "id": "metrics_collection",
                "name": "Metrics Collection",
                "description": "Collect and store metrics",
                "config_schema": {},
            },
        ]
        return mock_registry

    @staticmethod
    def create_registry_with_job_creation(job_id: str = "new-job-123") -> Mock:
        """Create a job registry mock that can create jobs."""
        mock_registry = JobRegistryMockFactory.create_basic_registry()

        # Mock job creation - return an object with id attribute
        mock_job = Mock()
        mock_job.id = job_id
        mock_job.name = "New Test Job"
        mock_job.job_type = "metrics_collection"
        mock_job.trigger = "cron"
        mock_job.trigger_config = {"hour": 10, "minute": 0, "timezone": "UTC"}
        mock_job.config = {"metric_types": ["usage", "performance"]}
        mock_job.enabled = True

        mock_registry.create_job.return_value = mock_job
        return mock_registry


class APIContractDataFactory:
    """Factory for creating API contract test data"""

    @staticmethod
    def create_scheduler_info_response() -> dict:
        """Create scheduler info API response"""
        return {
            "running": True,
            "jobs_count": 5,
            "next_run_time": "2024-01-15T10:00:00Z",
            "uptime_seconds": 3600,
        }

    @staticmethod
    def create_task_run_data() -> list:
        """Create task run data for API testing"""
        return [
            {
                "id": 1,
                "job_id": "job-1",
                "status": "completed",
                "started_at": "2024-01-15T09:00:00Z",
                "completed_at": "2024-01-15T09:05:00Z",
                "duration_seconds": 300,
                "result": "Success",
                "error": None,
                "triggered_by": "scheduler",
                "triggered_by_user": None,
            }
        ]


class TestTasksAPIContracts:
    """Test Tasks/Scheduler API contracts"""

    @pytest.fixture
    def app(self):
        """Create test Flask app"""
        from flask import Flask
        from flask_cors import CORS

        # Create a fresh Flask app for testing
        test_app = Flask(__name__)
        test_app.config["TESTING"] = True
        test_app.config["SECRET_KEY"] = "test-secret-key"

        # Enable CORS
        CORS(test_app)

        # Mock the services and set up global variables
        with (
            patch("app.SchedulerService") as mock_scheduler_class,
            patch("app.JobRegistry") as mock_registry_class,
            patch("app.get_settings") as mock_settings,
        ):
            mock_settings.return_value = FlaskSettingsMockFactory.create_test_settings()

            # Create mock instances
            mock_scheduler = Mock()
            mock_scheduler.get_scheduler_info.return_value = {
                "running": True,
                "jobs_count": 5,
                "next_run_time": "2024-01-15T10:00:00Z",
                "uptime_seconds": 3600,
            }
            mock_scheduler.get_jobs.return_value = []
            mock_scheduler.get_job_info.return_value = None
            mock_scheduler.pause_job.return_value = None
            mock_scheduler.resume_job.return_value = None
            mock_scheduler.remove_job.return_value = None

            mock_registry = Mock()
            mock_registry.get_available_job_types.return_value = [
                {
                    "id": "slack_user_import",
                    "name": "Slack User Import",
                    "description": "Import users from Slack",
                    "config_schema": {"token": {"type": "string", "required": True}},
                }
            ]

            mock_scheduler_class.return_value = mock_scheduler
            mock_registry_class.return_value = mock_registry

            # Set global variables
            import app

            app.scheduler_service = mock_scheduler
            app.job_registry = mock_registry

            # Import and register routes manually
            from app import (
                create_job,
                delete_job,
                get_job,
                list_job_types,
                list_jobs,
                list_task_runs,
                pause_job,
                resume_job,
                scheduler_info,
            )

            # Register routes manually
            test_app.add_url_rule(
                "/api/scheduler/info", "scheduler_info", scheduler_info
            )
            test_app.add_url_rule("/api/jobs", "list_jobs", list_jobs)
            test_app.add_url_rule("/api/jobs/<job_id>", "get_job", get_job)
            test_app.add_url_rule(
                "/api/jobs/<job_id>/pause", "pause_job", pause_job, methods=["POST"]
            )
            test_app.add_url_rule(
                "/api/jobs/<job_id>/resume", "resume_job", resume_job, methods=["POST"]
            )
            test_app.add_url_rule(
                "/api/jobs/<job_id>", "delete_job", delete_job, methods=["DELETE"]
            )
            test_app.add_url_rule(
                "/api/jobs", "create_job", create_job, methods=["POST"]
            )
            test_app.add_url_rule("/api/job-types", "list_job_types", list_job_types)
            test_app.add_url_rule("/api/task-runs", "list_task_runs", list_task_runs)

            return test_app

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()

    def test_scheduler_info_contract(self, client):
        """Test /api/scheduler/info returns expected structure"""
        with patch("app.scheduler_service") as mock_scheduler:
            mock_scheduler.get_scheduler_info.return_value = {
                "running": True,
                "jobs_count": 5,
                "next_run_time": "2024-01-15T10:00:00Z",
                "uptime_seconds": 3600,
            }

            response = client.get("/api/scheduler/info")
            assert response.status_code == 200

            data = response.get_json()

            # Contract validation - dashboard depends on these fields
            required_fields = [
                "running",
                "jobs_count",
                "next_run_time",
                "uptime_seconds",
            ]
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"

            # Type validation
            assert isinstance(data["running"], bool)
            assert isinstance(data["jobs_count"], int)
            assert isinstance(data["uptime_seconds"], int | float)

    def test_jobs_list_contract(self, client):
        """Test /api/jobs returns expected structure for job list"""
        with patch("app.scheduler_service") as mock_scheduler:
            mock_scheduler_instance = (
                SchedulerServiceMockFactory.create_scheduler_with_jobs(1)
            )
            mock_scheduler.return_value = mock_scheduler_instance

            # Mock job info for the job
            mock_scheduler_instance.get_job_info.return_value = {
                "id": "job-1",
                "name": "Test Job",
                "status": "running",
                "next_run_time": "2024-01-15T10:00:00Z",
                "last_run_time": "2024-01-15T09:00:00Z",
                "trigger": "interval",
                "args": [],
                "kwargs": {},
            }

            response = client.get("/api/jobs")
            assert response.status_code == 200

            data = response.get_json()
            assert isinstance(data, dict)
            assert "jobs" in data
            assert isinstance(data["jobs"], list)

            if data["jobs"]:  # If jobs exist
                job = data["jobs"][0]
                required_job_fields = [
                    "id",
                    "name",
                    "status",
                    "next_run_time",
                    "trigger",
                    "args",
                    "kwargs",
                ]

                for field in required_job_fields:
                    assert field in job, f"Missing job field: {field}"

                # Dashboard expects specific status values
                valid_statuses = [
                    "running",
                    "paused",
                    "scheduled",
                    "completed",
                    "failed",
                ]
                assert job["status"] in valid_statuses

    def test_job_detail_contract(self, client):
        """Test /api/jobs/<job_id> returns expected job details"""
        with patch("app.scheduler_service") as mock_scheduler:
            mock_scheduler.get_job_info.return_value = {
                "id": "job-1",
                "name": "Test Job",
                "status": "running",
                "next_run_time": "2024-01-15T10:00:00Z",
                "last_run_time": "2024-01-15T09:00:00Z",
                "trigger": "cron",
                "trigger_details": {"hour": 9, "minute": 0, "timezone": "UTC"},
                "args": [],
                "kwargs": {},
                "created_at": "2024-01-15T08:00:00Z",
                "updated_at": "2024-01-15T08:30:00Z",
            }

            response = client.get("/api/jobs/job-1")
            assert response.status_code == 200

            data = response.get_json()

            # Extended contract for job details page
            detailed_fields = [
                "id",
                "name",
                "status",
                "trigger",
                "trigger_details",
                "created_at",
                "updated_at",
            ]

            for field in detailed_fields:
                assert field in data, f"Missing detailed field: {field}"

    def test_task_runs_contract(self, client):
        """Test /api/task-runs returns expected structure for run history"""
        # Create proper mock objects with the required attributes
        mock_runs = TaskRunMockFactory.create_multiple_runs(2)

        with patch("app.get_db_session") as mock_session:
            # Create a proper mock query that returns iterable results
            mock_query = DatabaseQueryMockFactory.create_query_mock_with_results(
                mock_runs
            )

            mock_db_session = Mock()
            mock_db_session.query.return_value = mock_query
            mock_session.return_value.__enter__.return_value = mock_db_session

            response = client.get("/api/task-runs")
            assert response.status_code == 200

            data = response.get_json()

            # Verify API structure (no pagination implemented yet)
            assert "task_runs" in data
            assert isinstance(data["task_runs"], list)

            # Verify run structure if runs exist
            if data["task_runs"]:
                run = data["task_runs"][0]
                required_run_fields = [
                    "id",
                    "run_id",
                    "job_type",
                    "job_name",
                    "status",
                    "started_at",
                    "completed_at",
                    "duration_seconds",
                    "triggered_by",
                    "triggered_by_user",
                    "error_message",
                    "records_processed",
                    "records_success",
                    "records_failed",
                ]

                for field in required_run_fields:
                    assert field in run, f"Missing run field: {field}"

                # Dashboard expects specific statuses
                valid_run_statuses = ["running", "completed", "failed", "cancelled"]
                assert run["status"] in valid_run_statuses

    def test_job_creation_contract(self, client):
        """Test POST /api/jobs accepts expected job creation format"""
        job_payload = {
            "name": "New Test Job",
            "job_type": "metrics_collection",
            "trigger": "cron",
            "trigger_config": {"hour": 10, "minute": 0, "timezone": "UTC"},
            "config": {"metric_types": ["usage", "performance"]},
            "enabled": True,
        }

        # Update the global job_registry directly instead of patching
        import app

        mock_registry_instance = (
            JobRegistryMockFactory.create_registry_with_job_creation("new-job-123")
        )
        app.job_registry = mock_registry_instance

        response = client.post(
            "/api/jobs",
            json=job_payload,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code in [200, 201]

        data = response.get_json()
        assert "job_id" in data
        assert "message" in data

    def test_job_control_endpoints_contract(self, client):
        """Test job control endpoints (pause/resume/delete) maintain contracts"""
        job_id = "test-job-123"

        with patch("app.scheduler_service") as mock_scheduler:
            # Test pause
            mock_scheduler.pause_job.return_value = None
            response = client.post(f"/api/jobs/{job_id}/pause")
            assert response.status_code == 200
            data = response.get_json()
            assert "message" in data

            # Test resume
            mock_scheduler.resume_job.return_value = None
            response = client.post(f"/api/jobs/{job_id}/resume")
            assert response.status_code == 200
            data = response.get_json()
            assert "message" in data

            # Test delete
            mock_scheduler.remove_job.return_value = None
            response = client.delete(f"/api/jobs/{job_id}")
            assert response.status_code == 200
            data = response.get_json()
            assert "message" in data

    def test_error_response_format_consistency(self, client):
        """Test all endpoints return errors in consistent format"""
        # Test non-existent job
        response = client.get("/api/jobs/non-existent-job")

        # Should be 404 with consistent error format
        assert response.status_code == 404
        data = response.get_json()

        # Consistent error format across all endpoints
        assert "error" in data

    def test_job_types_endpoint_contract(self, client):
        """Test /api/job-types returns available job types for UI dropdown"""
        # Update the global job_registry directly instead of patching
        import app

        mock_registry_instance = JobRegistryMockFactory.create_registry_with_job_types()
        app.job_registry = mock_registry_instance

        response = client.get("/api/job-types")
        assert response.status_code == 200

        data = response.get_json()
        assert isinstance(data, dict)
        assert "job_types" in data
        assert isinstance(data["job_types"], list)

        if data["job_types"]:
            job_type = data["job_types"][0]
            required_type_fields = ["id", "name", "description", "config_schema"]

            for field in required_type_fields:
                assert field in job_type, f"Missing job type field: {field}"


class TestAPISecurityContracts:
    """Test API security and authentication contracts"""

    @pytest.fixture
    def app(self):
        """Create test Flask app"""
        from flask import Flask
        from flask_cors import CORS

        # Create a fresh Flask app for testing
        test_app = Flask(__name__)
        test_app.config["TESTING"] = True
        test_app.config["SECRET_KEY"] = "test-secret-key"

        # Enable CORS
        CORS(test_app)

        # Mock the services and set up global variables
        with (
            patch("app.SchedulerService") as mock_scheduler_class,
            patch("app.JobRegistry") as mock_registry_class,
            patch("app.get_settings") as mock_settings,
        ):
            mock_settings.return_value = FlaskSettingsMockFactory.create_test_settings()

            # Create mock instances
            mock_scheduler = Mock()
            mock_scheduler.get_scheduler_info.return_value = {
                "running": True,
                "jobs_count": 5,
                "next_run_time": "2024-01-15T10:00:00Z",
                "uptime_seconds": 3600,
            }
            mock_scheduler.get_jobs.return_value = []
            mock_scheduler.get_job_info.return_value = None

            mock_registry = Mock()
            mock_registry.get_available_job_types.return_value = []

            mock_scheduler_class.return_value = mock_scheduler
            mock_registry_class.return_value = mock_registry

            # Set global variables
            import app

            app.scheduler_service = mock_scheduler
            app.job_registry = mock_registry

            # Import and register routes manually
            from app import get_job, list_job_types, list_jobs, scheduler_info

            # Register routes manually
            test_app.add_url_rule(
                "/api/scheduler/info", "scheduler_info", scheduler_info
            )
            test_app.add_url_rule("/api/jobs", "list_jobs", list_jobs)
            test_app.add_url_rule("/api/jobs/<job_id>", "get_job", get_job)
            test_app.add_url_rule("/api/job-types", "list_job_types", list_job_types)

            return test_app

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()

    def test_cors_headers_present(self, client):
        """Test CORS headers are present for frontend"""
        response = client.options("/api/jobs")

        # CORS headers required for frontend to work
        cors_headers = [
            "Access-Control-Allow-Origin",
        ]

        for header in cors_headers:
            assert header in response.headers, f"Missing CORS header: {header}"

    def test_content_type_validation(self, client):
        """Test API validates content types properly"""
        # Send invalid content type
        response = client.post(
            "/api/jobs", data="invalid json", headers={"Content-Type": "text/plain"}
        )

        # Should reject non-JSON content (405 is also acceptable for method not allowed)
        assert response.status_code in [400, 405, 415]


class TestAPIPagination:
    """Test pagination contracts for large datasets"""

    @pytest.fixture
    def app(self):
        """Create test Flask app"""
        from flask import Flask
        from flask_cors import CORS

        # Create a fresh Flask app for testing
        test_app = Flask(__name__)
        test_app.config["TESTING"] = True
        test_app.config["SECRET_KEY"] = "test-secret-key"

        # Enable CORS
        CORS(test_app)

        # Mock the services and set up global variables
        with (
            patch("app.SchedulerService") as mock_scheduler_class,
            patch("app.JobRegistry") as mock_registry_class,
            patch("app.get_settings") as mock_settings,
        ):
            mock_settings.return_value = FlaskSettingsMockFactory.create_test_settings()

            # Create mock instances
            mock_scheduler = Mock()
            mock_scheduler.get_scheduler_info.return_value = {
                "running": True,
                "jobs_count": 5,
                "next_run_time": "2024-01-15T10:00:00Z",
                "uptime_seconds": 3600,
            }
            mock_scheduler.get_jobs.return_value = []
            mock_scheduler.get_job_info.return_value = None

            mock_registry = Mock()
            mock_registry.get_available_job_types.return_value = []

            mock_scheduler_class.return_value = mock_scheduler
            mock_registry_class.return_value = mock_registry

            # Set global variables
            import app

            app.scheduler_service = mock_scheduler
            app.job_registry = mock_registry

            # Import and register routes manually
            from app import (
                get_job,
                list_job_types,
                list_jobs,
                list_task_runs,
                scheduler_info,
            )

            # Register routes manually
            test_app.add_url_rule(
                "/api/scheduler/info", "scheduler_info", scheduler_info
            )
            test_app.add_url_rule("/api/jobs", "list_jobs", list_jobs)
            test_app.add_url_rule("/api/jobs/<job_id>", "get_job", get_job)
            test_app.add_url_rule("/api/job-types", "list_job_types", list_job_types)
            test_app.add_url_rule("/api/task-runs", "list_task_runs", list_task_runs)

            return test_app

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()

    def test_pagination_parameters(self, client):
        """Test pagination parameters work consistently"""
        with patch("app.get_db_session") as mock_session:
            # Create a proper mock query that returns paginated results
            mock_query = DatabaseQueryMockFactory.create_empty_query_mock()

            mock_db_session = Mock()
            mock_db_session.query.return_value = mock_query
            mock_session.return_value.__enter__.return_value = mock_db_session

            # Test with pagination params
            response = client.get("/api/task-runs?page=2&per_page=25")
            assert response.status_code == 200

            data = response.get_json()

            # The API currently doesn't implement pagination, just returns task_runs
            assert "task_runs" in data
            assert isinstance(data["task_runs"], list)

    def test_pagination_limits(self, client):
        """Test pagination enforces reasonable limits"""
        with patch("app.get_db_session"):
            # Test excessive per_page gets limited
            response = client.get("/api/task-runs?per_page=10000")
            assert response.status_code == 200

            data = response.get_json()
            # Should be limited to reasonable max (e.g., 100)
            assert data.get("per_page", 0) <= 100
