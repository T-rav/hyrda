"""Tests for YouTube channel ingestion job.

These tests focus on validation logic and parameter handling.
Integration tests with actual yt-dlp/database/services would require complex test infrastructure.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from config.settings import TasksSettings
from jobs.youtube_ingest import YouTubeIngestJob


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Mock(spec=TasksSettings)
    settings.tasks_port = 5001
    settings.tasks_host = "localhost"
    return settings


class TestYouTubeIngestJobValidation:
    """Test job parameter validation."""

    def test_job_name_and_description(self, mock_settings):
        """Test job has proper name and description."""
        job = YouTubeIngestJob(
            mock_settings, channel_url="https://www.youtube.com/@8thLightInc"
        )
        assert job.JOB_NAME == "YouTube Channel Ingestion"
        assert "yt-dlp" in job.JOB_DESCRIPTION.lower()
        assert "whisper" in job.JOB_DESCRIPTION.lower()

    def test_requires_channel_url(self, mock_settings):
        """Test job requires channel_url parameter."""
        with pytest.raises(ValueError, match="Required parameter missing: channel_url"):
            YouTubeIngestJob(mock_settings)

    def test_accepts_channel_url(self, mock_settings):
        """Test job accepts channel_url parameter."""
        job = YouTubeIngestJob(
            mock_settings, channel_url="https://www.youtube.com/@8thLightInc"
        )
        assert job.params["channel_url"] == "https://www.youtube.com/@8thLightInc"

    def test_optional_parameters(self, mock_settings):
        """Test job accepts optional parameters."""
        job = YouTubeIngestJob(
            mock_settings,
            channel_url="https://www.youtube.com/@test",
            include_videos=True,
            include_shorts=False,
            include_podcasts=True,
            max_videos=10,
            metadata={"department": "engineering"},
        )
        assert job.params["include_videos"] is True
        assert job.params["include_shorts"] is False
        assert job.params["include_podcasts"] is True
        assert job.params["max_videos"] == 10
        assert job.params["metadata"] == {"department": "engineering"}

    def test_default_video_type_params(self, mock_settings):
        """Test default video type parameters."""
        job = YouTubeIngestJob(
            mock_settings, channel_url="https://www.youtube.com/@test"
        )
        # Default: include videos, exclude shorts and podcasts
        assert job.params.get("include_videos", True) is True
        assert job.params.get("include_shorts", False) is False
        assert job.params.get("include_podcasts", False) is False

    def test_requires_at_least_one_video_type(self, mock_settings):
        """Test job requires at least one video type to be selected."""
        with pytest.raises(
            ValueError,
            match="Must include at least one video type \\(videos, shorts, or podcasts\\)",
        ):
            YouTubeIngestJob(
                mock_settings,
                channel_url="https://www.youtube.com/@test",
                include_videos=False,
                include_shorts=False,
                include_podcasts=False,
            )

    def test_accepts_all_video_types(self, mock_settings):
        """Test job accepts all video types enabled."""
        job = YouTubeIngestJob(
            mock_settings,
            channel_url="https://www.youtube.com/@test",
            include_videos=True,
            include_shorts=True,
            include_podcasts=True,
        )
        assert job.params["include_videos"] is True
        assert job.params["include_shorts"] is True
        assert job.params["include_podcasts"] is True


class TestYouTubeIngestJobExecution:
    """Test job execution logic - basic tests only."""

    @pytest.mark.asyncio
    async def test_requires_openai_api_key_env(self, mock_settings):
        """Test job fails without OpenAI API key (only key required!)."""
        job = YouTubeIngestJob(
            mock_settings, channel_url="https://www.youtube.com/@test"
        )

        with patch("os.getenv") as mock_getenv:
            mock_getenv.return_value = None
            with pytest.raises(
                ValueError, match="OPENAI_API_KEY environment variable is required"
            ):
                await job._execute_job()

    @pytest.mark.asyncio
    async def test_successful_execution_with_videos(self, mock_settings):
        """Test successful job execution with video processing."""
        job = YouTubeIngestJob(
            mock_settings,
            channel_url="https://www.youtube.com/@test",
            include_videos=True,
            include_shorts=False,
            include_podcasts=False,
        )

        # Mock all services
        with patch("os.getenv") as mock_getenv:
            mock_getenv.return_value = "openai-key"  # Only need OpenAI key!

            with (
                patch("services.youtube.YouTubeClient") as mock_youtube_client_class,
                patch(
                    "services.youtube.YouTubeTrackingService"
                ) as mock_tracking_service_class,
                patch(
                    "services.openai_embeddings.OpenAIEmbeddings"
                ) as mock_embeddings_class,
                patch("services.qdrant_client.QdrantClient") as mock_qdrant_class,
            ):
                # Setup YouTube client mock
                mock_youtube_client = Mock()
                mock_youtube_client_class.return_value = mock_youtube_client

                # Mock channel info
                mock_youtube_client.get_channel_info.return_value = {
                    "channel_id": "UC_test_channel",
                    "channel_name": "Test Channel",
                    "channel_url": "https://www.youtube.com/@test",
                }

                # Mock video list
                mock_youtube_client.list_channel_videos.return_value = [
                    {
                        "video_id": "video123",
                        "title": "Test Video",
                        "url": "https://www.youtube.com/watch?v=video123",
                    }
                ]

                # Mock video with transcript
                mock_youtube_client.get_video_info_with_transcript.return_value = {
                    "video_id": "video123",
                    "title": "Test Video",
                    "transcript": "This is a test transcript",
                    "video_type": "video",
                    "duration_seconds": 300,
                    "published_at": datetime(2024, 1, 1, tzinfo=UTC),
                    "view_count": 1000,
                }

                # Setup tracking service mock
                mock_tracking_service = Mock()
                mock_tracking_service_class.return_value = mock_tracking_service
                mock_tracking_service.check_video_needs_reindex.return_value = (
                    True,
                    None,
                )
                mock_tracking_service.generate_base_uuid.return_value = "uuid-123"

                # Setup embeddings mock (mixed sync/async methods)
                mock_embeddings = Mock()
                mock_embeddings_class.return_value = mock_embeddings
                # chunk_text is synchronous
                mock_embeddings.chunk_text.return_value = ["Chunk 1", "Chunk 2"]
                # embed_texts is async
                mock_embeddings.embed_texts = AsyncMock(
                    return_value=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
                )

                # Setup vector store mock
                mock_qdrant = AsyncMock()
                mock_qdrant_class.return_value = mock_qdrant
                # Mock the async methods
                mock_qdrant.initialize.return_value = None
                mock_qdrant.upsert_with_namespace.return_value = None

                # Execute job
                result = await job._execute_job()

                # Verify result structure
                assert result["records_processed"] == 1
                assert result["records_success"] == 1
                assert result["records_failed"] == 0
                assert result["records_skipped"] == 0
                assert result["channel_url"] == "https://www.youtube.com/@test"
                assert result["channel_name"] == "Test Channel"
                assert result["channel_id"] == "UC_test_channel"

                # Verify vector store was called
                mock_qdrant.upsert_with_namespace.assert_called_once()

                # Verify tracking service was called
                mock_tracking_service.record_video_ingestion.assert_called_once()

                # Verify YouTubeClient was initialized with ONLY OpenAI key
                mock_youtube_client_class.assert_called_once_with(
                    openai_api_key="openai-key"
                )

    @pytest.mark.asyncio
    async def test_skips_unchanged_videos(self, mock_settings):
        """Test job skips videos that haven't changed."""
        job = YouTubeIngestJob(
            mock_settings,
            channel_url="https://www.youtube.com/@test",
            include_videos=True,
        )

        # Mock all services
        with patch("os.getenv") as mock_getenv:
            mock_getenv.return_value = "openai-key"

            with (
                patch("services.youtube.YouTubeClient") as mock_youtube_client_class,
                patch(
                    "services.youtube.YouTubeTrackingService"
                ) as mock_tracking_service_class,
                patch("services.openai_embeddings.OpenAIEmbeddings"),
                patch("services.qdrant_client.QdrantClient") as mock_qdrant_class,
            ):
                # Setup YouTube client mock
                mock_youtube_client = Mock()
                mock_youtube_client_class.return_value = mock_youtube_client
                mock_youtube_client.get_channel_info.return_value = {
                    "channel_id": "UC_test_channel",
                    "channel_name": "Test Channel",
                    "channel_url": "https://www.youtube.com/@test",
                }
                mock_youtube_client.list_channel_videos.return_value = [
                    {"video_id": "video123", "title": "Test Video"}
                ]
                mock_youtube_client.get_video_info_with_transcript.return_value = {
                    "video_id": "video123",
                    "title": "Test Video",
                    "transcript": "Transcript",
                    "video_type": "video",
                    "duration_seconds": 300,
                    "published_at": datetime(2024, 1, 1, tzinfo=UTC),
                    "view_count": 1000,
                }

                # Setup tracking service mock - video unchanged
                mock_tracking_service = Mock()
                mock_tracking_service_class.return_value = mock_tracking_service
                mock_tracking_service.check_video_needs_reindex.return_value = (
                    False,
                    "existing-uuid",
                )

                # Setup vector store mock
                mock_qdrant = AsyncMock()
                mock_qdrant_class.return_value = mock_qdrant
                # Mock the async methods
                mock_qdrant.initialize.return_value = None
                mock_qdrant.upsert_with_namespace.return_value = None

                # Execute job
                result = await job._execute_job()

                # Verify result - should skip video
                assert result["records_processed"] == 1
                assert result["records_success"] == 0
                assert result["records_skipped"] == 1

                # Verify vector store was NOT called
                mock_qdrant.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_transcription_failures(self, mock_settings):
        """Test job handles videos with transcription failures."""
        job = YouTubeIngestJob(
            mock_settings,
            channel_url="https://www.youtube.com/@test",
            include_videos=True,
        )

        # Mock all services
        with patch("os.getenv") as mock_getenv:
            mock_getenv.return_value = "openai-key"

            with (
                patch("services.youtube.YouTubeClient") as mock_youtube_client_class,
                patch("services.youtube.YouTubeTrackingService"),
                patch("services.openai_embeddings.OpenAIEmbeddings"),
                patch("services.qdrant_client.QdrantClient") as mock_qdrant_class,
            ):
                # Setup YouTube client mock
                mock_youtube_client = Mock()
                mock_youtube_client_class.return_value = mock_youtube_client
                mock_youtube_client.get_channel_info.return_value = {
                    "channel_id": "UC_test_channel",
                    "channel_name": "Test Channel",
                    "channel_url": "https://www.youtube.com/@test",
                }
                mock_youtube_client.list_channel_videos.return_value = [
                    {"video_id": "video123", "title": "Test Video"}
                ]

                # Mock transcription failure - returns None
                mock_youtube_client.get_video_info_with_transcript.return_value = None

                # Setup vector store mock
                mock_qdrant = AsyncMock()
                mock_qdrant_class.return_value = mock_qdrant
                # Mock the async methods
                mock_qdrant.initialize.return_value = None
                mock_qdrant.upsert_with_namespace.return_value = None

                # Execute job
                result = await job._execute_job()

                # Verify result - should count as error
                assert result["records_processed"] == 1
                assert result["records_success"] == 0
                assert result["records_failed"] == 1

                # Verify vector store was NOT called
                mock_qdrant.upsert.assert_not_called()

    def test_job_has_required_attributes(self, mock_settings):
        """Test job has all required attributes."""
        job = YouTubeIngestJob(
            mock_settings, channel_url="https://www.youtube.com/@test"
        )

        assert hasattr(job, "JOB_NAME")
        assert hasattr(job, "JOB_DESCRIPTION")
        assert hasattr(job, "REQUIRED_PARAMS")
        assert hasattr(job, "OPTIONAL_PARAMS")
        assert hasattr(job, "params")

    def test_job_stores_parameters(self, mock_settings):
        """Test job properly stores all parameters."""
        job = YouTubeIngestJob(
            mock_settings,
            channel_url="https://www.youtube.com/@test",
            include_videos=True,
            include_shorts=True,
            max_videos=50,
            metadata={"key": "value"},
        )

        assert job.params["channel_url"] == "https://www.youtube.com/@test"
        assert job.params["include_videos"] is True
        assert job.params["include_shorts"] is True
        assert job.params["max_videos"] == 50
        assert job.params["metadata"] == {"key": "value"}
