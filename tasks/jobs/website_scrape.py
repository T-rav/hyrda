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
        # Get job parameters
        website_url = self.params.get("website_url")
        sitemap_url = self.params.get("sitemap_url")
        max_pages = self.params.get("max_pages", 100)
        include_patterns = self.params.get("include_patterns", [])
        exclude_patterns = self.params.get("exclude_patterns", [])
        metadata = self.params.get("metadata", {})

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

        # Scrape all pages
        scraped_pages = []
        failed_count = 0

        for i, url in enumerate(urls, 1):
            logger.info(f"Scraping page {i}/{len(urls)}: {url}")
            page_data = await self._scrape_page(url)

            if page_data:
                scraped_pages.append(page_data)
            else:
                failed_count += 1

        logger.info(
            f"Scraped {len(scraped_pages)} pages successfully, {failed_count} failed"
        )

        # Index into RAG system
        from services.rag_client import RAGIngestClient

        rag_client = RAGIngestClient(
            base_url=self.settings.rag_service_url,
            service_token=self.settings.bot_service_token,
        )

        # Prepare documents for ingestion
        documents = []
        for page in scraped_pages:
            # Add custom metadata
            doc_metadata = {
                "source": "website_scrape",
                "url": page["url"],
                "title": page["title"],
                "description": page["description"],
                "website": website_url,
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

        # Return result summary
        return {
            "success": True,
            "message": f"Successfully scraped and indexed {len(scraped_pages)} pages",
            "website_url": website_url,
            "sitemap_url": sitemap_url,
            "pages_scraped": len(scraped_pages),
            "pages_failed": failed_count,
            "pages_indexed": ingest_result.get("success_count", 0),
            "index_errors": ingest_result.get("error_count", 0),
            "details": {
                "total_urls_found": len(urls),
                "urls_filtered": len(urls) - len(scraped_pages) - failed_count,
                "sample_pages": [page["url"] for page in scraped_pages[:5]],
            },
        }
