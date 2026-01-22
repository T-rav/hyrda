"""Tests for YouTube ingestion retry logic with exponential backoff.

Tests the 5-attempt retry loop with 2s, 4s, 8s, 16s backoff.
"""

import time
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


class TestRetryLogic:
    """Test retry logic with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_on_transcription_failure(self, mock_settings):
        """Test that job retries on transcription failure with exponential backoff."""
        job = YouTubeIngestJob(
            mock_settings,
            channel_url="https://www.youtube.com/@test",
            include_videos=True,
        )

        with (
            patch("os.getenv", return_value="openai-key"),
            patch("time.sleep") as mock_sleep,
            patch("services.youtube.YouTubeClient") as mock_youtube_client_class,
            patch("services.youtube.YouTubeTrackingService"),
            patch("services.openai_embeddings.OpenAIEmbeddings"),
            patch("services.qdrant_client.QdrantClient") as mock_qdrant_class,
        ):
            # Setup YouTube client mock
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

            # Mock transcription to fail 3 times, then succeed on 4th attempt
            mock_youtube_client.get_video_info_with_transcript.side_effect = [
                None,  # Attempt 1: fail
                None,  # Attempt 2: fail
                None,  # Attempt 3: fail
                {  # Attempt 4: success
                    "video_id": "video123",
                    "title": "Test Video",
                    "transcript": "Success!",
                    "video_type": "video",
                    "duration_seconds": 300,
                    "published_at": datetime(2024, 1, 1, tzinfo=UTC),
                    "view_count": 1000,
                },
            ]

            # Setup vector store mock
            mock_qdrant = AsyncMock()
            mock_qdrant_class.return_value = mock_qdrant

            # Mock tracking service
            with patch(
                "services.youtube.YouTubeTrackingService"
            ) as mock_tracking_class:
                mock_tracking = Mock()
                mock_tracking_class.return_value = mock_tracking
                mock_tracking.check_video_needs_reindex.return_value = (True, None)
                mock_tracking.generate_base_uuid.return_value = "uuid-123"

                # Mock embeddings
                with patch(
                    "services.openai_embeddings.OpenAIEmbeddings"
                ) as mock_embeddings_class:
                    mock_embeddings = Mock()
                    mock_embeddings_class.return_value = mock_embeddings
                    mock_embeddings.chunk_text.return_value = ["Chunk 1"]
                    mock_embeddings.embed_texts = AsyncMock(return_value=[[0.1, 0.2]])

                    # Execute job
                    result = await job._execute_job()

                    # Verify retries happened (3 failures, 1 success)
                    assert mock_sleep.call_count == 3  # Sleep before attempts 2, 3, 4

                    # Verify exponential backoff: 2s, 4s, 8s
                    assert mock_sleep.call_args_list[0][0][0] == 2  # 2^1 = 2 seconds
                    assert mock_sleep.call_args_list[1][0][0] == 4  # 2^2 = 4 seconds
                    assert mock_sleep.call_args_list[2][0][0] == 8  # 2^3 = 8 seconds

                    # Verify final result shows success
                    assert result["records_success"] == 1
                    assert result["records_failed"] == 0

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self, mock_settings):
        """Test that job fails after 5 attempts."""
        job = YouTubeIngestJob(
            mock_settings,
            channel_url="https://www.youtube.com/@test",
            include_videos=True,
        )

        with (
            patch("os.getenv", return_value="openai-key"),
            patch("time.sleep") as mock_sleep,
            patch("services.youtube.YouTubeClient") as mock_youtube_client_class,
            patch("services.youtube.YouTubeTrackingService"),
            patch("services.openai_embeddings.OpenAIEmbeddings"),
            patch("services.qdrant_client.QdrantClient") as mock_qdrant_class,
        ):
            # Setup YouTube client mock
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

            # Mock transcription to always fail
            mock_youtube_client.get_video_info_with_transcript.return_value = None

            # Setup vector store mock
            mock_qdrant = AsyncMock()
            mock_qdrant_class.return_value = mock_qdrant

            # Execute job
            result = await job._execute_job()

            # Verify all 5 attempts were made (4 sleeps before attempts 2-5)
            assert mock_sleep.call_count == 4

            # Verify exponential backoff
            assert mock_sleep.call_args_list[0][0][0] == 2  # 2^1
            assert mock_sleep.call_args_list[1][0][0] == 4  # 2^2
            assert mock_sleep.call_args_list[2][0][0] == 8  # 2^3
            assert mock_sleep.call_args_list[3][0][0] == 16  # 2^4

            # Verify result shows failure
            assert result["records_success"] == 0
            assert result["records_failed"] == 1

    @pytest.mark.asyncio
    async def test_first_attempt_success_no_retry(self, mock_settings):
        """Test that successful first attempt doesn't retry."""
        job = YouTubeIngestJob(
            mock_settings,
            channel_url="https://www.youtube.com/@test",
            include_videos=True,
        )

        with (
            patch("os.getenv", return_value="openai-key"),
            patch("time.sleep") as mock_sleep,
            patch("services.youtube.YouTubeClient") as mock_youtube_client_class,
            patch("services.youtube.YouTubeTrackingService") as mock_tracking_class,
            patch("services.openai_embeddings.OpenAIEmbeddings") as mock_embeddings_class,
            patch("services.qdrant_client.QdrantClient") as mock_qdrant_class,
        ):
            # Setup mocks for immediate success
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
            mock_youtube_client.get_video_info_with_transcript.return_value = {
                "video_id": "video123",
                "title": "Test Video",
                "transcript": "Success on first try!",
                "video_type": "video",
                "duration_seconds": 300,
                "published_at": datetime(2024, 1, 1, tzinfo=UTC),
                "view_count": 1000,
            }

            # Setup tracking service
            mock_tracking = Mock()
            mock_tracking_class.return_value = mock_tracking
            mock_tracking.check_video_needs_reindex.return_value = (True, None)
            mock_tracking.generate_base_uuid.return_value = "uuid-123"

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

            # Verify NO retries (sleep never called)
            mock_sleep.assert_not_called()

            # Verify success on first attempt
            assert result["records_success"] == 1
            assert result["records_failed"] == 0

    @pytest.mark.asyncio
    async def test_retry_timing_accuracy(self, mock_settings):
        """Test that retry delays are accurate."""
        job = YouTubeIngestJob(
            mock_settings,
            channel_url="https://www.youtube.com/@test",
            include_videos=True,
        )

        with (
            patch("os.getenv", return_value="openai-key"),
            patch("services.youtube.YouTubeClient") as mock_youtube_client_class,
            patch("services.youtube.YouTubeTrackingService"),
            patch("services.openai_embeddings.OpenAIEmbeddings"),
            patch("services.qdrant_client.QdrantClient") as mock_qdrant_class,
        ):
            # Setup YouTube client to fail multiple times
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
            mock_youtube_client.get_video_info_with_transcript.return_value = None

            # Setup vector store
            mock_qdrant = AsyncMock()
            mock_qdrant_class.return_value = mock_qdrant

            # Track actual sleep times
            sleep_times = []

            def track_sleep(seconds):
                sleep_times.append((time.time(), seconds))

            with patch("time.sleep", side_effect=track_sleep):
                await job._execute_job()

            # Verify sleep times follow exponential backoff
            assert len(sleep_times) == 4
            assert sleep_times[0][1] == 2  # 2^1 = 2 seconds
            assert sleep_times[1][1] == 4  # 2^2 = 4 seconds
            assert sleep_times[2][1] == 8  # 2^3 = 8 seconds
            assert sleep_times[3][1] == 16  # 2^4 = 16 seconds
