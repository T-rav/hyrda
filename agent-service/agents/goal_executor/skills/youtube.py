"""YouTube skill - search, transcript, and summarize.

Fetches YouTube videos, extracts transcripts, and summarizes them.
All artifacts are transparently cached in MinIO for future runs.
"""

import hashlib
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from ..services.memory import get_goal_memory
from .base import BaseSkill, SkillContext, SkillResult, SkillStatus
from .registry import register_skill

logger = logging.getLogger(__name__)


@dataclass
class YouTubeVideo:
    """YouTube video metadata."""

    video_id: str
    title: str
    channel: str
    description: str = ""
    url: str = ""
    published_at: str = ""
    duration: str = ""
    view_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "channel": self.channel,
            "description": self.description,
            "url": self.url,
            "published_at": self.published_at,
            "duration": self.duration,
            "view_count": self.view_count,
        }


@dataclass
class YouTubeData:
    """YouTube skill result data."""

    query: str = ""
    video: YouTubeVideo | None = None
    transcript: str = ""
    summary: str = ""
    cached: bool = False
    full_transcript_available: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "video": self.video.to_dict() if self.video else None,
            "transcript_length": len(self.transcript),
            "summary": self.summary,
            "cached": self.cached,
            "full_transcript_available": self.full_transcript_available,
        }


def extract_video_id(url_or_id: str) -> str | None:
    """Extract video ID from URL or return as-is if already an ID."""
    # Already a video ID (11 chars, alphanumeric with _ and -)
    # Must not contain other special chars like dots
    if re.match(r"^[a-zA-Z0-9_-]{11}$", url_or_id) and "." not in url_or_id:
        return url_or_id

    # YouTube URL patterns
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/v/([a-zA-Z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    return None


@register_skill
class YouTubeSkill(BaseSkill):
    """YouTube research skill - search, transcript, and summarize.

    This skill handles the full YouTube research workflow:
    1. Search for videos OR fetch by URL/ID
    2. Extract transcript
    3. Summarize content
    4. Cache everything transparently

    All artifacts (transcripts, summaries) are cached in MinIO.
    Future requests for the same video return cached data instantly.

    Parameters:
        query: Search query OR YouTube URL/video ID
        summarize: Auto-summarize transcript (default: True)
        summary_focus: What to focus on in summary (optional)
        full_transcript: Return full transcript instead of summary (default: False)
        max_results: Max search results to consider (default: 3)

    Returns:
        Video metadata, transcript, and summary

    Examples:
        # Search and summarize
        youtube(query="Acme Corp product demo")

        # Fetch specific video
        youtube(query="https://youtube.com/watch?v=abc123")

        # Get full transcript
        youtube(query="abc123", full_transcript=True)

        # Focused summary
        youtube(query="Acme Corp", summary_focus="Extract tech stack and product features")
    """

    name = "youtube"
    description = (
        "YouTube research - search, transcript, summarize with transparent caching"
    )
    version = "1.0.0"

    def __init__(self, context: SkillContext | None = None):
        super().__init__(context)
        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

    async def execute(
        self,
        query: str,
        summarize: bool = True,
        summary_focus: str | None = None,
        full_transcript: bool = False,
        max_results: int = 3,
    ) -> SkillResult[YouTubeData]:
        """Execute YouTube research.

        Args:
            query: Search query or video URL/ID
            summarize: Whether to summarize transcript
            summary_focus: Focus area for summary
            full_transcript: Return full transcript instead of summary
            max_results: Max search results

        Returns:
            SkillResult with video data, transcript, and summary
        """
        data = YouTubeData(query=query)

        # Check if query is a video ID/URL
        video_id = extract_video_id(query)

        if video_id:
            # Direct video fetch
            self._step("fetch_video")
            video = await self._get_video_info(video_id)
            if video:
                data.video = video
        else:
            # Search for videos
            self._step("search")
            videos = await self._search_videos(query, max_results)
            if videos:
                data.video = videos[0]  # Take top result
                video_id = data.video.video_id

        if not data.video or not video_id:
            return SkillResult(
                status=SkillStatus.PARTIAL,
                data=data,
                message=f"No videos found for '{query}'",
                steps_completed=["search"],
            )

        # Check cache for transcript
        self._step("check_cache")
        memory = get_goal_memory(self.context.bot_id)
        cache_key = f"youtube_transcript_{video_id}"
        cached_transcript = memory.recall(cache_key)

        if cached_transcript:
            data.transcript = cached_transcript
            data.cached = True
            self._step("cache_hit")
        else:
            # Fetch transcript
            self._step("fetch_transcript")
            transcript = await self._get_transcript(video_id)
            if transcript:
                data.transcript = transcript
                data.full_transcript_available = True
                # Cache it
                memory.remember(cache_key, transcript)
            else:
                return SkillResult(
                    status=SkillStatus.PARTIAL,
                    data=data,
                    message=f"Found video but transcript unavailable: {data.video.title}",
                    steps_completed=["search", "fetch_transcript"],
                )

        data.full_transcript_available = len(data.transcript) > 0

        # Return full transcript if requested
        if full_transcript:
            return SkillResult(
                status=SkillStatus.SUCCESS,
                data=data,
                message=f"Transcript for '{data.video.title}' ({len(data.transcript)} chars)",
                steps_completed=["search", "fetch_transcript"],
            )

        # Summarize
        if summarize and data.transcript:
            self._step("summarize")

            # Check summary cache
            focus_hash = hashlib.md5((summary_focus or "").encode()).hexdigest()[:8]
            summary_cache_key = f"youtube_summary_{video_id}_{focus_hash}"
            cached_summary = memory.recall(summary_cache_key)

            if cached_summary:
                data.summary = cached_summary
                self._step("summary_cache_hit")
            else:
                summary = await self._summarize_transcript(
                    data.transcript,
                    data.video.title,
                    summary_focus,
                )
                if summary:
                    data.summary = summary
                    memory.remember(summary_cache_key, summary)

        steps = ["search", "fetch_transcript"]
        if data.summary:
            steps.append("summarize")
        if data.cached:
            steps.append("cache_hit")

        return SkillResult(
            status=SkillStatus.SUCCESS,
            data=data,
            message=f"📺 {data.video.title} - {len(data.summary)} char summary",
            steps_completed=steps,
        )

    async def _search_videos(self, query: str, max_results: int) -> list[YouTubeVideo]:
        """Search YouTube for videos."""
        # Try YouTube Data API first
        if self.youtube_api_key:
            return await self._search_with_api(query, max_results)

        # Fallback to web search
        return await self._search_with_web(query, max_results)

    async def _search_with_api(
        self, query: str, max_results: int
    ) -> list[YouTubeVideo]:
        """Search using YouTube Data API."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params={
                        "part": "snippet",
                        "q": query,
                        "type": "video",
                        "maxResults": max_results,
                        "key": self.youtube_api_key,
                    },
                )

                if response.status_code != 200:
                    logger.warning(f"YouTube API error: {response.status_code}")
                    return []

                data = response.json()
                videos = []

                for item in data.get("items", []):
                    snippet = item.get("snippet", {})
                    video_id = item.get("id", {}).get("videoId", "")

                    if video_id:
                        videos.append(
                            YouTubeVideo(
                                video_id=video_id,
                                title=snippet.get("title", ""),
                                channel=snippet.get("channelTitle", ""),
                                description=snippet.get("description", "")[:500],
                                url=f"https://youtube.com/watch?v={video_id}",
                                published_at=snippet.get("publishedAt", ""),
                            )
                        )

                return videos
        except Exception as e:
            logger.error(f"YouTube API search error: {e}")
            return []

    async def _search_with_web(
        self, query: str, max_results: int
    ) -> list[YouTubeVideo]:
        """Fallback: search YouTube via web search."""
        try:
            from .prospect.clients import get_tavily

            tavily = get_tavily()
            if not tavily.is_configured:
                return []

            results = tavily.search(
                f"{query} site:youtube.com",
                max_results=max_results,
            )

            videos = []
            for r in results:
                video_id = extract_video_id(r.url)
                if video_id:
                    videos.append(
                        YouTubeVideo(
                            video_id=video_id,
                            title=r.title,
                            channel="",
                            description=r.content[:500],
                            url=r.url,
                        )
                    )

            return videos
        except Exception as e:
            logger.error(f"Web search for YouTube error: {e}")
            return []

    async def _get_video_info(self, video_id: str) -> YouTubeVideo | None:
        """Get video info by ID."""
        if self.youtube_api_key:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(
                        "https://www.googleapis.com/youtube/v3/videos",
                        params={
                            "part": "snippet,statistics,contentDetails",
                            "id": video_id,
                            "key": self.youtube_api_key,
                        },
                    )

                    if response.status_code == 200:
                        data = response.json()
                        items = data.get("items", [])
                        if items:
                            item = items[0]
                            snippet = item.get("snippet", {})
                            stats = item.get("statistics", {})
                            details = item.get("contentDetails", {})

                            return YouTubeVideo(
                                video_id=video_id,
                                title=snippet.get("title", ""),
                                channel=snippet.get("channelTitle", ""),
                                description=snippet.get("description", "")[:500],
                                url=f"https://youtube.com/watch?v={video_id}",
                                published_at=snippet.get("publishedAt", ""),
                                duration=details.get("duration", ""),
                                view_count=int(stats.get("viewCount", 0)),
                            )
            except Exception as e:
                logger.error(f"YouTube video info error: {e}")

        # Minimal fallback
        return YouTubeVideo(
            video_id=video_id,
            title=f"Video {video_id}",
            channel="",
            url=f"https://youtube.com/watch?v={video_id}",
        )

    async def _get_transcript(self, video_id: str) -> str | None:
        """Get video transcript."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            api = YouTubeTranscriptApi()
            transcript = api.fetch(video_id)

            # Combine all snippet text
            full_text = " ".join(snippet.text for snippet in transcript.snippets)

            return full_text.strip()
        except Exception as e:
            logger.warning(f"Transcript fetch error for {video_id}: {e}")
            return None

    async def _summarize_transcript(
        self,
        transcript: str,
        title: str,
        focus: str | None = None,
    ) -> str | None:
        """Summarize transcript using LLM."""
        if not self.openai_api_key:
            # Return truncated transcript if no LLM
            return transcript[:2000] + "..." if len(transcript) > 2000 else transcript

        try:
            import httpx

            # Build prompt
            focus_instruction = ""
            if focus:
                focus_instruction = f"\n\nFocus on: {focus}"

            prompt = f"""Summarize this YouTube video transcript concisely.

Title: {title}

Transcript:
{transcript[:15000]}

Provide a structured summary with:
- Key points (bullet points)
- Main takeaways
- Any notable quotes or claims{focus_instruction}

Keep the summary under 500 words."""

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 1000,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.warning(f"OpenAI summarize error: {response.status_code}")
                    return transcript[:2000]
        except Exception as e:
            logger.error(f"Summarize error: {e}")
            return transcript[:2000]
