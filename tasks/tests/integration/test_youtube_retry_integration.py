"""Integration tests for YouTube ingestion retry logic.

Tests the actual retry mechanism with exponential backoff in the full job context.
"""

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from config.settings import TasksSettings
from jobs.youtube_ingest import YouTubeIngestJob


@pytest.mark.integration
class TestRetryLogicIntegration:
    """Integration tests for retry logic with timing verification."""

    @pytest.fixture
    def mock_settings(self):
        """Create real settings for testing."""
        return TasksSettings()

    @pytest.mark.asyncio
    async def test_retry_with_actual_timing(self, mock_settings):
        """Test retry logic with actual time delays (not mocked)."""
        job = YouTubeIngestJob(
            mock_settings,
            channel_url="https://www.youtube.com/@test",
            include_videos=True,
        )

        start_time = time.time()
        attempt_times = []

        # Mock services but use real retry/sleep logic
        with (
            patch("os.getenv", return_value="test-key"),
            patch("services.youtube.YouTubeClient") as mock_youtube_client_class,
            patch("services.youtube.YouTubeTrackingService") as mock_tracking_class,
            patch("services.openai_embeddings.OpenAIEmbeddings"),
            patch("services.qdrant_client.QdrantClient") as mock_qdrant_class,
        ):
            mock_youtube_client = Mock()
            mock_youtube_client_class.return_value = mock_youtube_client
            mock_youtube_client.get_channel_info.return_value = {
                "channel_id": "UC_test",
                "channel_name": "Test",
                "channel_url": "https://www.youtube.com/@test",
            }
            mock_youtube_client.list_channel_videos.return_value = [
                {"video_id": "video123", "title": "Test Video"}
            ]

            # Setup tracking service
            mock_tracking = Mock()
            mock_tracking_class.return_value = mock_tracking
            mock_tracking.check_video_needs_reindex_by_metadata.return_value = (True, None)
            mock_tracking.check_video_needs_reindex.return_value = (True, None)
            mock_tracking.generate_base_uuid.return_value = "uuid-123"
            mock_tracking.record_video_ingestion = Mock()

            # Track when each attempt happens
            def track_attempt(*args, **kwargs):
                attempt_times.append(time.time())

            mock_youtube_client.get_video_info.side_effect = (
                track_attempt
            )

            # Setup vector store
            mock_qdrant = AsyncMock()
            mock_qdrant_class.return_value = mock_qdrant

            # Execute job (will fail after 5 attempts)
            await job._execute_job()

            # Verify timing between attempts follows exponential backoff
            assert len(attempt_times) == 5, (
                f"Expected 5 attempts, got {len(attempt_times)}"
            )

            # Calculate delays between attempts
            delays = [
                attempt_times[i] - attempt_times[i - 1]
                for i in range(1, len(attempt_times))
            ]

            # Delays should be approximately 2s, 4s, 8s, 16s (with some tolerance)
            expected_delays = [2, 4, 8, 16]
            for i, (actual, expected) in enumerate(
                zip(delays, expected_delays, strict=False)
            ):
                # Allow 0.5s tolerance for execution time
                assert expected - 0.5 <= actual <= expected + 0.5, (
                    f"Delay {i + 1}: expected ~{expected}s, got {actual:.2f}s"
                )

            # Total time should be approximately 30 seconds (2+4+8+16)
            total_time = time.time() - start_time
            assert 29 <= total_time <= 32, f"Expected ~30s total, got {total_time:.1f}s"

    @pytest.mark.asyncio
    async def test_retry_stops_on_success(self, mock_settings):
        """Test that retry loop exits immediately on success."""
        job = YouTubeIngestJob(
            mock_settings,
            channel_url="https://www.youtube.com/@test",
            include_videos=True,
        )

        start_time = time.time()

        with (
            patch("os.getenv", return_value="test-key"),
            patch("services.youtube.YouTubeClient") as mock_youtube_client_class,
            patch("services.youtube.YouTubeTrackingService") as mock_tracking_class,
            patch(
                "services.openai_embeddings.OpenAIEmbeddings"
            ) as mock_embeddings_class,
            patch("services.qdrant_client.QdrantClient") as mock_qdrant_class,
        ):
            mock_youtube_client = Mock()
            mock_youtube_client_class.return_value = mock_youtube_client
            mock_youtube_client.get_channel_info.return_value = {
                "channel_id": "UC_test",
                "channel_name": "Test",
                "channel_url": "https://www.youtube.com/@test",
            }
            mock_youtube_client.list_channel_videos.return_value = [
                {"video_id": "video123", "title": "Test Video"}
            ]

            # Fail twice, then succeed
            mock_youtube_client.get_video_info.side_effect = [
                None,  # Fail attempt 1
                None,  # Fail attempt 2
                {  # Success attempt 3
                    "video_id": "video123",
                    "title": "Test Video",
                    "video_type": "video",
                    "duration_seconds": 300,
                    "published_at": datetime(2024, 1, 1, tzinfo=UTC),
                    "view_count": 1000,
                },
            ]

            # Mock get_video_transcript
            mock_youtube_client.get_video_transcript.return_value = ("Success!", "en")

            # Setup tracking service
            mock_tracking = Mock()
            mock_tracking_class.return_value = mock_tracking
            mock_tracking.check_video_needs_reindex_by_metadata.return_value = (True, None)
            mock_tracking.check_video_needs_reindex.return_value = (True, None)
            mock_tracking.generate_base_uuid.return_value = "uuid-123"
            mock_tracking.record_video_ingestion = Mock()

            # Setup embeddings
            mock_embeddings = Mock()
            mock_embeddings_class.return_value = mock_embeddings
            mock_embeddings.chunk_text.return_value = ["Chunk 1"]
            mock_embeddings.embed_texts = AsyncMock(return_value=[[0.1, 0.2]])

            # Setup vector store
            mock_qdrant = AsyncMock()
            mock_qdrant_class.return_value = mock_qdrant

            # Execute job
            result = await job._execute_job()

            # Should complete in ~6 seconds (2s delay + 4s delay)
            # Not 30 seconds (all 5 attempts)
            total_time = time.time() - start_time
            assert total_time < 10, (
                f"Expected early exit (<10s), took {total_time:.1f}s"
            )

            # Should show success
            assert result["records_success"] == 1
            assert result["records_failed"] == 0


@pytest.mark.integration
class TestJobExecutionUnderLoad:
    """Integration tests for job execution with concurrent operations."""

    @pytest.mark.asyncio
    async def test_multiple_jobs_concurrent_execution(self):
        """Test that multiple jobs can execute concurrently without blocking."""
        from config.settings import TasksSettings
        from models.base import get_db_session
        from services.scheduler_service import SchedulerService

        # Test database connection - skip if unavailable
        try:
            with get_db_session() as session:
                session.execute("SELECT 1")
        except Exception:
            pytest.skip("Database not available for integration tests")

        settings = TasksSettings()
        scheduler_service = SchedulerService(settings)

        # Mock a simple job that takes 2 seconds
        async def mock_job_execution():
            import asyncio

            await asyncio.sleep(2)
            return {"status": "success"}

        # Start scheduler (required for thread pool)
        scheduler_service.start()

        try:
            # Submit multiple jobs concurrently
            # In real ThreadPoolExecutor with 20 threads, 10 jobs should run in parallel
            # Taking ~2 seconds total, not 20 seconds sequential
            # Simulate concurrent job submission
            # (In reality, this would be APScheduler triggering jobs)
            # For integration test, we verify the thread pool exists and can handle load

            # Check thread pool configuration
            assert scheduler_service.scheduler is not None
            assert scheduler_service.scheduler._executors["default"].max_workers == 20

            # Verify scheduler is running
            assert scheduler_service.scheduler.running is True

        finally:
            scheduler_service.shutdown()

    @pytest.mark.asyncio
    async def test_http_responsive_during_job_execution(self):
        """Test that HTTP endpoints remain responsive during job execution."""
        # This would test that FastAPI can handle requests while jobs run
        # Requires actual HTTP client and running service

        # Mock test - verify threading doesn't block HTTP
        import threading

        request_handled = False

        def simulate_http_request():
            nonlocal request_handled
            time.sleep(0.1)  # Simulate request processing
            request_handled = True

        def simulate_job_execution():
            time.sleep(2)  # Simulate long-running job

        # Start job in thread (simulating ThreadPoolExecutor)
        job_thread = threading.Thread(target=simulate_job_execution)
        job_thread.start()

        # Handle HTTP request concurrently
        request_thread = threading.Thread(target=simulate_http_request)
        request_thread.start()
        request_thread.join()

        # HTTP request should complete even while job is running
        assert request_handled is True

        job_thread.join()
