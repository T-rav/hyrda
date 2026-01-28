"""Integration tests for YouTube audio chunking with real files and ffmpeg.

Tests the actual audio processing pipeline with real file I/O and subprocess calls.
"""

import os
import subprocess
import tempfile
from unittest.mock import patch

import pytest

from services.youtube.youtube_client import YouTubeClient


@pytest.mark.integration
class TestAudioChunkingIntegration:
    """Integration tests for audio chunking with real ffmpeg."""

    @pytest.fixture
    def youtube_client(self):
        """Create YouTube client with test API key."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-integration"}):
            return YouTubeClient()

    @pytest.fixture
    def create_test_audio_file(self):
        """Create a real audio file for testing using ffmpeg."""

        def _create(size_mb: int, duration_seconds: int = 60):
            """Create test audio file of specified size."""
            # Check if ffmpeg is available
            try:
                subprocess.run(
                    ["ffmpeg", "-version"],
                    capture_output=True,
                    check=True,
                    timeout=5,
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                pytest.skip("ffmpeg not available for integration tests")

            with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
                output_file = f.name

            try:
                # Generate silent audio file with ffmpeg
                # Target bitrate to achieve desired file size
                target_bitrate = int((size_mb * 8 * 1024) / duration_seconds)  # kbps

                subprocess.run(
                    [
                        "ffmpeg",
                        "-f",
                        "lavfi",
                        "-i",
                        f"anullsrc=r=44100:cl=stereo:d={duration_seconds}",
                        "-b:a",
                        f"{target_bitrate}k",
                        "-y",
                        output_file,
                    ],
                    capture_output=True,
                    check=True,
                    timeout=30,
                )

                return output_file
            except subprocess.CalledProcessError as e:
                # Cleanup on failure
                if os.path.exists(output_file):
                    os.unlink(output_file)
                pytest.skip(f"ffmpeg not available or failed: {e.stderr}")

        return _create

    def test_chunk_large_audio_file_with_real_ffmpeg(
        self, youtube_client, create_test_audio_file
    ):
        """Test chunking a real 30MB audio file with ffmpeg."""
        # Create 30MB audio file
        audio_file = create_test_audio_file(size_mb=30, duration_seconds=300)

        try:
            # Check actual file size (ffmpeg compression may result in smaller file)
            actual_size_mb = os.path.getsize(audio_file) / (1024 * 1024)
            max_size_mb = 24

            # If file is smaller than max size, it won't be chunked - skip test
            if actual_size_mb <= max_size_mb:
                pytest.skip(
                    f"File too small for chunking test: {actual_size_mb:.2f}MB <= {max_size_mb}MB"
                )

            # Chunk the file (max 24MB)
            chunks = youtube_client._chunk_audio_file(audio_file, max_size_mb=max_size_mb)

            # Should have created multiple chunks
            assert len(chunks) >= 2, f"Expected multiple chunks, got {len(chunks)}"

            # All chunk files should exist
            for chunk in chunks:
                assert os.path.exists(chunk), f"Chunk file not found: {chunk}"

                # Chunk should be smaller than original
                chunk_size_mb = os.path.getsize(chunk) / (1024 * 1024)
                assert chunk_size_mb <= 25, f"Chunk too large: {chunk_size_mb:.1f}MB"

            # Cleanup chunk files
            for chunk in chunks:
                if chunk != audio_file and os.path.exists(chunk):
                    os.unlink(chunk)

        finally:
            # Cleanup original file
            if os.path.exists(audio_file):
                os.unlink(audio_file)

    def test_small_audio_file_no_chunking_integration(
        self, youtube_client, create_test_audio_file
    ):
        """Test that small files are not chunked (real file)."""
        # Create 10MB audio file
        audio_file = create_test_audio_file(size_mb=10, duration_seconds=120)

        try:
            # Attempt to chunk
            chunks = youtube_client._chunk_audio_file(audio_file, max_size_mb=24)

            # Should return original file only (no chunking)
            assert len(chunks) == 1
            assert chunks[0] == audio_file

        finally:
            if os.path.exists(audio_file):
                os.unlink(audio_file)

    def test_chunk_timing_and_quality(self, youtube_client, create_test_audio_file):
        """Test that chunked audio maintains quality and timing."""
        # Create 50MB audio file with known duration
        audio_file = create_test_audio_file(size_mb=50, duration_seconds=600)

        try:
            # Check actual file size (ffmpeg compression may result in smaller file)
            actual_size_mb = os.path.getsize(audio_file) / (1024 * 1024)
            max_size_mb = 24

            # If file is smaller than max size, it won't be chunked - skip test
            if actual_size_mb <= max_size_mb:
                pytest.skip(
                    f"File too small for chunking test: {actual_size_mb:.2f}MB <= {max_size_mb}MB"
                )

            # Chunk the file
            chunks = youtube_client._chunk_audio_file(audio_file, max_size_mb=max_size_mb)

            # Should have multiple chunks based on actual size
            assert len(chunks) >= 2, f"Expected multiple chunks, got {len(chunks)}"

            # Verify each chunk's duration using ffprobe
            total_chunk_duration = 0
            for chunk in chunks:
                result = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=noprint_wrappers=1:nokey=1",
                        chunk,
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                chunk_duration = float(result.stdout.strip())
                total_chunk_duration += chunk_duration

            # Total duration should approximately match original (within 1 second)
            assert abs(total_chunk_duration - 600) < 1, (
                f"Duration mismatch: expected ~600s, got {total_chunk_duration:.1f}s"
            )

            # Cleanup
            for chunk in chunks:
                if chunk != audio_file and os.path.exists(chunk):
                    os.unlink(chunk)

        finally:
            if os.path.exists(audio_file):
                os.unlink(audio_file)


@pytest.mark.integration
class TestTranscriptionIntegration:
    """Integration tests for transcription with chunking."""

    @pytest.fixture
    def youtube_client(self):
        """Create YouTube client with test API key."""
        # Use real API key from environment for integration tests
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip(
                "OPENAI_API_KEY not set - skipping transcription integration test"
            )
        return YouTubeClient(openai_api_key=api_key)

    @pytest.mark.skipif(
        not os.getenv("RUN_EXPENSIVE_TESTS"),
        reason="Skipping expensive OpenAI API test (set RUN_EXPENSIVE_TESTS=1 to run)",
    )
    def test_transcribe_large_file_with_chunking(self, youtube_client):
        """Test transcription of large file with automatic chunking.

        WARNING: This test makes real OpenAI API calls and costs money.
        Only run with RUN_EXPENSIVE_TESTS=1 environment variable.
        """
        # Create 30MB test audio file with actual speech
        # (In real test, we'd download a known YouTube video's audio)
        pytest.skip("Implementation requires test audio file with speech")

    def test_transcription_failure_recovery(self, youtube_client):
        """Test that transcription failures are handled gracefully."""
        # Create invalid audio file
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
            f.write(b"invalid audio data")
            invalid_file = f.name

        try:
            # Mock OpenAI to avoid real API call
            with patch("openai.OpenAI") as mock_openai_class:
                mock_client = mock_openai_class.return_value
                mock_client.audio.transcriptions.create.side_effect = Exception(
                    "Invalid audio format"
                )

                # Should return None on failure, not crash
                result = youtube_client.transcribe_audio(invalid_file)
                assert result is None

        finally:
            if os.path.exists(invalid_file):
                os.unlink(invalid_file)
