"""Tests for YouTube tracking service."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from services.youtube.youtube_tracking_service import (
    YouTubeTrackingService,
    YouTubeVideo,
)


@pytest.fixture
def tracking_service():
    """Create YouTubeTrackingService instance."""
    return YouTubeTrackingService()


class TestYouTubeTrackingServiceHashComputation:
    """Test transcript hash computation."""

    def test_compute_transcript_hash(self, tracking_service):
        """Test transcript hash computation."""
        transcript = "This is a test video transcript."
        hash1 = tracking_service.compute_transcript_hash(transcript)
        hash2 = tracking_service.compute_transcript_hash(transcript)

        # Same transcript should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64 character hex string

    def test_different_transcripts_produce_different_hashes(self, tracking_service):
        """Test that different transcripts produce different hashes."""
        transcript1 = "First video transcript"
        transcript2 = "Second video transcript"

        hash1 = tracking_service.compute_transcript_hash(transcript1)
        hash2 = tracking_service.compute_transcript_hash(transcript2)

        assert hash1 != hash2


class TestYouTubeTrackingServiceUUIDGeneration:
    """Test UUID generation."""

    def test_generate_base_uuid(self, tracking_service):
        """Test UUID generation from video ID."""
        video_id = "dQw4w9WgXcQ"
        uuid1 = tracking_service.generate_base_uuid(video_id)
        uuid2 = tracking_service.generate_base_uuid(video_id)

        # Same video ID should produce same UUID (deterministic)
        assert uuid1 == uuid2
        assert len(uuid1) == 36  # UUID format with dashes
        assert uuid1.count("-") == 4

    def test_different_video_ids_produce_different_uuids(self, tracking_service):
        """Test that different video IDs produce different UUIDs."""
        uuid1 = tracking_service.generate_base_uuid("video1")
        uuid2 = tracking_service.generate_base_uuid("video2")

        assert uuid1 != uuid2


class TestYouTubeTrackingServiceReindexCheck:
    """Test video reindex checking."""

    def test_check_new_video_needs_reindex(self, tracking_service):
        """Test checking a new video that doesn't exist in database."""
        with patch("services.youtube.youtube_tracking_service.get_data_db_session"):
            with patch(
                "services.youtube.youtube_tracking_service.get_data_db_session"
            ) as mock_session:
                mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = (
                    None
                )

                needs_reindex, existing_uuid = (
                    tracking_service.check_video_needs_reindex(
                        "new_video_id", "New transcript"
                    )
                )

                assert needs_reindex is True
                assert existing_uuid is None

    def test_check_unchanged_video_skips_reindex(self, tracking_service):
        """Test that unchanged video is skipped."""
        transcript = "Unchanged transcript"
        transcript_hash = tracking_service.compute_transcript_hash(transcript)

        mock_video = Mock(spec=YouTubeVideo)
        mock_video.transcript_hash = transcript_hash
        mock_video.vector_uuid = "existing-uuid-123"

        with patch(
            "services.youtube.youtube_tracking_service.get_data_db_session"
        ) as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = (
                mock_video
            )

            needs_reindex, existing_uuid = tracking_service.check_video_needs_reindex(
                "existing_video_id", transcript
            )

            assert needs_reindex is False
            assert existing_uuid == "existing-uuid-123"

    def test_check_changed_video_needs_reindex(self, tracking_service):
        """Test that changed video needs reindexing."""
        old_transcript = "Old transcript"
        new_transcript = "New updated transcript"

        old_hash = tracking_service.compute_transcript_hash(old_transcript)

        mock_video = Mock(spec=YouTubeVideo)
        mock_video.transcript_hash = old_hash
        mock_video.vector_uuid = "existing-uuid-123"

        with patch(
            "services.youtube.youtube_tracking_service.get_data_db_session"
        ) as mock_session:
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = (
                mock_video
            )

            needs_reindex, existing_uuid = tracking_service.check_video_needs_reindex(
                "existing_video_id", new_transcript
            )

            assert needs_reindex is True
            assert existing_uuid == "existing-uuid-123"


class TestYouTubeTrackingServiceRecordIngestion:
    """Test recording video ingestion."""

    def test_record_new_video_ingestion(self, tracking_service):
        """Test recording a new video ingestion."""
        with patch(
            "services.youtube.youtube_tracking_service.get_data_db_session"
        ) as mock_session:
            mock_db = mock_session.return_value.__enter__.return_value
            mock_db.query.return_value.filter.return_value.first.return_value = None

            tracking_service.record_video_ingestion(
                youtube_video_id="test_video_123",
                video_title="Test Video",
                channel_id="channel_123",
                channel_name="Test Channel",
                video_type="video",
                transcript="Test transcript",
                vector_uuid="uuid-123",
                chunk_count=5,
                duration_seconds=300,
                view_count=1000,
            )

            # Verify session operations
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    def test_record_updated_video_ingestion(self, tracking_service):
        """Test updating an existing video record."""
        mock_video = Mock(spec=YouTubeVideo)

        with patch(
            "services.youtube.youtube_tracking_service.get_data_db_session"
        ) as mock_session:
            mock_db = mock_session.return_value.__enter__.return_value
            mock_db.query.return_value.filter.return_value.first.return_value = (
                mock_video
            )

            tracking_service.record_video_ingestion(
                youtube_video_id="existing_video_123",
                video_title="Updated Video Title",
                channel_id="channel_123",
                channel_name="Test Channel",
                video_type="video",
                transcript="Updated transcript",
                vector_uuid="uuid-123",
                chunk_count=7,
                duration_seconds=350,
                view_count=2000,
            )

            # Verify video was updated, not added
            mock_db.add.assert_not_called()
            mock_db.commit.assert_called_once()

            # Verify fields were updated
            assert mock_video.video_title == "Updated Video Title"
            assert mock_video.chunk_count == 7


class TestYouTubeTrackingServiceGetVideoInfo:
    """Test retrieving video information."""

    def test_get_video_info_existing(self, tracking_service):
        """Test retrieving info for existing video."""
        mock_video = Mock(spec=YouTubeVideo)
        mock_video.youtube_video_id = "test_123"
        mock_video.video_title = "Test Video"
        mock_video.channel_id = "channel_123"
        mock_video.channel_name = "Test Channel"
        mock_video.video_type = "video"
        mock_video.transcript_hash = "hash123"
        mock_video.vector_uuid = "uuid-123"
        mock_video.chunk_count = 5
        mock_video.duration_seconds = 300
        mock_video.published_at = datetime(2024, 1, 1)
        mock_video.view_count = 1000
        mock_video.transcript_language = "en"
        mock_video.first_ingested_at = datetime(2024, 1, 1)
        mock_video.last_ingested_at = datetime(2024, 1, 2)
        mock_video.ingestion_status = "success"
        mock_video.extra_metadata = {"key": "value"}

        with patch(
            "services.youtube.youtube_tracking_service.get_data_db_session"
        ) as mock_session:
            mock_db = mock_session.return_value.__enter__.return_value
            mock_db.query.return_value.filter.return_value.first.return_value = (
                mock_video
            )

            info = tracking_service.get_video_info("test_123")

            assert info is not None
            assert info["youtube_video_id"] == "test_123"
            assert info["video_title"] == "Test Video"
            assert info["channel_name"] == "Test Channel"
            assert info["chunk_count"] == 5

    def test_get_video_info_not_found(self, tracking_service):
        """Test retrieving info for non-existent video."""
        with patch(
            "services.youtube.youtube_tracking_service.get_data_db_session"
        ) as mock_session:
            mock_db = mock_session.return_value.__enter__.return_value
            mock_db.query.return_value.filter.return_value.first.return_value = None

            info = tracking_service.get_video_info("nonexistent_video")

            assert info is None
