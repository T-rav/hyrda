"""
YouTube Video Tracking Service

Handles tracking of ingested YouTube videos for idempotent ingestion.
Uses the youtube_videos_data table to store content hashes and UUIDs.
"""

import hashlib
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# Add tasks path for database access
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tasks"))

# Import from tasks/models/base.py
from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, get_data_db_session  # noqa: E402


class YouTubeVideo(Base):
    """Model for tracking ingested YouTube videos."""

    __tablename__ = "youtube_videos_data"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # YouTube identifiers
    youtube_video_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    video_title: Mapped[str] = mapped_column(String(512), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Video metadata
    video_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'video', 'short', 'podcast'
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    view_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Content tracking
    transcript_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # SHA-256 of transcript
    transcript_language: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # e.g., 'en', 'es'

    # Vector database tracking
    vector_uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    vector_namespace: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="youtube"
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # Ingestion metadata
    first_ingested_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    last_ingested_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    ingestion_status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="success"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Additional metadata (JSON)
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, name="metadata"
    )


class YouTubeTrackingService:
    """Service for tracking YouTube video ingestion."""

    @staticmethod
    def compute_transcript_hash(transcript: str) -> str:
        """
        Compute SHA-256 hash of video transcript.

        Args:
            transcript: Video transcript text

        Returns:
            SHA-256 hash as hex string
        """
        return hashlib.sha256(transcript.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_base_uuid(youtube_video_id: str) -> str:
        """
        Generate a deterministic base UUID from YouTube video ID.

        This UUID serves as the base for chunk UUIDs:
        - Chunk 0: base_uuid with suffix _0
        - Chunk 1: base_uuid with suffix _1
        - etc.

        Args:
            youtube_video_id: YouTube video ID

        Returns:
            UUID string
        """
        # Use UUID5 with YouTube namespace for deterministic UUIDs
        namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace
        return str(uuid.uuid5(namespace, f"youtube:{youtube_video_id}"))

    def check_video_needs_reindex_by_metadata(
        self, youtube_video_id: str, published_at: datetime | None
    ) -> tuple[bool, str | None]:
        """
        Check if a video needs reindexing based on metadata (FAST - no transcription).

        This method checks if the video exists and if its published_at date has changed.
        Use this BEFORE transcription to avoid unnecessary API costs.

        Args:
            youtube_video_id: YouTube video ID
            published_at: Video publication date from YouTube API

        Returns:
            Tuple of (needs_reindex, existing_uuid)
            - needs_reindex: True if video is new or published_at changed
            - existing_uuid: Base UUID if video exists, None otherwise
        """
        with get_data_db_session() as session:
            video_record = (
                session.query(YouTubeVideo)
                .filter(YouTubeVideo.youtube_video_id == youtube_video_id)
                .first()
            )

            if not video_record:
                # Video doesn't exist, needs indexing
                return (True, None)

            # Compare published_at dates (videos don't change after publishing)
            # If published_at matches, video hasn't changed - skip transcription!
            if published_at and video_record.published_at:
                # Compare dates (ignore time differences for comparison)
                existing_date = (
                    video_record.published_at.date()
                    if video_record.published_at
                    else None
                )
                new_date = published_at.date() if published_at else None

                if existing_date == new_date:
                    # Published date unchanged, video content unchanged - SKIP!
                    return (False, video_record.vector_uuid)

            # If we can't compare dates or they differ, transcribe to be safe
            return (True, video_record.vector_uuid)

    def check_video_needs_reindex(
        self, youtube_video_id: str, transcript: str
    ) -> tuple[bool, str | None]:
        """
        Check if a video needs to be reindexed based on transcript changes.

        NOTE: This method requires the full transcript (expensive to obtain).
        Use check_video_needs_reindex_by_metadata() first to avoid transcription costs.

        Args:
            youtube_video_id: YouTube video ID
            transcript: Current video transcript

        Returns:
            Tuple of (needs_reindex, existing_uuid)
            - needs_reindex: True if video should be reindexed
            - existing_uuid: Base UUID if video exists, None otherwise
        """
        current_hash = self.compute_transcript_hash(transcript)

        with get_data_db_session() as session:
            video_record = (
                session.query(YouTubeVideo)
                .filter(YouTubeVideo.youtube_video_id == youtube_video_id)
                .first()
            )

            if not video_record:
                # Video doesn't exist, needs indexing
                return (True, None)

            if video_record.transcript_hash != current_hash:
                # Transcript changed, needs reindexing
                return (True, video_record.vector_uuid)

            # Transcript unchanged, skip
            return (False, video_record.vector_uuid)

    def record_video_ingestion(
        self,
        youtube_video_id: str,
        video_title: str,
        channel_id: str,
        channel_name: str,
        video_type: str,
        transcript: str,
        vector_uuid: str,
        chunk_count: int,
        duration_seconds: int | None = None,
        published_at: datetime | None = None,
        view_count: int | None = None,
        transcript_language: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Record or update a video ingestion in the tracking database.

        Args:
            youtube_video_id: YouTube video ID
            video_title: Video title
            channel_id: YouTube channel ID
            channel_name: Channel name
            video_type: Type of video ('video', 'short', 'podcast')
            transcript: Video transcript
            vector_uuid: Base UUID for vector chunks
            chunk_count: Number of chunks created
            duration_seconds: Video duration in seconds
            published_at: Video publication date
            view_count: Number of views
            transcript_language: Transcript language code
            metadata: Additional metadata as JSON
        """
        transcript_hash = self.compute_transcript_hash(transcript)

        with get_data_db_session() as session:
            # Check if video already exists
            video_record = (
                session.query(YouTubeVideo)
                .filter(YouTubeVideo.youtube_video_id == youtube_video_id)
                .first()
            )

            if video_record:
                # Update existing record
                video_record.video_title = video_title
                video_record.transcript_hash = transcript_hash
                video_record.chunk_count = chunk_count
                video_record.duration_seconds = duration_seconds
                video_record.published_at = published_at
                video_record.view_count = view_count
                video_record.transcript_language = transcript_language
                video_record.extra_metadata = metadata
                video_record.ingestion_status = "success"
                video_record.error_message = None
            else:
                # Create new record
                video_record = YouTubeVideo(
                    youtube_video_id=youtube_video_id,
                    video_title=video_title,
                    channel_id=channel_id,
                    channel_name=channel_name,
                    video_type=video_type,
                    transcript_hash=transcript_hash,
                    vector_uuid=vector_uuid,
                    chunk_count=chunk_count,
                    duration_seconds=duration_seconds,
                    published_at=published_at,
                    view_count=view_count,
                    transcript_language=transcript_language,
                    extra_metadata=metadata,
                    ingestion_status="success",
                )
                session.add(video_record)

            session.commit()

    def get_video_info(self, youtube_video_id: str) -> dict[str, Any] | None:
        """
        Get stored information about an ingested video.

        Args:
            youtube_video_id: YouTube video ID

        Returns:
            Dictionary with video information, or None if not found
        """
        with get_data_db_session() as session:
            video_record = (
                session.query(YouTubeVideo)
                .filter(YouTubeVideo.youtube_video_id == youtube_video_id)
                .first()
            )

            if not video_record:
                return None

            return {
                "youtube_video_id": video_record.youtube_video_id,
                "video_title": video_record.video_title,
                "channel_id": video_record.channel_id,
                "channel_name": video_record.channel_name,
                "video_type": video_record.video_type,
                "transcript_hash": video_record.transcript_hash,
                "vector_uuid": video_record.vector_uuid,
                "chunk_count": video_record.chunk_count,
                "duration_seconds": video_record.duration_seconds,
                "published_at": video_record.published_at,
                "view_count": video_record.view_count,
                "transcript_language": video_record.transcript_language,
                "first_ingested_at": video_record.first_ingested_at,
                "last_ingested_at": video_record.last_ingested_at,
                "ingestion_status": video_record.ingestion_status,
                "metadata": video_record.extra_metadata,
            }
