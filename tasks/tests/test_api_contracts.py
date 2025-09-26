"""
Tasks API Contract Tests

Protect against API changes that could break the dashboard UI.
"""

from unittest.mock import Mock, patch

import pytest

from app import create_app


class TestTasksAPIContracts:
    """Test Tasks/Scheduler API contracts"""

    @pytest.fixture
    def app(self):
        """Create test Flask app"""
        with (
            patch("app.SchedulerService"),
            patch("app.JobRegistry"),
            patch("app.get_settings") as mock_settings,
        ):
            mock_settings.return_value = Mock(
                secret_key="test-secret", flask_env="testing"
            )

            app = create_app()
            app.config["TESTING"] = True
            return app

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
            assert isinstance(data["uptime_seconds"], (int, float))

    def test_jobs_list_contract(self, client):
        """Test /api/jobs returns expected structure for job list"""
        with patch("app.job_registry") as mock_registry:
            mock_registry.get_jobs.return_value = [
                {
                    "id": "job-1",
                    "name": "Test Job",
                    "status": "running",
                    "next_run_time": "2024-01-15T10:00:00Z",
                    "last_run_time": "2024-01-15T09:00:00Z",
                    "trigger": "interval",
                    "args": [],
                    "kwargs": {},
                }
            ]

            response = client.get("/api/jobs")
            assert response.status_code == 200

            data = response.get_json()
            assert isinstance(data, list)

            if data:  # If jobs exist
                job = data[0]
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
        with patch("app.job_registry") as mock_registry:
            mock_registry.get_job.return_value = {
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
        mock_runs = [
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

        with patch("app.get_db_session") as mock_session:
            mock_query = Mock()
            mock_query.order_by.return_value.limit.return_value.offset.return_value = (
                mock_runs
            )
            mock_session.return_value.__enter__.return_value.query.return_value = (
                mock_query
            )

            response = client.get("/api/task-runs")
            assert response.status_code == 200

            data = response.get_json()

            # Verify pagination structure
            required_top_level = ["runs", "total", "page", "per_page"]
            for field in required_top_level:
                assert field in data, f"Missing pagination field: {field}"

            # Verify run structure if runs exist
            if data["runs"]:
                run = data["runs"][0]
                required_run_fields = [
                    "id",
                    "job_id",
                    "status",
                    "started_at",
                    "duration_seconds",
                    "triggered_by",
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

        with patch("app.job_registry") as mock_registry:
            mock_registry.create_job.return_value = {
                "id": "new-job-123",
                "status": "created",
                **job_payload,
            }

            response = client.post(
                "/api/jobs",
                json=job_payload,
                headers={"Content-Type": "application/json"},
            )

            assert response.status_code in [200, 201]

            data = response.get_json()
            assert "id" in data
            assert "status" in data

    def test_job_control_endpoints_contract(self, client):
        """Test job control endpoints (pause/resume/delete) maintain contracts"""
        job_id = "test-job-123"

        with patch("app.job_registry") as mock_registry:
            # Test pause
            mock_registry.pause_job.return_value = {"status": "paused"}
            response = client.post(f"/api/jobs/{job_id}/pause")
            assert response.status_code == 200
            data = response.get_json()
            assert "status" in data

            # Test resume
            mock_registry.resume_job.return_value = {"status": "running"}
            response = client.post(f"/api/jobs/{job_id}/resume")
            assert response.status_code == 200
            data = response.get_json()
            assert "status" in data

            # Test delete
            mock_registry.delete_job.return_value = {"status": "deleted"}
            response = client.delete(f"/api/jobs/{job_id}")
            assert response.status_code == 200
            data = response.get_json()
            assert "status" in data

    def test_error_response_format_consistency(self, client):
        """Test all endpoints return errors in consistent format"""
        # Test non-existent job
        response = client.get("/api/jobs/non-existent-job")

        # Should be 404 with consistent error format
        assert response.status_code == 404
        data = response.get_json()

        # Consistent error format across all endpoints
        error_fields = ["error", "message"]
        for field in error_fields:
            assert field in data, f"Missing error field: {field}"

    def test_job_types_endpoint_contract(self, client):
        """Test /api/job-types returns available job types for UI dropdown"""
        expected_job_types = [
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

        with patch("app.job_registry") as mock_registry:
            mock_registry.get_job_types.return_value = expected_job_types

            response = client.get("/api/job-types")
            assert response.status_code == 200

            data = response.get_json()
            assert isinstance(data, list)

            if data:
                job_type = data[0]
                required_type_fields = ["id", "name", "description", "config_schema"]

                for field in required_type_fields:
                    assert field in job_type, f"Missing job type field: {field}"


class TestAPISecurityContracts:
    """Test API security and authentication contracts"""

    def test_cors_headers_present(self, client):
        """Test CORS headers are present for frontend"""
        response = client.options("/api/jobs")

        # CORS headers required for frontend to work
        cors_headers = [
            "Access-Control-Allow-Origin",
            "Access-Control-Allow-Methods",
            "Access-Control-Allow-Headers",
        ]

        for header in cors_headers:
            assert header in response.headers, f"Missing CORS header: {header}"

    def test_content_type_validation(self, client):
        """Test API validates content types properly"""
        # Send invalid content type
        response = client.post(
            "/api/jobs", data="invalid json", headers={"Content-Type": "text/plain"}
        )

        # Should reject non-JSON content
        assert response.status_code in [400, 415]


class TestAPIPagination:
    """Test pagination contracts for large datasets"""

    def test_pagination_parameters(self, client):
        """Test pagination parameters work consistently"""
        with patch("app.get_db_session"):
            # Test with pagination params
            response = client.get("/api/task-runs?page=2&per_page=25")
            assert response.status_code == 200

            data = response.get_json()

            # Pagination info should match request
            assert data.get("page") == 2
            assert data.get("per_page") == 25
            assert "total" in data
            assert "runs" in data

    def test_pagination_limits(self, client):
        """Test pagination enforces reasonable limits"""
        with patch("app.get_db_session"):
            # Test excessive per_page gets limited
            response = client.get("/api/task-runs?per_page=10000")
            assert response.status_code == 200

            data = response.get_json()
            # Should be limited to reasonable max (e.g., 100)
            assert data.get("per_page", 0) <= 100
