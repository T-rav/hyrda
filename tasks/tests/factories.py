"""Test factories for creating test fixtures."""

import os
from unittest.mock import MagicMock, Mock

from fastapi import FastAPI


class MockSchedulerFactory:
    """Factory for creating mock scheduler instances."""

    @staticmethod
    def create(
        running: bool = True,
        jobs_count: int = 5,
        next_run_time: str = "2024-01-15T10:00:00Z",
        uptime_seconds: int = 3600,
    ):
        """Create a mock scheduler with configurable responses."""
        mock_scheduler = Mock()
        mock_scheduler.get_scheduler_info.return_value = {
            "running": running,
            "jobs_count": jobs_count,
            "next_run_time": next_run_time,
            "uptime_seconds": uptime_seconds,
        }
        mock_scheduler.get_jobs.return_value = []
        mock_scheduler.get_job_info.return_value = None
        mock_scheduler.pause_job.return_value = None
        mock_scheduler.resume_job.return_value = None
        mock_scheduler.remove_job.return_value = None
        mock_scheduler.scheduler.running = running
        mock_scheduler.start.return_value = None
        return mock_scheduler


class MockJobRegistryFactory:
    """Factory for creating mock job registry instances."""

    @staticmethod
    def create(job_types: list[dict] | None = None):
        """Create a mock job registry with configurable job types."""
        if job_types is None:
            job_types = [
                {
                    "id": "slack_user_import",
                    "name": "Slack User Import",
                    "description": "Import users from Slack",
                    "config_schema": {"token": {"type": "string", "required": True}},
                }
            ]

        mock_registry = Mock()
        mock_registry.get_available_job_types.return_value = job_types
        return mock_registry


class FastAPIAppFactory:
    """Factory for creating FastAPI test apps with proper isolation."""

    @staticmethod
    def create_test_app(
        mock_scheduler=None,
        mock_registry=None,
        with_auth: bool = True,
    ) -> FastAPI:
        """
        Create a fresh FastAPI app for testing.

        Args:
            mock_scheduler: Mock scheduler instance (creates default if None)
            mock_registry: Mock job registry instance (creates default if None)
            with_auth: Whether to set up authenticated session

        Returns:
            Configured FastAPI test app
        """
        import sys
        from unittest.mock import Mock

        # Clear cached modules for true isolation
        modules_to_clear = [
            m
            for m in list(sys.modules.keys())
            if m.startswith("app") or m.startswith("api.")
        ]
        for module in modules_to_clear:
            sys.modules.pop(module, None)

        # Create mocks if not provided
        if mock_scheduler is None:
            mock_scheduler = MockSchedulerFactory.create()
        if mock_registry is None:
            mock_registry = MockJobRegistryFactory.create()

        # Import and patch
        import app

        app.SchedulerService = Mock(return_value=mock_scheduler)
        app.JobRegistry = Mock(return_value=mock_registry)

        from config.settings import TasksSettings

        # Note: No longer setting ENVIRONMENT=testing
        # All tests use proper authentication via session cookies

        mock_settings = MagicMock(spec=TasksSettings)
        mock_settings.secret_key = "test-secret-key"
        mock_settings.server_base_url = "http://localhost:5001"
        app.get_settings = Mock(return_value=mock_settings)

        # Create app
        from app import create_app

        test_app = create_app()
        # FastAPI doesn't have config dict - store services in app.state instead
        test_app.state.scheduler_service = mock_scheduler
        test_app.state.job_registry = mock_registry

        # Patch auth module to use test domain (ALLOWED_DOMAIN is loaded at import time)
        import utils.auth

        # Read from environment (set by conftest or mock_oauth_env) with fallback to "test.com"
        # This allows tests to override the domain via env vars
        test_domain = os.getenv("ALLOWED_EMAIL_DOMAIN", "test.com")
        utils.auth.ALLOWED_DOMAIN = test_domain

        # Ensure OAuth vars are set (required by auth middleware)
        if not utils.auth.GOOGLE_CLIENT_ID:
            utils.auth.GOOGLE_CLIENT_ID = "test-client-id.apps.googleusercontent.com"
        if not utils.auth.GOOGLE_CLIENT_SECRET:
            utils.auth.GOOGLE_CLIENT_SECRET = "test-client-secret"

        # Mock database session to avoid "no such table" errors
        from contextlib import contextmanager

        @contextmanager
        def mock_db_session():
            """Mock database session that returns empty results."""
            mock_session = Mock()
            mock_query = Mock()
            mock_query.all.return_value = []
            mock_query.first.return_value = None
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_session.query.return_value = mock_query
            mock_session.add = Mock()
            mock_session.delete = Mock()
            mock_session.commit = Mock()
            yield mock_session

        # Initialize test database with tables
        import models.base
        from models.oauth_credential import OAuthCredential
        from models.task_metadata import TaskMetadata
        from models.task_run import TaskRun

        # Create tables in the test database
        try:
            test_task_db = os.getenv("TASK_DATABASE_URL", "sqlite:///:memory:")
            models.base.init_db(test_task_db)

            # Import models to register them with Base.metadata before create_all
            from models.oauth_credential import OAuthCredential  # noqa: F401
            from models.task_metadata import TaskMetadata  # noqa: F401
            from models.task_run import TaskRun  # noqa: F401

            models.base.Base.metadata.create_all(bind=models.base._engine)

            test_data_db = os.getenv("DATA_DATABASE_URL", "sqlite:///:memory:")
            models.base.init_data_db(test_data_db)
            models.base.Base.metadata.create_all(bind=models.base._data_engine)
        except Exception as e:
            # If table creation fails, use mock (for tests that don't need real DB)
            import traceback

            print(f"Warning: Database initialization failed: {e}")
            traceback.print_exc()
            models.base.get_db_session = mock_db_session

        # Mock services already set in app.state above
        # FastAPI doesn't have app.extensions, using app.state instead

        return test_app

    @staticmethod
    def create_test_client(test_app: FastAPI, authenticated: bool = True):
        """
        Create a test client from a FastAPI app.

        Args:
            test_app: FastAPI application instance
            authenticated: Whether to set up an authenticated session

        Returns:
            FastAPI test client
        """
        from starlette.testclient import TestClient

        client = TestClient(test_app)

        if authenticated:
            # FastAPI standard: Use dependency overrides for authenticated tests
            from dependencies.auth import get_current_user, require_admin_from_database

            # Override the auth dependency to return a mock admin user
            async def mock_get_current_user():
                return {
                    "email": "test@test.com",
                    "name": "Test User",
                    "is_admin": True,  # Grant admin access for tests
                }

            # Override admin verification to avoid HTTP calls to control plane
            async def mock_require_admin():
                return {
                    "email": "test@test.com",
                    "name": "Test Admin",
                    "is_admin": True,
                }

            test_app.dependency_overrides[get_current_user] = mock_get_current_user
            test_app.dependency_overrides[require_admin_from_database] = (
                mock_require_admin
            )

        return client
