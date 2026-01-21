"""
YouTube Client Service

Handles interaction with YouTube Data API v3, audio download, and transcription.
"""

import json
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


class YouTubeClient:
    """Client for fetching YouTube channel videos, downloading audio, and transcribing."""

    def __init__(
        self, youtube_api_key: str | None = None, openai_api_key: str | None = None
    ):
        """
        Initialize YouTube client.

        Args:
            youtube_api_key: YouTube Data API v3 key. If None, reads from YOUTUBE_API_KEY env var.
            openai_api_key: OpenAI API key for Whisper transcription. If None, reads from OPENAI_API_KEY env var.
        """
        self.youtube_api_key = youtube_api_key or os.getenv("YOUTUBE_API_KEY")
        if not self.youtube_api_key:
            raise ValueError(
                "YouTube API key is required. Set YOUTUBE_API_KEY environment variable."
            )

        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError(
                "OpenAI API key is required for transcription. Set OPENAI_API_KEY environment variable."
            )

        self.youtube = build("youtube", "v3", developerKey=self.youtube_api_key)

    def extract_channel_id_from_url(self, url: str) -> tuple[str | None, str | None]:
        """
        Extract channel ID or handle from YouTube URL.

        Args:
            url: YouTube channel URL

        Returns:
            Tuple of (channel_id, handle) where one will be None
        """
        # Pattern for @handle URLs: https://www.youtube.com/@8thLightInc
        handle_match = re.search(r"youtube\.com/@([\w-]+)", url)
        if handle_match:
            return (None, handle_match.group(1))

        # Pattern for channel ID URLs: https://www.youtube.com/channel/UC...
        channel_match = re.search(r"youtube\.com/channel/([\w-]+)", url)
        if channel_match:
            return (channel_match.group(1), None)

        # Pattern for user URLs: https://www.youtube.com/user/username
        user_match = re.search(r"youtube\.com/user/([\w-]+)", url)
        if user_match:
            # Need to look up channel by username
            return (None, user_match.group(1))

        # If no pattern matches, try treating it as a channel ID directly
        return (url, None)

    def get_channel_id_from_handle(self, handle: str) -> str | None:
        """
        Get channel ID from channel handle.

        Args:
            handle: Channel handle (e.g., '8thLightInc')

        Returns:
            Channel ID or None if not found
        """
        try:
            # Search for channel by handle
            request = self.youtube.search().list(
                part="snippet", q=f"@{handle}", type="channel", maxResults=1
            )
            response = request.execute()

            if response["items"]:
                return response["items"][0]["snippet"]["channelId"]
            return None
        except Exception as e:
            logger.error(f"Error looking up channel handle {handle}: {e}")
            return None

    def get_channel_info(self, channel_id: str) -> dict[str, Any] | None:
        """
        Get channel information.

        Args:
            channel_id: YouTube channel ID

        Returns:
            Dictionary with channel info or None if not found
        """
        try:
            request = self.youtube.channels().list(
                part="snippet,statistics", id=channel_id
            )
            response = request.execute()

            if not response["items"]:
                return None

            item = response["items"][0]
            return {
                "channel_id": item["id"],
                "channel_name": item["snippet"]["title"],
                "description": item["snippet"]["description"],
                "subscriber_count": int(
                    item["statistics"].get("subscriberCount", 0)
                ),
                "video_count": int(item["statistics"].get("videoCount", 0)),
                "view_count": int(item["statistics"].get("viewCount", 0)),
            }
        except Exception as e:
            logger.error(f"Error fetching channel info for {channel_id}: {e}")
            return None

    def list_channel_videos(
        self,
        channel_id: str,
        include_videos: bool = True,
        include_shorts: bool = True,
        include_podcasts: bool = True,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        List videos from a YouTube channel.

        Args:
            channel_id: YouTube channel ID
            include_videos: Include regular videos
            include_shorts: Include YouTube Shorts
            include_podcasts: Include podcast episodes
            max_results: Maximum number of videos to fetch (None = all)

        Returns:
            List of video metadata dictionaries
        """
        videos = []
        page_token = None

        try:
            while True:
                # Search for channel uploads
                request = self.youtube.search().list(
                    part="id,snippet",
                    channelId=channel_id,
                    type="video",
                    order="date",
                    maxResults=50,  # API limit per request
                    pageToken=page_token,
                )
                response = request.execute()

                # Get detailed video info for duration filtering
                video_ids = [item["id"]["videoId"] for item in response["items"]]
                if video_ids:
                    videos_detail = self._get_videos_detail(video_ids)

                    for video in videos_detail:
                        video_type = self._classify_video_type(video)

                        # Filter by type
                        if video_type == "video" and not include_videos:
                            continue
                        if video_type == "short" and not include_shorts:
                            continue
                        if video_type == "podcast" and not include_podcasts:
                            continue

                        videos.append(video)

                        # Check max results
                        if max_results and len(videos) >= max_results:
                            return videos[:max_results]

                # Check if there are more pages
                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            return videos
        except Exception as e:
            logger.error(f"Error listing channel videos for {channel_id}: {e}")
            return videos

    def _get_videos_detail(self, video_ids: list[str]) -> list[dict[str, Any]]:
        """
        Get detailed information for a list of video IDs.

        Args:
            video_ids: List of YouTube video IDs

        Returns:
            List of video metadata dictionaries
        """
        try:
            request = self.youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=",".join(video_ids),
            )
            response = request.execute()

            videos = []
            for item in response["items"]:
                videos.append(
                    {
                        "video_id": item["id"],
                        "title": item["snippet"]["title"],
                        "description": item["snippet"]["description"],
                        "channel_id": item["snippet"]["channelId"],
                        "channel_name": item["snippet"]["channelTitle"],
                        "published_at": datetime.fromisoformat(
                            item["snippet"]["publishedAt"].replace("Z", "+00:00")
                        ),
                        "duration": item["contentDetails"]["duration"],
                        "view_count": int(item["statistics"].get("viewCount", 0)),
                        "like_count": int(item["statistics"].get("likeCount", 0)),
                        "comment_count": int(
                            item["statistics"].get("commentCount", 0)
                        ),
                        "thumbnail_url": item["snippet"]["thumbnails"]["high"]["url"],
                    }
                )
            return videos
        except Exception as e:
            logger.error(f"Error fetching video details: {e}")
            return []

    def _classify_video_type(self, video: dict[str, Any]) -> str:
        """
        Classify video as video, short, or podcast.

        Args:
            video: Video metadata dictionary

        Returns:
            'video', 'short', or 'podcast'
        """
        duration = video.get("duration", "")
        title = video.get("title", "").lower()
        description = video.get("description", "").lower()

        # Parse ISO 8601 duration to seconds
        duration_seconds = self._parse_duration(duration)

        # YouTube Shorts are typically under 60 seconds
        if duration_seconds and duration_seconds <= 60:
            return "short"

        # Check for podcast indicators
        podcast_keywords = ["podcast", "episode", "ep.", "interview"]
        if any(keyword in title or keyword in description for keyword in podcast_keywords):
            return "podcast"

        return "video"

    def _parse_duration(self, duration: str) -> int | None:
        """
        Parse ISO 8601 duration to seconds.

        Args:
            duration: ISO 8601 duration string (e.g., 'PT15M33S')

        Returns:
            Duration in seconds or None if parsing fails
        """
        try:
            match = re.match(
                r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration
            )
            if not match:
                return None

            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)

            return hours * 3600 + minutes * 60 + seconds
        except Exception:
            return None

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

            result = subprocess.run(
                command, check=True, capture_output=True, text=True
            )

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

    def transcribe_audio(self, audio_file_path: str) -> str | None:
        """
        Transcribe audio file using OpenAI Whisper API.

        Args:
            audio_file_path: Path to audio file

        Returns:
            Transcribed text, or None if transcription fails
        """
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.openai_api_key)

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

    def get_video_info_with_transcript(
        self, video_id: str
    ) -> dict[str, Any] | None:
        """
        Get video info including transcript.

        Args:
            video_id: YouTube video ID

        Returns:
            Dictionary with video info and transcript, or None if video not found
        """
        videos = self._get_videos_detail([video_id])
        if not videos:
            return None

        video = videos[0]
        transcript, language = self.get_video_transcript(video_id)

        if not transcript:
            logger.warning(f"Skipping video {video_id} - no transcript available")
            return None

        video["transcript"] = transcript
        video["transcript_language"] = language
        video["video_type"] = self._classify_video_type(video)
        video["duration_seconds"] = self._parse_duration(video["duration"])

        return video
