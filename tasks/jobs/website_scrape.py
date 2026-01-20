"""Website scraping and indexing job for scheduled RAG updates."""

import logging
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from config.settings import TasksSettings

from .base_job import BaseJob

logger = logging.getLogger(__name__)


class WebsiteScrapeJob(BaseJob):
    """Job to scrape a website using sitemap and index into RAG system."""

    JOB_NAME = "Website Scraping"
    JOB_DESCRIPTION = "Scrape website content using sitemap.xml and index into RAG system for Q&A"
    REQUIRED_PARAMS = ["website_url"]
    OPTIONAL_PARAMS = [
        "sitemap_url",
        "max_pages",
        "include_patterns",
        "exclude_patterns",
        "metadata",
        "force_rescrape",  # Force rescrape even if content hasn't changed
    ]

    def __init__(self, settings: TasksSettings, **kwargs: Any):
        """Initialize the website scraping job."""
        super().__init__(settings, **kwargs)
        self.validate_params()

    def validate_params(self) -> bool:
        """Validate job parameters."""
        super().validate_params()

        # Validate website_url format
        website_url = self.params.get("website_url")
        if not website_url.startswith(("http://", "https://")):
            raise ValueError("website_url must start with http:// or https://")

        return True

    async def _fetch_sitemap(self, sitemap_url: str) -> list[str]:
        """Fetch and parse sitemap.xml to get list of URLs.

        Args:
            sitemap_url: URL to sitemap.xml

        Returns:
            List of page URLs from sitemap
        """
        logger.info(f"Fetching sitemap from: {sitemap_url}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(sitemap_url, follow_redirects=True)
                response.raise_for_status()
            except httpx.HTTPError as e:
                logger.error(f"Failed to fetch sitemap: {e}")
                return []

        # Parse XML sitemap
        soup = BeautifulSoup(response.content, "xml")
        urls = []

        # Handle standard sitemap format
        for loc in soup.find_all("loc"):
            url = loc.text.strip()
            if url:
                urls.append(url)

        # Handle sitemap index (sitemap of sitemaps)
        if not urls and soup.find_all("sitemap"):
            logger.info("Found sitemap index, fetching child sitemaps...")
            for sitemap_tag in soup.find_all("sitemap"):
                child_loc = sitemap_tag.find("loc")
                if child_loc:
                    child_urls = await self._fetch_sitemap(child_loc.text.strip())
                    urls.extend(child_urls)

        logger.info(f"Found {len(urls)} URLs in sitemap")
        return urls

    async def _scrape_page(self, url: str) -> dict[str, Any] | None:
        """Scrape a single page and extract text content.

        Args:
            url: URL to scrape

        Returns:
            Dict with content and metadata, or None if failed
        """
        logger.debug(f"Scraping page: {url}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
            except httpx.HTTPError as e:
                logger.warning(f"Failed to scrape {url}: {e}")
                return None

        # Parse HTML
        soup = BeautifulSoup(response.content, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        # Extract text content
        text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        text = "\n".join(line for line in lines if line)

        # Extract title
        title = soup.title.string if soup.title else urlparse(url).path

        # Extract meta description
        description = ""
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            description = meta_desc.get("content", "")

        return {
            "content": text,
            "title": title,
            "description": description,
            "url": url,
            "length": len(text),
        }

    def _filter_urls(
        self, urls: list[str], include_patterns: list[str], exclude_patterns: list[str]
    ) -> list[str]:
        """Filter URLs based on include/exclude patterns.

        Args:
            urls: List of URLs to filter
            include_patterns: List of URL patterns to include (substring match)
            exclude_patterns: List of URL patterns to exclude (substring match)

        Returns:
            Filtered list of URLs
        """
        filtered = urls

        # Apply include patterns
        if include_patterns:
            filtered = [
                url
                for url in filtered
                if any(pattern in url for pattern in include_patterns)
            ]

        # Apply exclude patterns
        if exclude_patterns:
            filtered = [
                url
                for url in filtered
                if not any(pattern in url for pattern in exclude_patterns)
            ]

        return filtered

    async def _execute_job(self) -> dict[str, Any]:
        """Execute the website scraping job."""
        # Import tracking service
        from services.web_page_tracking_service import WebPageTrackingService

        tracking_service = WebPageTrackingService()

        # Get job parameters
        website_url = self.params.get("website_url")
        sitemap_url = self.params.get("sitemap_url")
        max_pages = self.params.get("max_pages", 100)
        include_patterns = self.params.get("include_patterns", [])
        exclude_patterns = self.params.get("exclude_patterns", [])
        metadata = self.params.get("metadata", {})
        force_rescrape = self.params.get("force_rescrape", False)

        # Determine sitemap URL (try common locations if not provided)
        if not sitemap_url:
            base_url = website_url.rstrip("/")
            sitemap_url = f"{base_url}/sitemap.xml"
            logger.info(f"No sitemap_url provided, trying: {sitemap_url}")

        logger.info(
            f"Starting website scraping: url={website_url}, "
            f"sitemap={sitemap_url}, max_pages={max_pages}"
        )

        # Fetch sitemap URLs
        urls = await self._fetch_sitemap(sitemap_url)

        if not urls:
            # Try alternative sitemap locations
            logger.info("No URLs found in sitemap.xml, trying /sitemap_index.xml...")
            alternative_url = f"{website_url.rstrip('/')}/sitemap_index.xml"
            urls = await self._fetch_sitemap(alternative_url)

        if not urls:
            raise ValueError(
                f"No URLs found in sitemap. Tried {sitemap_url}. "
                "Please verify sitemap exists or provide sitemap_url parameter."
            )

        # Filter URLs
        if include_patterns or exclude_patterns:
            original_count = len(urls)
            urls = self._filter_urls(urls, include_patterns, exclude_patterns)
            logger.info(
                f"Filtered {original_count} URLs to {len(urls)} "
                f"(include={include_patterns}, exclude={exclude_patterns})"
            )

        # Limit number of pages
        if len(urls) > max_pages:
            logger.info(f"Limiting to {max_pages} pages (found {len(urls)})")
            urls = urls[:max_pages]

        # Check for pages to scrape vs skip
        domain = tracking_service.extract_domain(website_url)
        scraped_pages = []
        skipped_count = 0
        failed_count = 0

        for i, url in enumerate(urls, 1):
            # Check if page needs rescraping
            if not force_rescrape:
                needs_rescrape, existing_uuid = tracking_service.check_page_needs_rescrape(url)
                if not needs_rescrape:
                    logger.info(f"Skipping unchanged page {i}/{len(urls)}: {url}")
                    skipped_count += 1
                    continue

            logger.info(f"Scraping page {i}/{len(urls)}: {url}")
            page_data = await self._scrape_page(url)

            if page_data:
                scraped_pages.append(page_data)
            else:
                failed_count += 1

        logger.info(
            f"Scraped {len(scraped_pages)} new/changed pages, "
            f"skipped {skipped_count} unchanged, {failed_count} failed"
        )

        # Detect removed pages (in DB but not in sitemap)
        removed_count = 0
        if not force_rescrape:
            logger.info(f"Checking for removed pages on {domain}...")
            existing_pages = tracking_service.get_pages_by_domain(domain)
            sitemap_urls_set = set(urls)

            for existing_page in existing_pages:
                if existing_page["url"] not in sitemap_urls_set:
                    logger.info(f"Page removed from sitemap: {existing_page['url']}")
                    # Mark as removed (will be deleted from vector DB below)
                    tracking_service.record_page_scrape(
                        url=existing_page["url"],
                        page_title=existing_page.get("page_title"),
                        content="",  # Empty content for removed page
                        vector_uuid=existing_page.get("vector_uuid", ""),
                        chunk_count=0,
                        status="removed",
                        error_message="Page no longer in sitemap"
                    )
                    removed_count += 1

            if removed_count > 0:
                logger.info(f"Marked {removed_count} pages as removed")

        # Index into RAG system
        from services.rag_client import RAGIngestClient

        rag_client = RAGIngestClient(
            base_url=self.settings.rag_service_url,
            service_token=self.settings.bot_service_token,
        )

        # Prepare documents for ingestion and track them
        documents = []
        for page in scraped_pages:
            # Generate deterministic UUID for this page
            vector_uuid = tracking_service.generate_base_uuid(page["url"])

            # Add custom metadata
            doc_metadata = {
                "source": "website_scrape",
                "url": page["url"],
                "title": page["title"],
                "description": page["description"],
                "website": website_url,
                "vector_uuid": vector_uuid,
                **metadata,  # Include any custom metadata from job params
            }

            documents.append({"content": page["content"], "metadata": doc_metadata})

        # Ingest documents
        logger.info(f"Ingesting {len(documents)} documents into RAG system...")
        ingest_result = await rag_client.ingest_documents(documents)

        logger.info(
            f"Ingestion complete: {ingest_result.get('success_count', 0)} success, "
            f"{ingest_result.get('error_count', 0)} errors"
        )

        # Record successful scrapes in tracking table
        for i, page in enumerate(scraped_pages):
            try:
                vector_uuid = documents[i]["metadata"]["vector_uuid"]
                tracking_service.record_page_scrape(
                    url=page["url"],
                    page_title=page["title"],
                    content=page["content"],
                    vector_uuid=vector_uuid,
                    chunk_count=1,  # Single chunk for now (RAG service handles chunking)
                    metadata=documents[i]["metadata"],
                    status="success",
                )
            except Exception as tracking_error:
                logger.warning(f"Failed to record tracking for {page['url']}: {tracking_error}")
                # Don't fail entire job on tracking errors

        # Return result summary
        return {
            "success": True,
            "message": f"Scraped {len(scraped_pages)} new/changed pages, skipped {skipped_count} unchanged, removed {removed_count} obsolete",
            "website_url": website_url,
            "sitemap_url": sitemap_url,
            "pages_scraped": len(scraped_pages),
            "pages_skipped": skipped_count,
            "pages_removed": removed_count,
            "pages_failed": failed_count,
            "pages_indexed": ingest_result.get("success_count", 0),
            "index_errors": ingest_result.get("error_count", 0),
            "force_rescrape": force_rescrape,
            "details": {
                "total_urls_in_sitemap": len(urls),
                "urls_filtered_out": len(urls) - len(scraped_pages) - skipped_count - failed_count,
                "sample_scraped": [page["url"] for page in scraped_pages[:5]],
                "change_detection_enabled": not force_rescrape,
            },
        }
