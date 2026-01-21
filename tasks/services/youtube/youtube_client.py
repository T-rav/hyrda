"""
YouTube Client Service

Handles interaction with YouTube Data API v3 and transcript fetching.
"""

import logging
import os
import re
from datetime import datetime
from typing import Any

from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

logger = logging.getLogger(__name__)


class YouTubeClient:
    """Client for fetching YouTube channel videos and transcripts."""

    def __init__(self, api_key: str | None = None):
        """
        Initialize YouTube client.

        Args:
            api_key: YouTube Data API v3 key. If None, reads from YOUTUBE_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "YouTube API key is required. Set YOUTUBE_API_KEY environment variable."
            )

        self.youtube = build("youtube", "v3", developerKey=self.api_key)

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

    def get_video_transcript(
        self, video_id: str, preferred_languages: list[str] | None = None
    ) -> tuple[str | None, str | None]:
        """
        Get transcript for a YouTube video.

        Args:
            video_id: YouTube video ID
            preferred_languages: List of preferred language codes (e.g., ['en', 'es'])

        Returns:
            Tuple of (transcript_text, language_code) or (None, None) if not available
        """
        if preferred_languages is None:
            preferred_languages = ["en"]

        try:
            # Try to get transcript in preferred languages
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Try manual transcripts first (higher quality)
            try:
                transcript = transcript_list.find_manually_created_transcript(
                    preferred_languages
                )
                transcript_data = transcript.fetch()
                language = transcript.language_code
            except NoTranscriptFound:
                # Fall back to auto-generated transcripts
                transcript = transcript_list.find_generated_transcript(
                    preferred_languages
                )
                transcript_data = transcript.fetch()
                language = transcript.language_code

            # Combine transcript segments
            full_transcript = " ".join([segment["text"] for segment in transcript_data])
            return (full_transcript, language)

        except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
            logger.warning(f"Transcript not available for video {video_id}: {e}")
            return (None, None)
        except Exception as e:
            logger.error(f"Error fetching transcript for video {video_id}: {e}")
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
