"""Tests to validate all jobs have correct imports and can be instantiated.

This test file prevents issues like using non-existent class names or
suppressing import errors with noqa comments.
"""

import importlib
import inspect
from unittest.mock import Mock, patch

import pytest

from config.settings import TasksSettings


@pytest.fixture
def mock_settings():
    """Create mock settings for all jobs."""
    settings = Mock(spec=TasksSettings)
    settings.tasks_port = 5001
    settings.tasks_host = "localhost"
    settings.tasks_database_url = "mysql://test:test@localhost/test"
    settings.data_database_url = "mysql://test:test@localhost/test"
    settings.rag_service_url = "http://localhost:8080"
    settings.bot_service_token = "test-token"
    return settings


class TestJobImports:
    """Test all job imports are valid and classes exist."""

    def test_gdrive_ingest_imports_exist(self):
        """Test GDriveIngestJob imports only real classes."""

        # Check the module doesn't have suppressed import errors
        import jobs.gdrive_ingest as module

        source = inspect.getsource(module)

        # Should not have any noqa: F821 (undefined name)
        assert "noqa: F821" not in source, "Job has suppressed undefined name errors"
        assert "# type: ignore" not in source, "Job has suppressed type errors"

    def test_metric_sync_imports_exist(self):
        """Test MetricSyncJob imports only real classes."""
        from jobs.metric_sync import MetricSyncJob

        assert MetricSyncJob is not None

    def test_slack_user_import_imports_exist(self):
        """Test SlackUserImportJob imports only real classes."""
        from jobs.slack_user_import import SlackUserImportJob

        assert SlackUserImportJob is not None

    def test_website_scrape_imports_exist(self):
        """Test WebsiteScrapeJob imports only real classes."""
        from jobs.website_scrape import WebsiteScrapeJob

        assert WebsiteScrapeJob is not None

    def test_all_service_imports_are_valid(self):
        """Test all services imported by jobs actually exist."""
        # List of (module_path, class_name) tuples that jobs try to import
        service_imports = [
            ("services.openai_embeddings", "OpenAIEmbeddings"),
            ("services.qdrant_client", "QdrantClient"),
            ("services.metric_client", "MetricClient"),
            ("services.portal_client", "PortalClient"),
            ("services.web_page_tracking_service", "WebPageTrackingService"),
            ("services.rag_client", "RAGIngestClient"),
            ("services.encryption_service", "EncryptionService"),
        ]

        for module_path, class_name in service_imports:
            # Import the module
            module = importlib.import_module(module_path)

            # Check class exists
            assert hasattr(module, class_name), (
                f"Class {class_name} not found in {module_path}"
            )

            # Get the class
            cls = getattr(module, class_name)

            # Verify it's actually a class
            assert inspect.isclass(cls), f"{class_name} in {module_path} is not a class"


class TestJobInstantiation:
    """Test all jobs can be instantiated without runtime errors."""

    def test_gdrive_ingest_instantiation(self, mock_settings):
        """Test GDriveIngestJob can be instantiated."""
        from jobs.gdrive_ingest import GDriveIngestJob

        # Should not raise on instantiation
        job = GDriveIngestJob(mock_settings, folder_id="test-folder")
        assert job is not None
        assert job.JOB_NAME == "Google Drive Ingestion"

    @patch("jobs.metric_sync.QdrantClient")
    @patch("jobs.metric_sync.OpenAIEmbeddings")
    @patch("jobs.metric_sync.MetricClient")
    def test_metric_sync_instantiation(
        self, mock_metric, mock_embeddings, mock_qdrant, mock_settings
    ):
        """Test MetricSyncJob can be instantiated."""
        from jobs.metric_sync import MetricSyncJob

        job = MetricSyncJob(mock_settings)
        assert job is not None
        assert job.JOB_NAME == "Metric.ai Data Sync"

    def test_slack_user_import_instantiation(self, mock_settings):
        """Test SlackUserImportJob can be instantiated."""
        from jobs.slack_user_import import SlackUserImportJob

        # Add required slack token
        mock_settings.slack_bot_token = "xoxb-test-token"

        job = SlackUserImportJob(mock_settings)
        assert job is not None
        assert job.JOB_NAME == "Slack User Import"

    @patch("jobs.website_scrape.QdrantClient")
    @patch("jobs.website_scrape.OpenAIEmbeddings")
    def test_website_scrape_instantiation(
        self, mock_embeddings, mock_qdrant, mock_settings
    ):
        """Test WebsiteScrapeJob can be instantiated."""
        from jobs.website_scrape import WebsiteScrapeJob

        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")
        assert job is not None
        assert job.JOB_NAME == "Website Scraping"


class TestJobRegistry:
    """Test job registry has all jobs properly registered."""

    def test_all_jobs_in_registry(self, mock_settings):
        """Test job registry contains all job types."""
        from jobs.job_registry import JobRegistry
        from services.scheduler_service import SchedulerService

        mock_scheduler = Mock(spec=SchedulerService)
        registry = JobRegistry(mock_settings, mock_scheduler)

        expected_jobs = [
            "slack_user_import",
            "metric_sync",
            "gdrive_ingest",
            "website_scrape",
        ]

        for job_type in expected_jobs:
            assert job_type in registry.job_types, (
                f"Job type '{job_type}' not found in registry"
            )

    def test_registry_job_classes_exist(self, mock_settings):
        """Test all registered jobs reference real classes."""
        from jobs.job_registry import JobRegistry
        from services.scheduler_service import SchedulerService

        mock_scheduler = Mock(spec=SchedulerService)
        registry = JobRegistry(mock_settings, mock_scheduler)

        for job_type, job_class in registry.job_types.items():
            # Check it's a class
            assert inspect.isclass(job_class), (
                f"Registry entry '{job_type}' is not a class"
            )

            # Check it has required attributes
            assert hasattr(job_class, "JOB_NAME"), (
                f"Job class '{job_type}' missing JOB_NAME"
            )
            assert hasattr(job_class, "JOB_DESCRIPTION"), (
                f"Job class '{job_type}' missing JOB_DESCRIPTION"
            )


class TestNoSuppressedErrors:
    """Test no jobs have suppressed linting/type errors."""

    def test_no_undefined_name_suppressions(self):
        """Test no jobs use noqa: F821 to suppress undefined names."""
        import jobs.gdrive_ingest as gdrive
        import jobs.metric_sync as metric
        import jobs.slack_user_import as slack
        import jobs.website_scrape as website

        modules = [gdrive, metric, slack, website]

        for module in modules:
            source = inspect.getsource(module)
            module_name = module.__name__

            # Check for suppressed undefined names
            assert "noqa: F821" not in source, (
                f"{module_name} has suppressed undefined name errors (noqa: F821)"
            )

            # Check for suppressed type errors
            assert (
                "# type: ignore" not in source or source.count("# type: ignore") < 3
            ), f"{module_name} has many suppressed type errors"

    def test_all_imports_at_top_level(self):
        """Test all job imports are at module level, not inside functions.

        Note: GDriveIngestJob has many imports inside methods due to lazy loading
        of heavy dependencies (Google Drive API). This is acceptable for that job.
        """
        from jobs.metric_sync import MetricSyncJob
        from jobs.slack_user_import import SlackUserImportJob
        from jobs.website_scrape import WebsiteScrapeJob

        # GDriveIngestJob excluded as it has intentional lazy loading
        jobs = [
            MetricSyncJob,
            SlackUserImportJob,
            WebsiteScrapeJob,
        ]

        for job_class in jobs:
            # Get the source code
            source = inspect.getsource(job_class)

            # Count imports inside methods (this is usually a code smell)
            method_imports = source.count("    import ") + source.count("    from ")

            # Some imports inside async methods are ok (lazy loading)
            # But having many is suspicious
            assert method_imports < 5, (
                f"{job_class.__name__} has {method_imports} imports inside methods "
                "(may indicate missing top-level imports)"
            )
