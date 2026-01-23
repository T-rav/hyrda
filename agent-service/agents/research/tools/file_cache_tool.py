"""File cache tools for research agent."""

import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from ..services.file_cache import ResearchFileCache

logger = logging.getLogger(__name__)


class CacheFileInput(BaseModel):
    """Input for caching a file."""

    file_type: str = Field(
        description='File type: "sec_filing", "web_page", "pdf", or "json_data"'
    )
    content: str = Field(
        min_length=10,
        description="File content to cache (text or JSON string)",
    )
    company: str | None = Field(
        default=None,
        description="Company name (for sec_filing type)",
    )
    url: str | None = Field(
        default=None,
        description="Source URL (for web_page type)",
    )
    title: str | None = Field(
        default=None,
        description="Document title",
    )
    source: str | None = Field(
        default=None,
        description="Source identifier (e.g., 'arxiv', 'sec', 'google')",
    )


class RetrieveCacheInput(BaseModel):
    """Input for retrieving cached files."""

    query: str = Field(
        min_length=3,
        description="Search query to find cached files (matches filenames)",
    )
    file_type: str | None = Field(
        default=None,
        description='Optional filter by type: "sec_filing", "web_page", "pdf", "json_data"',
    )


class FileCacheTool(BaseTool):
    """Cache downloaded data to S3 storage with smart organization.

    Use this to store SEC filings, web pages, PDFs, and API responses
    for future reference. Files are organized by type with lifecycle policies.
    """

    name: str = "cache_file"
    description: str = (
        "Cache downloaded data (SEC filings, web pages, PDFs, JSON) to S3 storage. "
        "Files are automatically organized by type and source with smart naming. "
        "30-day lifecycle policy automatically cleans up old files. "
        "Returns cache location and file ID."
    )
    args_schema: type[BaseModel] = CacheFileInput

    file_cache: ResearchFileCache

    class Config:
        """Config."""

        arbitrary_types_allowed = True

    def __init__(self, file_cache: ResearchFileCache, **kwargs: Any):
        """Initialize with file cache.

        Args:
            file_cache: Shared file cache instance
            **kwargs: Additional BaseTool arguments
        """
        kwargs["file_cache"] = file_cache
        super().__init__(**kwargs)

    def _run(
        self,
        file_type: str,
        content: str,
        company: str | None = None,
        url: str | None = None,
        title: str | None = None,
        source: str | None = None,
    ) -> str:
        """Cache file to S3.

        Args:
            file_type: Type of file
            content: File content
            company: Company name (for SEC filings)
            url: Source URL (for web pages)
            title: Document title
            source: Source identifier

        Returns:
            Success message with S3 path
        """
        try:
            # Build metadata dict
            metadata = {}
            if company:
                metadata["company"] = company
            if url:
                metadata["url"] = url
            if title:
                metadata["title"] = title
            if source:
                metadata["source"] = source

            # Cache file
            cached_file = self.file_cache.cache_file(file_type, content, metadata)

            return (
                f"✅ Cached {file_type} to {cached_file.file_path}\n"
                f"File ID: {cached_file.file_id}\n"
                f"Size: {cached_file.size_bytes} bytes\n"
                f"Will auto-delete after 30 days"
            )
        except Exception as e:
            logger.error(f"Error caching file: {e}")
            return f"❌ Error caching file: {str(e)}"


class RetrieveCacheTool(BaseTool):
    """Search and retrieve previously cached files.

    Use this to find and reuse cached SEC filings, web pages, or other data
    instead of re-downloading.
    """

    name: str = "retrieve_cache"
    description: str = (
        "Search cached files by query and optionally filter by type. "
        "Returns list of matching files with their S3 paths and metadata. "
        "Use this to check if data was already downloaded before fetching again."
    )
    args_schema: type[BaseModel] = RetrieveCacheInput

    file_cache: ResearchFileCache

    class Config:
        """Config."""

        arbitrary_types_allowed = True

    def __init__(self, file_cache: ResearchFileCache, **kwargs: Any):
        """Initialize with file cache.

        Args:
            file_cache: Shared file cache instance
            **kwargs: Additional BaseTool arguments
        """
        kwargs["file_cache"] = file_cache
        super().__init__(**kwargs)

    def _run(self, query: str, file_type: str | None = None) -> str:
        """Search cached files.

        Args:
            query: Search query
            file_type: Optional type filter

        Returns:
            List of matching cached files
        """
        try:
            matches = self.file_cache.search_cache(query, file_type)

            if not matches:
                return f"No cached files found for query: {query}"

            # Format results
            results = [f"Found {len(matches)} cached file(s):\n"]
            for cached_file in matches[:10]:  # Limit to 10 results
                results.append(
                    f"\n📄 {cached_file.file_path}\n"
                    f"   Type: {cached_file.file_type}\n"
                    f"   Size: {cached_file.size_bytes} bytes\n"
                    f"   Cached: {cached_file.cached_at}\n"
                    f"   Metadata: {cached_file.metadata}"
                )

            if len(matches) > 10:
                results.append(f"\n... and {len(matches) - 10} more files")

            return "".join(results)
        except Exception as e:
            logger.error(f"Error searching cache: {e}")
            return f"❌ Error searching cache: {str(e)}"
