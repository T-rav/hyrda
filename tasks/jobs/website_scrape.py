"""Website scraping and indexing job for scheduled RAG updates."""

import logging
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from config.settings import TasksSettings
from services.openai_embeddings import OpenAIEmbeddings
from services.qdrant_client import QdrantClient

from .base_job import BaseJob

logger = logging.getLogger(__name__)


class WebsiteScrapeJob(BaseJob):
    """Job to scrape a website using sitemap and index into RAG system."""

    JOB_NAME = "Website Scraping"
    JOB_DESCRIPTION = (
        "Scrape website content using sitemap.xml and index into RAG system for Q&A"
    )
    REQUIRED_PARAMS = ["website_url"]
    OPTIONAL_PARAMS = [
        "sitemap_url",
        "max_pages",
        "include_patterns",
        "exclude_patterns",
        "metadata",
        "force_rescrape",  # Force rescrape even if content hasn't changed
        "credential_id",  # OAuth credential for authenticated scraping (e.g. Google Sites)
    ]

    def __init__(self, settings: TasksSettings, **kwargs: Any):
        """Initialize the website scraping job."""
        super().__init__(settings, **kwargs)

        # Initialize embedding and vector clients for direct Qdrant access
        self.embedding_client = OpenAIEmbeddings()
        self.vector_client = QdrantClient()

        self.validate_params()

    def validate_params(self) -> bool:
        """Validate job parameters."""
        super().validate_params()

        # Validate website_url format
        website_url = self.params.get("website_url")
        if not website_url.startswith(("http://", "https://")):
            raise ValueError("website_url must start with http:// or https://")

        return True

    async def _fetch_sitemap(
        self, sitemap_url: str, auth_headers: dict[str, str] | None = None
    ) -> list[str]:
        """Fetch and parse sitemap.xml to get list of URLs.

        Args:
            sitemap_url: URL to sitemap.xml
            auth_headers: Optional authentication headers (e.g. OAuth Bearer token)

        Returns:
            List of page URLs from sitemap
        """
        logger.info(f"Fetching sitemap from: {sitemap_url}")

        # Use system CA bundle for SSL verification
        import ssl

        ssl_context = ssl.create_default_context()
        ssl_context.load_verify_locations("/etc/ssl/certs/ca-certificates.crt")

        # Include auth headers if provided
        headers = auth_headers or {}

        async with httpx.AsyncClient(
            timeout=30.0, verify=ssl_context, headers=headers
        ) as client:
            try:
                response = await client.get(sitemap_url, follow_redirects=True)
                response.raise_for_status()
            except httpx.HTTPError as e:
                logger.error(f"Failed to fetch sitemap: {e}")
                return []

        # Parse XML sitemap
        soup = BeautifulSoup(response.content, "xml")
        urls = []

        # Check if this is a sitemap index (contains <sitemap> tags)
        sitemap_tags = soup.find_all("sitemap")

        if sitemap_tags:
            # This is a sitemap index - recursively fetch child sitemaps
            logger.info(f"Found sitemap index with {len(sitemap_tags)} child sitemaps")
            for sitemap_tag in sitemap_tags:
                child_loc = sitemap_tag.find("loc")
                if child_loc:
                    child_sitemap_url = child_loc.text.strip()
                    logger.debug(f"Fetching child sitemap: {child_sitemap_url}")
                    child_urls = await self._fetch_sitemap(
                        child_sitemap_url, auth_headers
                    )
                    urls.extend(child_urls)
        else:
            # This is a regular sitemap with content URLs
            for loc in soup.find_all("loc"):
                url = loc.text.strip()
                if url:
                    # Filter out sitemap XML files - only keep actual content pages
                    if not url.endswith(".xml"):
                        urls.append(url)
                    else:
                        logger.debug(f"Skipping sitemap file: {url}")

        logger.info(f"Found {len(urls)} content URLs in sitemap")
        return urls

    async def _scrape_page(
        self, url: str, auth_headers: dict[str, str] | None = None
    ) -> dict[str, Any] | None:
        """Scrape a single page and extract text content.

        Args:
            url: URL to scrape
            auth_headers: Optional authentication headers (e.g. OAuth Bearer token)

        Returns:
            Dict with content and metadata, or None if failed
        """
        logger.debug(f"Scraping page: {url}")

        # Use system CA bundle for SSL verification
        import ssl

        ssl_context = ssl.create_default_context()
        ssl_context.load_verify_locations("/etc/ssl/certs/ca-certificates.crt")

        # Include auth headers if provided
        headers = auth_headers or {}

        async with httpx.AsyncClient(
            timeout=30.0, verify=ssl_context, headers=headers
        ) as client:
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

    async def _crawl_site(
        self,
        start_url: str,
        max_pages: int | None,
        include_patterns: list[str],
        exclude_patterns: list[str],
        auth_headers: dict[str, str] | None = None,
    ) -> list[str]:
        """Crawl website by following internal links (fallback when no sitemap).

        Uses Crawlee library for robust web crawling with automatic link discovery.

        Args:
            start_url: Starting URL to crawl from
            max_pages: Maximum number of pages to discover (None = unlimited)
            include_patterns: URL patterns to include
            exclude_patterns: URL patterns to exclude
            auth_headers: Optional authentication headers

        Returns:
            List of discovered page URLs
        """
        from crawlee.beautifulsoup_crawler import (
            BeautifulSoupCrawler,
            BeautifulSoupCrawlingContext,
        )

        logger.info(f"No sitemap found, crawling site starting from: {start_url}")

        # Track discovered URLs
        discovered_urls = []

        async def request_handler(context: BeautifulSoupCrawlingContext) -> None:
            """Handle each crawled page."""
            url = context.request.url

            # Apply include/exclude patterns
            if include_patterns and not any(
                pattern in url for pattern in include_patterns
            ):
                logger.debug(f"Skipping (no match): {url}")
                return

            if exclude_patterns and any(pattern in url for pattern in exclude_patterns):
                logger.debug(f"Skipping (excluded): {url}")
                return

            # Add to discovered list
            discovered_urls.append(url)
            logger.debug(
                f"Discovered: {url} ({len(discovered_urls)}/{max_pages or 'unlimited'})"
            )

            # Enqueue links from this page (Crawlee handles deduplication)
            await context.enqueue_links(
                strategy="same-domain",  # Only follow links on same domain
            )

        # Create crawler with custom configuration
        crawler = BeautifulSoupCrawler(
            max_requests_per_crawl=max_pages,  # Limit total pages
            max_request_retries=2,
            request_handler=request_handler,
        )

        # Add custom headers if OAuth token provided
        if auth_headers:
            # Crawlee will use these headers for all requests
            crawler._http_client.headers.update(auth_headers)

        # Run the crawler
        try:
            await crawler.run([start_url])
        except Exception as e:
            logger.error(f"Crawler error: {e}")

        logger.info(f"Crawling complete: discovered {len(discovered_urls)} pages")
        return discovered_urls

    async def _execute_job(self) -> dict[str, Any]:
        """Execute the website scraping job."""
        # Import tracking service
        from services.web_page_tracking_service import WebPageTrackingService

        tracking_service = WebPageTrackingService()

        # Initialize vector client before use
        logger.info("Initializing vector database connection...")
        await self.vector_client.initialize()

        # Get job parameters
        website_url = self.params.get("website_url")
        sitemap_url = self.params.get("sitemap_url")
        max_pages = self.params.get("max_pages", None)  # None = unlimited
        include_patterns = self.params.get("include_patterns", [])
        exclude_patterns = self.params.get("exclude_patterns", [])
        metadata = self.params.get("metadata", {})
        force_rescrape = self.params.get("force_rescrape", False)
        credential_id = self.params.get("credential_id")

        # Load OAuth credential if provided (for authenticated scraping)
        auth_headers = {}
        if credential_id:
            logger.info(f"Loading OAuth credential: {credential_id}")
            try:
                from models.base import get_db_session
                from models.oauth_credential import OAuthCredential
                from services.encryption_service import get_encryption_service

                encryption_service = get_encryption_service()

                with get_db_session() as db_session:
                    credential = (
                        db_session.query(OAuthCredential)
                        .filter(OAuthCredential.credential_id == credential_id)
                        .first()
                    )

                    if not credential:
                        raise FileNotFoundError(
                            f"Credential not found in database: {credential_id}"
                        )

                    # Decrypt token
                    token_json = encryption_service.decrypt(credential.encrypted_token)

                    # Check if token needs refresh
                    import json
                    from datetime import UTC, datetime, timedelta

                    from google.auth.transport.requests import Request
                    from google.oauth2.credentials import Credentials

                    token_data = json.loads(token_json)
                    should_refresh = False

                    # Check token expiry
                    if token_data.get("expiry"):
                        try:
                            expiry = datetime.fromisoformat(
                                token_data["expiry"].replace("Z", "+00:00")
                            )
                            now = datetime.now(UTC)
                            # Refresh if expired or expiring within 5 minutes
                            if expiry <= now + timedelta(minutes=5):
                                should_refresh = True
                                logger.info(
                                    f"Token expired or expiring soon for {credential_id}, refreshing..."
                                )
                        except Exception as e:
                            logger.warning(f"Could not parse token expiry: {e}")

                    # Refresh token if needed
                    if should_refresh and token_data.get("refresh_token"):
                        try:
                            creds = Credentials.from_authorized_user_info(token_data)
                            creds.refresh(Request())

                            # Update token in database
                            new_token_json = creds.to_json()
                            new_encrypted_token = encryption_service.encrypt(
                                new_token_json
                            )

                            new_token_data = json.loads(new_token_json)
                            new_token_metadata = {
                                "scopes": new_token_data.get("scopes", []),
                                "token_uri": new_token_data.get("token_uri"),
                                "expiry": new_token_data.get("expiry"),
                            }

                            credential.encrypted_token = new_encrypted_token
                            credential.token_metadata = new_token_metadata
                            logger.info(
                                f"Token refreshed successfully for {credential_id}"
                            )

                            # Use the new token
                            token_json = new_token_json
                        except Exception as e:
                            logger.error(f"Token refresh failed: {e}")

                    # Update last_used_at
                    credential.last_used_at = datetime.now(UTC)
                    db_session.commit()

                # Extract access token for Authorization header
                token_data = json.loads(token_json)
                access_token = token_data.get("token")
                if access_token:
                    auth_headers = {"Authorization": f"Bearer {access_token}"}
                    logger.info("OAuth authentication enabled for scraping")
                else:
                    logger.warning("No access token found in credential")

            except Exception as e:
                logger.error(f"Failed to load OAuth credential: {e}")
                raise ValueError(f"OAuth credential loading failed: {e}") from e

        # Determine sitemap URL (try common locations if not provided)
        if not sitemap_url:
            base_url = website_url.rstrip("/")
            sitemap_url = f"{base_url}/sitemap.xml"
            logger.info(f"No sitemap_url provided, trying: {sitemap_url}")

        logger.info(
            f"Starting website scraping: url={website_url}, "
            f"sitemap={sitemap_url}, max_pages={max_pages or 'unlimited'}"
        )

        # Fetch sitemap URLs
        urls = await self._fetch_sitemap(sitemap_url, auth_headers)

        if not urls:
            # Try alternative sitemap locations
            logger.info("No URLs found in sitemap.xml, trying /sitemap_index.xml...")
            alternative_url = f"{website_url.rstrip('/')}/sitemap_index.xml"
            urls = await self._fetch_sitemap(alternative_url, auth_headers)

        # If no sitemap found, fall back to manual crawling
        if not urls:
            logger.info(
                "No sitemap found, falling back to manual site crawling from base URL"
            )
            # website_url is guaranteed to be a string by validate_params()
            urls = await self._crawl_site(
                start_url=str(website_url),
                max_pages=max_pages,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
                auth_headers=auth_headers,
            )

            if not urls:
                raise ValueError(
                    f"No pages discovered. Could not find sitemap at {sitemap_url} "
                    f"and manual crawling from {website_url} found no pages."
                )

        # Filter URLs
        if include_patterns or exclude_patterns:
            original_count = len(urls)
            urls = self._filter_urls(urls, include_patterns, exclude_patterns)
            logger.info(
                f"Filtered {original_count} URLs to {len(urls)} "
                f"(include={include_patterns}, exclude={exclude_patterns})"
            )

        # Limit number of pages (if max_pages is specified)
        if max_pages is not None and len(urls) > max_pages:
            logger.info(f"Limiting to {max_pages} pages (found {len(urls)})")
            urls = urls[:max_pages]
        else:
            logger.info(f"Processing all {len(urls)} URLs from sitemap (no limit)")

        # Check for pages to scrape vs skip
        domain = tracking_service.extract_domain(website_url)
        scraped_pages = []
        skipped_count = 0
        failed_count = 0

        for i, url in enumerate(urls, 1):
            # Check if page needs rescraping
            if not force_rescrape:
                needs_rescrape, existing_uuid = (
                    tracking_service.check_page_needs_rescrape(url)
                )
                if not needs_rescrape:
                    logger.info(f"Skipping unchanged page {i}/{len(urls)}: {url}")
                    skipped_count += 1
                    continue

            logger.info(f"Scraping page {i}/{len(urls)}: {url}")
            page_data = await self._scrape_page(url, auth_headers)

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
                        error_message="Page no longer in sitemap",
                    )
                    removed_count += 1

            if removed_count > 0:
                logger.info(f"Marked {removed_count} pages as removed")

        # Index into Qdrant (direct vector database access like other jobs)
        texts = []
        metadata_list = []
        vector_ids = []
        page_chunk_counts = []  # Track chunks per page for recording

        for page in scraped_pages:
            # Generate deterministic UUID for this page
            vector_uuid = tracking_service.generate_base_uuid(page["url"])

            # Chunk the content to avoid token limit errors
            # Using same settings as Google Drive ingestion
            chunks = self.embedding_client.chunk_text(
                page["content"], chunk_size=2000, chunk_overlap=200
            )

            # If content is empty or very small, create at least one chunk
            if not chunks:
                chunks = [page["content"] or ""]

            page_chunk_counts.append(len(chunks))
            logger.debug(
                f"Split {page['url']} into {len(chunks)} chunks "
                f"({len(page['content'])} chars)"
            )

            # Create a chunk for each piece of content
            for i, chunk in enumerate(chunks):
                # Add page title/URL context to each chunk
                chunk_with_context = f"[{page['title']}]\n{page['url']}\n\n{chunk}"

                # Add chunk metadata
                doc_metadata = {
                    "source": "website_scrape",
                    "url": page["url"],
                    "title": page["title"],
                    "description": page["description"],
                    "website": website_url,
                    "vector_uuid": vector_uuid,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    **metadata,  # Include any custom metadata from job params
                }

                texts.append(chunk_with_context)
                metadata_list.append(doc_metadata)

                # Generate unique ID for this chunk
                import uuid as uuid_lib

                chunk_id = str(uuid_lib.uuid5(uuid_lib.UUID(vector_uuid), f"chunk_{i}"))
                vector_ids.append(chunk_id)

        # Generate embeddings and upsert to Qdrant
        logger.info(
            f"Generating embeddings for {len(texts)} chunks from {len(scraped_pages)} pages..."
        )
        embeddings = self.embedding_client.embed_batch(texts)

        logger.info(f"Upserting {len(texts)} documents to Qdrant...")
        await self.vector_client.upsert_with_namespace(
            texts, embeddings, metadata_list, namespace="website_scrape"
        )

        success_count = len(texts)
        error_count = 0

        logger.info(
            f"Ingestion complete: {success_count} success, {error_count} errors"
        )

        # Record successful scrapes in tracking table
        for i, page in enumerate(scraped_pages):
            try:
                vector_uuid = tracking_service.generate_base_uuid(page["url"])
                tracking_service.record_page_scrape(
                    url=page["url"],
                    page_title=page["title"],
                    content=page["content"],
                    vector_uuid=vector_uuid,
                    chunk_count=page_chunk_counts[i],  # Actual chunk count
                    metadata={
                        "source": "website_scrape",
                        "url": page["url"],
                        "title": page["title"],
                        "description": page["description"],
                        "website": website_url,
                    },
                    status="success",
                )
            except Exception as tracking_error:
                logger.warning(
                    f"Failed to record tracking for {page['url']}: {tracking_error}"
                )
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
            "pages_indexed": success_count,
            "index_errors": error_count,
            "force_rescrape": force_rescrape,
            "details": {
                "total_urls_in_sitemap": len(urls),
                "urls_filtered_out": len(urls)
                - len(scraped_pages)
                - skipped_count
                - failed_count,
                "sample_scraped": [page["url"] for page in scraped_pages[:5]],
                "change_detection_enabled": not force_rescrape,
            },
        }
