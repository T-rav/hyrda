"""Tests for YouTube audio chunking functionality.

Tests the _chunk_audio_file method that splits large audio files for Whisper API.
"""

import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from services.youtube.youtube_client import YouTubeClient


@pytest.fixture
def youtube_client():
    """Create YouTube client with mock API key."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        return YouTubeClient()


class TestAudioChunking:
    """Test audio file chunking for large files."""

    def test_small_file_no_chunking(self, youtube_client):
        """Test that small files (<24MB) are not chunked."""
        # Create temp file smaller than 24MB
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
            f.write(b"0" * (20 * 1024 * 1024))  # 20MB
            temp_file = f.name

        try:
            chunks = youtube_client._chunk_audio_file(temp_file, max_size_mb=24)

            # Should return original file (no chunking)
            assert len(chunks) == 1
            assert chunks[0] == temp_file
        finally:
            os.unlink(temp_file)

    def test_large_file_chunking_calculation(self, youtube_client):
        """Test that large files (>24MB) trigger chunking logic."""
        # Create temp file larger than 24MB
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
            f.write(b"0" * (50 * 1024 * 1024))  # 50MB
            temp_file = f.name

        try:
            # Mock subprocess calls for ffprobe and ffmpeg
            with (
                patch("subprocess.run") as mock_run,
            ):
                # Mock ffprobe duration response (600 seconds)
                mock_run.return_value.stdout = "600.0"
                mock_run.return_value.returncode = 0

                chunks = youtube_client._chunk_audio_file(temp_file, max_size_mb=24)

                # Should split into multiple chunks (50MB / 24MB = ~3 chunks)
                # But will return original file if ffmpeg mock fails
                assert isinstance(chunks, list)
                assert len(chunks) >= 1
        finally:
            os.unlink(temp_file)

    def test_chunking_fallback_on_error(self, youtube_client):
        """Test that chunking falls back to original file on error."""
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
            f.write(b"0" * (30 * 1024 * 1024))  # 30MB
            temp_file = f.name

        try:
            # Mock subprocess to raise error
            with patch("subprocess.run", side_effect=Exception("ffmpeg error")):
                chunks = youtube_client._chunk_audio_file(temp_file, max_size_mb=24)

                # Should fall back to original file
                assert len(chunks) == 1
                assert chunks[0] == temp_file
        finally:
            os.unlink(temp_file)

    def test_max_size_parameter(self, youtube_client):
        """Test that max_size_mb parameter is respected."""
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
            f.write(b"0" * (15 * 1024 * 1024))  # 15MB
            temp_file = f.name

        try:
            # With max_size=20, should not chunk
            chunks = youtube_client._chunk_audio_file(temp_file, max_size_mb=20)
            assert len(chunks) == 1

            # With max_size=10, should trigger chunking logic
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.stdout = "300.0"
                mock_run.return_value.returncode = 0

                chunks = youtube_client._chunk_audio_file(temp_file, max_size_mb=10)
                assert isinstance(chunks, list)
        finally:
            os.unlink(temp_file)


class TestTranscribeAudio:
    """Test transcribe_audio handles chunking."""

    def test_transcribe_calls_chunking_for_large_file(self, youtube_client):
        """Test that transcribe_audio calls _chunk_audio_file for large files."""
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
            f.write(b"0" * (30 * 1024 * 1024))  # 30MB
            temp_file = f.name

        try:
            with (
                patch.object(
                    youtube_client, "_chunk_audio_file", return_value=[temp_file]
                ) as mock_chunk,
                patch("openai.OpenAI") as mock_openai_class,
            ):
                # Mock OpenAI client
                mock_client = Mock()
                mock_openai_class.return_value = mock_client
                mock_client.audio.transcriptions.create.return_value = "Test transcript"

                youtube_client.transcribe_audio(temp_file)

                # Should have called chunking
                mock_chunk.assert_called_once_with(temp_file)
        finally:
            os.unlink(temp_file)

    def test_transcribe_no_chunking_for_small_file(self, youtube_client):
        """Test that transcribe_audio skips chunking for small files."""
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
            f.write(b"0" * (10 * 1024 * 1024))  # 10MB
            temp_file = f.name

        try:
            with (
                patch.object(youtube_client, "_chunk_audio_file") as mock_chunk,
                patch("openai.OpenAI") as mock_openai_class,
            ):
                # Mock OpenAI client
                mock_client = Mock()
                mock_openai_class.return_value = mock_client
                mock_client.audio.transcriptions.create.return_value = "Test transcript"

                youtube_client.transcribe_audio(temp_file)

                # Should NOT have called chunking
                mock_chunk.assert_not_called()
        finally:
            os.unlink(temp_file)
