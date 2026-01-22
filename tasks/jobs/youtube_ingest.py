"""YouTube channel ingestion job for scheduled RAG updates."""

import logging
import time
from typing import Any

from config.settings import TasksSettings

from .base_job import BaseJob

logger = logging.getLogger(__name__)


class YouTubeIngestJob(BaseJob):
    """Job to ingest videos from YouTube channel into RAG system."""

    JOB_NAME = "YouTube Channel Ingestion"
    JOB_DESCRIPTION = "Ingest videos from YouTube channel into RAG system with audio transcription (yt-dlp + Whisper)"
    REQUIRED_PARAMS = ["channel_url"]
    OPTIONAL_PARAMS = [
        "include_videos",
        "include_shorts",
        "include_podcasts",
        "max_videos",
        "metadata",
    ]

    def __init__(self, settings: TasksSettings, **kwargs: Any):
        """Initialize the YouTube ingestion job."""
        super().__init__(settings, **kwargs)
        self.validate_params()

    def validate_params(self) -> bool:
        """Validate job parameters."""
        super().validate_params()

        # Validate channel_url
        channel_url = self.params.get("channel_url")
        if not channel_url:
            raise ValueError("Must provide 'channel_url' parameter")

        # Validate at least one video type is selected
        include_videos = self.params.get("include_videos", True)
        include_shorts = self.params.get("include_shorts", False)
        include_podcasts = self.params.get("include_podcasts", False)

        if not (include_videos or include_shorts or include_podcasts):
            raise ValueError(
                "Must include at least one video type (videos, shorts, or podcasts)"
            )

        return True

    async def _execute_job(self) -> dict[str, Any]:
        """Execute the YouTube ingestion job."""
        # Get job parameters
        channel_url = self.params.get("channel_url")
        include_videos = self.params.get("include_videos", True)
        include_shorts = self.params.get("include_shorts", False)
        include_podcasts = self.params.get("include_podcasts", False)
        max_videos = self.params.get("max_videos")
        metadata = self.params.get("metadata", {})

        logger.info(
            f"Starting YouTube ingestion: "
            f"channel={channel_url}, "
            f"videos={include_videos}, shorts={include_shorts}, podcasts={include_podcasts}"
        )

        try:
            # Import services
            import os

            from services.openai_embeddings import OpenAIEmbeddings
            from services.qdrant_client import QdrantClient
            from services.youtube import YouTubeClient, YouTubeTrackingService

            # Get OpenAI API key from environment (only key needed!)
            openai_api_key = os.getenv("OPENAI_API_KEY")

            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY environment variable is required")

            # Initialize services (no YouTube API key needed!)
            youtube_client = YouTubeClient(openai_api_key=openai_api_key)
            tracking_service = YouTubeTrackingService()

            # Initialize vector and embedding services
            logger.info("Initializing vector database and embedding service...")
            embedding_provider = OpenAIEmbeddings()
            vector_store = QdrantClient()
            await vector_store.initialize()

            # Get channel info using yt-dlp
            channel_info = youtube_client.get_channel_info(channel_url)
            if not channel_info:
                raise ValueError(f"Could not find channel: {channel_url}")

            logger.info(f"Processing channel: {channel_info['channel_name']}")

            # List videos from channel using yt-dlp
            videos = youtube_client.list_channel_videos(
                channel_url=channel_url,
                include_videos=include_videos,
                include_shorts=include_shorts,
                include_podcasts=include_podcasts,
                max_results=max_videos,
            )

            logger.info(f"Found {len(videos)} videos to process")

            success_count = 0
            error_count = 0
            skipped_count = 0

            for video in videos:
                video_id = video["video_id"]
                video_title = video["title"]
                max_attempts = 5
                attempt = 0
                success = False

                while attempt < max_attempts and not success:
                    try:
                        attempt += 1
                        if attempt > 1:
                            backoff_seconds = 2 ** (attempt - 1)
                            logger.info(
                                f"Retry attempt {attempt}/{max_attempts} for {video_title} "
                                f"(waiting {backoff_seconds}s)"
                            )
                            time.sleep(backoff_seconds)

                        logger.info(f"Processing: {video_title}")

                        # Get video transcript (download audio + transcribe)
                        video_with_transcript = (
                            youtube_client.get_video_info_with_transcript(video_id)
                        )

                        if not video_with_transcript or not video_with_transcript.get(
                            "transcript"
                        ):
                            logger.warning(
                                f"Skipping {video_title} - transcription failed "
                                f"(attempt {attempt}/{max_attempts})"
                            )
                            if attempt >= max_attempts:
                                error_count += 1
                                break
                            continue

                        transcript = video_with_transcript["transcript"]

                        # Check if video needs reindexing
                        needs_reindex, existing_uuid = (
                            tracking_service.check_video_needs_reindex(
                                video_id, transcript
                            )
                        )

                        if not needs_reindex:
                            logger.info(f"⏭️  Skipping (unchanged): {video_title}")
                            skipped_count += 1
                            success = True  # Mark as success to exit retry loop
                            break

                        if existing_uuid:
                            logger.info(f"🔄 Transcript changed, reindexing: {video_title}")

                        # Generate or reuse UUID
                        base_uuid = existing_uuid or tracking_service.generate_base_uuid(
                            video_id
                        )

                        # Chunk transcript
                        chunks = embedding_provider.chunk_text(
                            transcript, chunk_size=512, chunk_overlap=50
                        )

                        # Create metadata for each chunk
                        chunk_metadata_list = []
                        for i, _chunk in enumerate(chunks):
                            chunk_metadata = {
                                "youtube_video_id": video_id,
                                "video_title": video_title,
                                "channel_id": channel_info["channel_id"],
                                "channel_name": channel_info["channel_name"],
                                "video_type": video_with_transcript["video_type"],
                                "duration_seconds": video_with_transcript[
                                    "duration_seconds"
                                ],
                                "published_at": video_with_transcript[
                                    "published_at"
                                ].isoformat()
                                if video_with_transcript.get("published_at")
                                else None,
                                "view_count": video_with_transcript["view_count"],
                                "chunk_index": i,
                                "chunk_count": len(chunks),
                                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                                "namespace": "youtube",
                                **metadata,
                            }
                            chunk_metadata_list.append(chunk_metadata)

                        # Embed chunks
                        embeddings = await embedding_provider.embed_texts(chunks)

                        # Create chunk IDs (stored in metadata for tracking)
                        chunk_ids = [f"{base_uuid}_{i}" for i in range(len(chunks))]

                        # Add chunk_id to metadata for each chunk
                        for i, meta in enumerate(chunk_metadata_list):
                            meta["chunk_id"] = chunk_ids[i]

                        # Upsert to vector store
                        await vector_store.upsert_with_namespace(
                            texts=chunks,
                            embeddings=embeddings,
                            metadata=chunk_metadata_list,
                            namespace="youtube",
                        )

                        # Record ingestion in tracking database
                        tracking_service.record_video_ingestion(
                            youtube_video_id=video_id,
                            video_title=video_title,
                            channel_id=channel_info["channel_id"],
                            channel_name=channel_info["channel_name"],
                            video_type=video_with_transcript["video_type"],
                            transcript=transcript,
                            vector_uuid=base_uuid,
                            chunk_count=len(chunks),
                            duration_seconds=video_with_transcript["duration_seconds"],
                            published_at=video_with_transcript.get("published_at"),
                            view_count=video_with_transcript["view_count"],
                            transcript_language="en",
                            metadata=chunk_metadata_list[0],
                        )

                        success_count += 1
                        logger.info(f"✅ Ingested: {video_title} ({len(chunks)} chunks)")
                        success = True  # Mark as success to exit retry loop

                    except Exception as e:
                        logger.error(
                            f"Error processing video {video_title} "
                            f"(attempt {attempt}/{max_attempts}): {e}"
                        )
                        if attempt >= max_attempts:
                            logger.error(
                                f"❌ Failed after {max_attempts} attempts: {video_title}"
                            )
                            error_count += 1

            processed_count = success_count + error_count + skipped_count

            logger.info(
                f"YouTube ingestion completed: "
                f"success={success_count}, skipped={skipped_count}, errors={error_count}"
            )

            return {
                # Standardized fields for task run tracking
                "records_processed": processed_count,
                "records_success": success_count,
                "records_failed": error_count,
                # Job-specific details
                "records_skipped": skipped_count,
                "channel_url": channel_url,
                "channel_name": channel_info["channel_name"],
                "channel_id": channel_info["channel_id"],
                "include_videos": include_videos,
                "include_shorts": include_shorts,
                "include_podcasts": include_podcasts,
                "metadata": metadata,
            }

        except Exception as e:
            logger.error(f"Error in YouTube ingestion: {str(e)}")
            raise
