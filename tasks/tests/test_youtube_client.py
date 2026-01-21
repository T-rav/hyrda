"""Tests for YouTube client (yt-dlp based)."""

import json
from unittest.mock import Mock, patch

import pytest

from services.youtube.youtube_client import YouTubeClient


@pytest.fixture
def mock_openai_key():
    """Mock OpenAI API key."""
    with patch("os.getenv", return_value="test-openai-key"):
        yield


@pytest.fixture
def youtube_client(mock_openai_key):
    """Create YouTubeClient instance."""
    return YouTubeClient(openai_api_key="test-openai-key")


class TestYouTubeClientInitialization:
    """Test YouTubeClient initialization."""

    def test_requires_openai_key(self):
        """Test that OpenAI API key is required."""
        with (
            patch("os.getenv", return_value=None),
            pytest.raises(ValueError, match="OpenAI API key is required"),
        ):
            YouTubeClient()

    def test_accepts_openai_key_param(self):
        """Test initialization with explicit API key."""
        client = YouTubeClient(openai_api_key="test-key")
        assert client.openai_api_key == "test-key"

    def test_reads_openai_key_from_env(self):
        """Test reading API key from environment."""
        with patch("os.getenv", return_value="env-key"):
            client = YouTubeClient()
            assert client.openai_api_key == "env-key"


class TestYouTubeClientGetChannelInfo:
    """Test channel info retrieval."""

    def test_get_channel_info_success(self, youtube_client):
        """Test successful channel info retrieval."""
        mock_output = json.dumps(
            {
                "channel_id": "UC123",
                "channel": "Test Channel",
                "channel_url": "https://youtube.com/@test",
            }
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout=mock_output + "\n")

            result = youtube_client.get_channel_info("https://youtube.com/@test")

            assert result["channel_id"] == "UC123"
            assert result["channel_name"] == "Test Channel"
            assert result["channel_url"] == "https://youtube.com/@test"

            # Verify yt-dlp command
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "yt-dlp"
            assert "--dump-json" in args
            assert "--playlist-items" in args

    def test_get_channel_info_handles_errors(self, youtube_client):
        """Test error handling for channel info."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("yt-dlp error")

            result = youtube_client.get_channel_info("https://youtube.com/@test")

            assert result is None


class TestYouTubeClientListChannelVideos:
    """Test channel video listing."""

    def test_list_channel_videos_success(self, youtube_client):
        """Test successful video listing."""
        mock_output = "\n".join(
            [
                json.dumps({"id": "video1", "title": "Video 1", "url": "url1"}),
                json.dumps({"id": "video2", "title": "Video 2", "url": "url2"}),
            ]
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout=mock_output + "\n")

            result = youtube_client.list_channel_videos(
                "https://youtube.com/@test", max_results=10
            )

            assert len(result) == 2
            assert result[0]["video_id"] == "video1"
            assert result[0]["title"] == "Video 1"
            assert result[1]["video_id"] == "video2"

            # Verify yt-dlp command
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "yt-dlp"
            assert "--flat-playlist" in args
            assert "--playlist-end" in args
            assert "10" in args

    def test_list_channel_videos_filters_by_type(self, youtube_client):
        """Test video type filtering."""
        mock_list_output = json.dumps(
            {"id": "video1", "title": "Video 1", "url": "url1"}
        )
        mock_info_output = json.dumps(
            {
                "id": "video1",
                "title": "Video 1",
                "duration": 45,  # Short video
                "channel_id": "UC123",
                "channel": "Test",
                "upload_date": "20240101",
                "view_count": 1000,
                "like_count": 100,
                "comment_count": 10,
                "thumbnail": "thumb.jpg",
            }
        )

        with patch("subprocess.run") as mock_run:
            # First call: list videos, second call: get video info
            mock_run.side_effect = [
                Mock(stdout=mock_list_output + "\n"),
                Mock(stdout=mock_info_output),
            ]

            result = youtube_client.list_channel_videos(
                "https://youtube.com/@test",
                include_videos=False,
                include_shorts=True,
                include_podcasts=False,
            )

            # Should include the short video
            assert len(result) == 1

    def test_list_channel_videos_handles_errors(self, youtube_client):
        """Test error handling for video listing."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("yt-dlp error")

            result = youtube_client.list_channel_videos("https://youtube.com/@test")

            assert result == []


class TestYouTubeClientGetVideoInfo:
    """Test video info retrieval."""

    def test_get_video_info_success(self, youtube_client):
        """Test successful video info retrieval."""
        mock_output = json.dumps(
            {
                "id": "video123",
                "title": "Test Video",
                "description": "Test description",
                "channel_id": "UC123",
                "channel": "Test Channel",
                "upload_date": "20240115",
                "duration": 1800,
                "view_count": 5000,
                "like_count": 500,
                "comment_count": 50,
                "thumbnail": "thumb.jpg",
            }
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout=mock_output)

            result = youtube_client.get_video_info("video123")

            assert result["video_id"] == "video123"
            assert result["title"] == "Test Video"
            assert result["channel_name"] == "Test Channel"
            assert result["duration_seconds"] == 1800
            assert result["video_type"] == "video"
            assert result["published_at"] is not None

            # Verify yt-dlp command
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "yt-dlp"
            assert "--dump-json" in args
            assert "--no-download" in args

    def test_get_video_info_classifies_short(self, youtube_client):
        """Test short video classification."""
        mock_output = json.dumps(
            {
                "id": "short123",
                "title": "Short Video",
                "duration": 45,  # Under 60 seconds
                "channel_id": "UC123",
                "channel": "Test",
                "upload_date": "20240101",
                "view_count": 1000,
                "like_count": 100,
                "comment_count": 10,
                "thumbnail": "thumb.jpg",
            }
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout=mock_output)

            result = youtube_client.get_video_info("short123")

            assert result["video_type"] == "short"

    def test_get_video_info_classifies_podcast(self, youtube_client):
        """Test podcast video classification."""
        mock_output = json.dumps(
            {
                "id": "podcast123",
                "title": "Podcast Episode 1",
                "description": "This is a podcast interview",
                "duration": 3600,
                "channel_id": "UC123",
                "channel": "Test",
                "upload_date": "20240101",
                "view_count": 1000,
                "like_count": 100,
                "comment_count": 10,
                "thumbnail": "thumb.jpg",
            }
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout=mock_output)

            result = youtube_client.get_video_info("podcast123")

            assert result["video_type"] == "podcast"

    def test_get_video_info_handles_errors(self, youtube_client):
        """Test error handling for video info."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("yt-dlp error")

            result = youtube_client.get_video_info("video123")

            assert result is None


class TestYouTubeClientDownloadAudio:
    """Test audio download."""

    def test_download_audio_success(self, youtube_client):
        """Test successful audio download."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="Destination: /tmp/video123.m4a\n")

            result = youtube_client.download_audio(
                "https://youtube.com/watch?v=video123", output_path="/tmp"
            )

            assert result == "/tmp/video123.m4a"

            # Verify yt-dlp command
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "yt-dlp"
            assert "-x" in args
            assert "--audio-format" in args
            assert "m4a" in args

    def test_download_audio_fallback_to_listdir(self, youtube_client):
        """Test fallback to listdir when regex fails."""
        with (
            patch("subprocess.run") as mock_run,
            patch("os.listdir") as mock_listdir,
        ):
            mock_run.return_value = Mock(stdout="Some output without Destination")
            mock_listdir.return_value = ["video123.m4a"]

            result = youtube_client.download_audio(
                "https://youtube.com/watch?v=video123", output_path="/tmp"
            )

            assert result == "/tmp/video123.m4a"

    def test_download_audio_handles_errors(self, youtube_client):
        """Test error handling for audio download."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("yt-dlp error")

            result = youtube_client.download_audio(
                "https://youtube.com/watch?v=video123"
            )

            assert result is None


class TestYouTubeClientTranscribeAudio:
    """Test audio transcription."""

    def test_transcribe_audio_success(self, youtube_client):
        """Test successful audio transcription."""
        with patch("builtins.open"), patch("openai.OpenAI") as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            mock_client.audio.transcriptions.create.return_value = (
                "This is the transcribed text"
            )

            result = youtube_client.transcribe_audio("/tmp/audio.m4a")

            assert result == "This is the transcribed text"
            mock_client.audio.transcriptions.create.assert_called_once()

    def test_transcribe_audio_handles_empty_result(self, youtube_client):
        """Test handling of empty transcription."""
        with patch("builtins.open"), patch("openai.OpenAI") as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            mock_client.audio.transcriptions.create.return_value = "   "

            result = youtube_client.transcribe_audio("/tmp/audio.m4a")

            assert result is None

    def test_transcribe_audio_handles_errors(self, youtube_client):
        """Test error handling for transcription."""
        with patch("builtins.open"), patch("openai.OpenAI") as mock_openai:
            mock_openai.side_effect = Exception("API error")

            result = youtube_client.transcribe_audio("/tmp/audio.m4a")

            assert result is None


class TestYouTubeClientGetVideoTranscript:
    """Test video transcript retrieval (download + transcribe)."""

    def test_get_video_transcript_success(self, youtube_client):
        """Test successful transcript retrieval."""
        with (
            patch.object(
                youtube_client, "download_audio", return_value="/tmp/audio.m4a"
            ),
            patch.object(
                youtube_client, "transcribe_audio", return_value="Transcribed text"
            ),
            patch("os.path.exists", return_value=True),
            patch("os.unlink"),
            patch("os.listdir", return_value=[]),
            patch("os.rmdir"),
        ):
            transcript, language = youtube_client.get_video_transcript("video123")

            assert transcript == "Transcribed text"
            assert language == "en"

    def test_get_video_transcript_handles_download_failure(self, youtube_client):
        """Test handling of download failure."""
        with patch.object(youtube_client, "download_audio", return_value=None):
            transcript, language = youtube_client.get_video_transcript("video123")

            assert transcript is None
            assert language is None

    def test_get_video_transcript_handles_transcription_failure(self, youtube_client):
        """Test handling of transcription failure."""
        with (
            patch.object(
                youtube_client, "download_audio", return_value="/tmp/audio.m4a"
            ),
            patch.object(youtube_client, "transcribe_audio", return_value=None),
            patch("os.path.exists", return_value=True),
            patch("os.unlink"),
        ):
            transcript, language = youtube_client.get_video_transcript("video123")

            assert transcript is None
            assert language is None

    def test_get_video_transcript_cleanup(self, youtube_client):
        """Test audio file cleanup after transcription."""
        with (
            patch.object(
                youtube_client, "download_audio", return_value="/tmp/audio.m4a"
            ),
            patch.object(
                youtube_client, "transcribe_audio", return_value="Transcribed text"
            ),
            patch("os.path.exists", return_value=True),
            patch("os.unlink") as mock_unlink,
            patch("os.listdir", return_value=[]),
            patch("os.rmdir") as mock_rmdir,
        ):
            youtube_client.get_video_transcript("video123", cleanup=True)

            # Verify cleanup was called
            mock_unlink.assert_called_once_with("/tmp/audio.m4a")
            mock_rmdir.assert_called_once()


class TestYouTubeClientGetVideoInfoWithTranscript:
    """Test getting video info with transcript."""

    def test_get_video_info_with_transcript_success(self, youtube_client):
        """Test successful video info + transcript retrieval."""
        mock_video_info = {
            "video_id": "video123",
            "title": "Test Video",
            "duration_seconds": 300,
            "video_type": "video",
        }

        with (
            patch.object(
                youtube_client, "get_video_info", return_value=mock_video_info
            ),
            patch.object(
                youtube_client,
                "get_video_transcript",
                return_value=("Transcript text", "en"),
            ),
        ):
            result = youtube_client.get_video_info_with_transcript("video123")

            assert result["video_id"] == "video123"
            assert result["transcript"] == "Transcript text"
            assert result["transcript_language"] == "en"

    def test_get_video_info_with_transcript_no_video(self, youtube_client):
        """Test handling when video not found."""
        with patch.object(youtube_client, "get_video_info", return_value=None):
            result = youtube_client.get_video_info_with_transcript("video123")

            assert result is None

    def test_get_video_info_with_transcript_no_transcript(self, youtube_client):
        """Test handling when transcript unavailable."""
        mock_video_info = {"video_id": "video123", "title": "Test Video"}

        with (
            patch.object(
                youtube_client, "get_video_info", return_value=mock_video_info
            ),
            patch.object(
                youtube_client, "get_video_transcript", return_value=(None, None)
            ),
        ):
            result = youtube_client.get_video_info_with_transcript("video123")

            assert result is None


class TestYouTubeClientVideoTypeClassification:
    """Test video type classification logic."""

    def test_classify_short_video(self, youtube_client):
        """Test classification of short video."""
        result = youtube_client._classify_video_type(45, "Short video", "")
        assert result == "short"

    def test_classify_podcast_by_title(self, youtube_client):
        """Test podcast classification by title."""
        result = youtube_client._classify_video_type(
            1800, "Podcast Episode 5", "Regular description"
        )
        assert result == "podcast"

    def test_classify_podcast_by_description(self, youtube_client):
        """Test podcast classification by description."""
        result = youtube_client._classify_video_type(
            1800, "Regular title", "This is a podcast interview"
        )
        assert result == "podcast"

    def test_classify_regular_video(self, youtube_client):
        """Test classification of regular video."""
        result = youtube_client._classify_video_type(
            1800, "Regular video", "Regular description"
        )
        assert result == "video"
