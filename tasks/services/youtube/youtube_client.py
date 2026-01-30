"""
YouTube Client Service

Uses yt-dlp for all operations - no YouTube Data API required!
Only requires OpenAI API key for Whisper transcription.
"""

import contextlib
import json
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# Security: Validate YouTube URLs to prevent command injection
YOUTUBE_URL_PATTERNS = [
    r"^https?://(www\.)?youtube\.com/",
    r"^https?://(www\.)?youtu\.be/",
    r"^https?://youtube\.com/",
    r"^https?://youtu\.be/",
]
YOUTUBE_URL_REGEX = re.compile("|".join(YOUTUBE_URL_PATTERNS), re.IGNORECASE)


def validate_youtube_url(url: str) -> bool:
    """Validate that a URL is a legitimate YouTube URL.

    Args:
        url: URL to validate

    Returns:
        True if valid YouTube URL, False otherwise
    """
    # Basic validation: must be non-empty string matching YouTube pattern
    if not url or not isinstance(url, str) or not YOUTUBE_URL_REGEX.match(url):
        return False

    # Parse and validate URL components
    try:
        parsed = urlparse(url)
        allowed_domains = ("youtube.com", "www.youtube.com", "youtu.be", "www.youtu.be")
        is_valid = (
            parsed.scheme in ("http", "https")
            and parsed.netloc
            and parsed.netloc.lower() in allowed_domains
        )
        return is_valid
    except Exception:
        return False


class YouTubeClient:
    """Client for fetching YouTube videos and transcribing using only yt-dlp + Whisper."""

    def __init__(self, openai_api_key: str | None = None):
        """
        Initialize YouTube client.

        Args:
            openai_api_key: OpenAI API key for Whisper transcription. If None, reads from OPENAI_API_KEY env var.
        """
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError(
                "OpenAI API key is required for transcription. Set OPENAI_API_KEY environment variable."
            )

    def get_channel_info(self, channel_url: str) -> dict[str, Any] | None:
        """
        Get channel information using yt-dlp.

        Args:
            channel_url: YouTube channel URL (e.g., https://www.youtube.com/@8thLightInc)

        Returns:
            Dictionary with channel info or None if not found
        """
        # Security: Validate URL before passing to subprocess
        if not validate_youtube_url(channel_url):
            logger.error(f"Invalid YouTube URL provided: {channel_url}")
            return None

        try:
            command = [
                "yt-dlp",
                "--dump-json",
                "--playlist-items",
                "1",  # Just get first video to extract channel info
                channel_url,
            ]

            result = subprocess.run(command, check=True, capture_output=True, text=True)

            # Parse JSON from first video
            first_video = json.loads(result.stdout.split("\n")[0])

            return {
                "channel_id": first_video.get("channel_id", ""),
                "channel_name": first_video.get("channel", ""),
                "channel_url": first_video.get("channel_url", channel_url),
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"Error fetching channel info for {channel_url}: {e.stderr}")
            return None
        except Exception as e:
            logger.error(f"Error fetching channel info: {e}")
            return None

    def list_channel_videos(
        self,
        channel_url: str,
        include_videos: bool = True,
        include_shorts: bool = True,
        include_podcasts: bool = True,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        List videos from a YouTube channel using yt-dlp.

        Args:
            channel_url: YouTube channel URL (e.g., https://www.youtube.com/@8thLightInc)
            include_videos: Include regular videos
            include_shorts: Include YouTube Shorts
            include_podcasts: Include podcast episodes
            max_results: Maximum number of videos to fetch (None = all)

        Returns:
            List of video metadata dictionaries
        """
        # Security: Validate URL before passing to subprocess
        if not validate_youtube_url(channel_url):
            logger.error(f"Invalid YouTube URL provided: {channel_url}")
            return []

        try:
            # Build yt-dlp command to list all videos
            command = [
                "yt-dlp",
                "--flat-playlist",
                "--dump-json",
                channel_url,
            ]

            if max_results:
                command.extend(["--playlist-end", str(max_results)])

            result = subprocess.run(command, check=True, capture_output=True, text=True)

            videos = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                video_data = json.loads(line)

                # Extract basic info
                video = {
                    "video_id": video_data.get("id", ""),
                    "title": video_data.get("title", ""),
                    "url": video_data.get("url", ""),
                }

                videos.append(video)

            # Filter by type if needed
            if not (include_videos and include_shorts and include_podcasts):
                filtered_videos = []
                for video in videos:
                    # Get detailed info to determine type
                    detailed_info = self.get_video_info(video["video_id"])
                    if not detailed_info:
                        continue

                    video_type = detailed_info.get("video_type", "video")

                    if video_type == "video" and not include_videos:
                        continue
                    if video_type == "short" and not include_shorts:
                        continue
                    if video_type == "podcast" and not include_podcasts:
                        continue

                    filtered_videos.append(video)

                return filtered_videos[:max_results] if max_results else filtered_videos

            return videos[:max_results] if max_results else videos

        except subprocess.CalledProcessError as e:
            logger.error(f"Error listing channel videos for {channel_url}: {e.stderr}")
            return []
        except Exception as e:
            logger.error(f"Error listing channel videos: {e}")
            return []

    def get_video_info(self, video_id: str) -> dict[str, Any] | None:
        """
        Get detailed video information using yt-dlp.

        Args:
            video_id: YouTube video ID

        Returns:
            Dictionary with video metadata or None if not found
        """
        # Security: Validate video_id format to prevent injection
        if not video_id or not isinstance(video_id, str):
            logger.error("Invalid video_id provided")
            return None

        # YouTube video IDs are 11 characters, alphanumeric, hyphen, underscore
        if not re.match(r"^[a-zA-Z0-9_-]{11}$", video_id):
            logger.error(f"Invalid video_id format: {video_id}")
            return None

        try:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            command = [
                "yt-dlp",
                "--dump-json",
                "--no-download",
                video_url,
            ]

            result = subprocess.run(command, check=True, capture_output=True, text=True)

            video_data = json.loads(result.stdout)

            # Parse duration
            duration_seconds = video_data.get("duration", 0)

            # Classify video type
            video_type = self._classify_video_type(
                duration_seconds,
                video_data.get("title", ""),
                video_data.get("description", ""),
            )

            # Parse upload date
            upload_date = video_data.get("upload_date", "")
            published_at = None
            if upload_date:
                from contextlib import suppress

                with suppress(Exception):
                    published_at = datetime.strptime(upload_date, "%Y%m%d")

            return {
                "video_id": video_id,
                "title": video_data.get("title", ""),
                "description": video_data.get("description", ""),
                "channel_id": video_data.get("channel_id", ""),
                "channel_name": video_data.get("channel", ""),
                "published_at": published_at,
                "duration_seconds": duration_seconds,
                "view_count": video_data.get("view_count", 0),
                "like_count": video_data.get("like_count", 0),
                "comment_count": video_data.get("comment_count", 0),
                "thumbnail_url": video_data.get("thumbnail", ""),
                "video_type": video_type,
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"Error fetching video info for {video_id}: {e.stderr}")
            return None
        except Exception as e:
            logger.error(f"Error fetching video info: {e}")
            return None

    def _classify_video_type(
        self, duration_seconds: int, title: str, description: str
    ) -> str:
        """
        Classify video as video, short, or podcast.

        Args:
            duration_seconds: Video duration in seconds
            title: Video title
            description: Video description

        Returns:
            'video', 'short', or 'podcast'
        """
        title_lower = title.lower()
        description_lower = description.lower()

        # YouTube Shorts are typically under 60 seconds
        if duration_seconds and duration_seconds <= 60:
            return "short"

        # Check for podcast indicators
        podcast_keywords = ["podcast", "episode", "ep.", "interview"]
        if any(
            keyword in title_lower or keyword in description_lower
            for keyword in podcast_keywords
        ):
            return "podcast"

        return "video"

    def download_audio(
        self, video_url: str, output_path: str | None = None
    ) -> str | None:
        """
        Download audio from YouTube video using yt-dlp.

        Args:
            video_url: YouTube video URL
            output_path: Output directory (default: temp directory)

        Returns:
            Path to downloaded audio file, or None if download fails
        """
        # Security: Validate URL before passing to subprocess
        if not validate_youtube_url(video_url):
            logger.error(f"Invalid YouTube URL provided: {video_url}")
            return None

        if output_path is None:
            output_path = tempfile.mkdtemp()

        try:
            # Use yt-dlp to download audio only
            command = [
                "yt-dlp",
                "-x",  # Extract audio
                "--audio-format",
                "m4a",  # Audio format
                "--output",
                os.path.join(output_path, "%(id)s.%(ext)s"),  # Use video ID as filename
                "--format",
                "bestaudio",
                "-N",
                "4",  # Use 4 connections
                video_url,
            ]

            result = subprocess.run(command, check=True, capture_output=True, text=True)

            # Extract file path from yt-dlp output
            file_path_match = re.search(r"Destination:\s+(.*\.m4a)", result.stdout)
            if file_path_match:
                return file_path_match.group(1)

            # If not found, try to find the file in output directory
            for file in os.listdir(output_path):
                if file.endswith(".m4a"):
                    return os.path.join(output_path, file)

            logger.error("Audio file not found after download")
            return None

        except subprocess.CalledProcessError as e:
            logger.error(f"Error downloading audio from {video_url}: {e.stderr}")
            return None
        except Exception as e:
            logger.error(f"Error downloading audio: {e}")
            return None

    def _chunk_audio_file(
        self, audio_file_path: str, max_size_mb: int = 24
    ) -> list[str]:
        """
        Split large audio file into smaller chunks using ffmpeg.

        Args:
            audio_file_path: Path to audio file
            max_size_mb: Maximum size per chunk in MB (default 24MB to stay under 25MB limit)

        Returns:
            List of chunk file paths
        """
        import os

        file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)

        if file_size_mb <= max_size_mb:
            return [audio_file_path]

        try:
            # Calculate chunk duration based on file size and bitrate estimate
            # Assuming average bitrate of ~128kbps for m4a files
            duration_cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                audio_file_path,
            ]

            duration_result = subprocess.run(
                duration_cmd, capture_output=True, text=True, check=True
            )
            total_duration = float(duration_result.stdout.strip())

            # Calculate chunk duration to keep each chunk under max_size_mb
            num_chunks = int(file_size_mb / max_size_mb) + 1
            chunk_duration = total_duration / num_chunks

            logger.info(
                f"Splitting audio file ({file_size_mb:.1f}MB) into {num_chunks} chunks "
                f"of ~{chunk_duration:.0f}s each"
            )

            # Split audio file into chunks
            chunk_paths = []
            output_dir = os.path.dirname(audio_file_path)
            base_name = os.path.splitext(os.path.basename(audio_file_path))[0]

            for i in range(num_chunks):
                start_time = i * chunk_duration
                chunk_path = os.path.join(output_dir, f"{base_name}_chunk{i}.m4a")

                chunk_cmd = [
                    "ffmpeg",
                    "-i",
                    audio_file_path,
                    "-ss",
                    str(start_time),
                    "-t",
                    str(chunk_duration),
                    "-c",
                    "copy",
                    "-y",  # Overwrite output file
                    chunk_path,
                ]

                subprocess.run(
                    chunk_cmd, capture_output=True, text=True, check=True, timeout=300
                )
                chunk_paths.append(chunk_path)

            logger.info(f"Created {len(chunk_paths)} audio chunks")
            return chunk_paths

        except Exception as e:
            logger.error(f"Error chunking audio file: {e}")
            return [audio_file_path]  # Fall back to original file

    def transcribe_audio(self, audio_file_path: str) -> str | None:
        """
        Transcribe audio file using OpenAI Whisper API.
        Automatically chunks large files (>24MB) before transcription.

        Args:
            audio_file_path: Path to audio file

        Returns:
            Transcribed text, or None if transcription fails
        """
        import os

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.openai_api_key)

            # Check file size and chunk if needed
            file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)

            if file_size_mb > 24:
                logger.info(
                    f"Audio file is {file_size_mb:.1f}MB, chunking before transcription"
                )
                chunk_paths = self._chunk_audio_file(audio_file_path)

                # Transcribe each chunk
                transcriptions = []
                for i, chunk_path in enumerate(chunk_paths):
                    logger.debug(
                        f"Transcribing chunk {i + 1}/{len(chunk_paths)}: {chunk_path}"
                    )
                    with open(chunk_path, "rb") as audio_file:
                        transcription = client.audio.transcriptions.create(
                            model="whisper-1", file=audio_file, response_format="text"
                        )
                        if transcription and transcription.strip():
                            transcriptions.append(transcription.strip())

                    # Clean up chunk file if it's not the original
                    if chunk_path != audio_file_path:
                        with contextlib.suppress(Exception):
                            os.remove(chunk_path)

                # Assemble transcriptions
                full_transcript = " ".join(transcriptions)
                logger.info(
                    f"Assembled transcript from {len(transcriptions)} chunks "
                    f"({len(full_transcript)} characters)"
                )
                return full_transcript if full_transcript else None

            else:
                # File is small enough, transcribe directly
                with open(audio_file_path, "rb") as audio_file:
                    logger.debug(f"Transcribing audio file: {audio_file_path}")
                    transcription = client.audio.transcriptions.create(
                        model="whisper-1", file=audio_file, response_format="text"
                    )

                return transcription if transcription.strip() else None

        except Exception as e:
            logger.error(f"Error transcribing audio file: {e}")
            return None

    def get_video_transcript(
        self, video_id: str, cleanup: bool = True
    ) -> tuple[str | None, str | None]:
        """
        Download video audio and transcribe it.

        Args:
            video_id: YouTube video ID
            cleanup: Whether to delete downloaded audio file after transcription

        Returns:
            Tuple of (transcript_text, 'en') or (None, None) if transcription fails
        """
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        try:
            # Download audio
            audio_path = self.download_audio(video_url)
            if not audio_path:
                return (None, None)

            # Transcribe audio
            transcript = self.transcribe_audio(audio_path)

            # Cleanup audio file
            if cleanup and audio_path and os.path.exists(audio_path):
                try:
                    os.unlink(audio_path)
                    # Also try to clean up temp directory if empty
                    temp_dir = os.path.dirname(audio_path)
                    if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                        os.rmdir(temp_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup audio file: {e}")

            return (transcript, "en" if transcript else None)

        except Exception as e:
            logger.error(f"Error getting transcript for video {video_id}: {e}")
            return (None, None)

    def get_video_info_with_transcript(self, video_id: str) -> dict[str, Any] | None:
        """
        Get video info including transcript.

        Args:
            video_id: YouTube video ID

        Returns:
            Dictionary with video info and transcript, or None if video not found
        """
        video_info = self.get_video_info(video_id)
        if not video_info:
            return None

        transcript, language = self.get_video_transcript(video_id)

        if not transcript:
            logger.warning(f"Skipping video {video_id} - no transcript available")
            return None

        video_info["transcript"] = transcript
        video_info["transcript_language"] = language

        return video_info
