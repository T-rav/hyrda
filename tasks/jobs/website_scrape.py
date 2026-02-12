"""Website scraping and indexing job for scheduled RAG updates."""

import contextlib
import json
import logging
import re
import ssl
import uuid as uuid_lib
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from config.settings import TasksSettings
from models.base import get_db_session
from models.oauth_credential import OAuthCredential
from services.encryption_service import get_encryption_service
from services.openai_embeddings import OpenAIEmbeddings
from services.qdrant_client import QdrantClient
from services.web_page_tracking_service import WebPageTrackingService

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
        super().__init__(settings, **kwargs)

        self.embedding_client = OpenAIEmbeddings()
        self.vector_client = QdrantClient()

        self.validate_params()

    def validate_params(self) -> bool:
        super().validate_params()

        # Validate website_url format
        website_url = self.params.get("website_url")
        if not website_url or not website_url.startswith(("http://", "https://")):
            raise ValueError("website_url must start with http:// or https://")

        return True

    def _create_ssl_context(self) -> ssl.SSLContext:
        ssl_context = ssl.create_default_context()

        # Try to load system CA bundle (Linux path)
        # If it fails (e.g., on macOS), fall back to default system certs
        with contextlib.suppress(FileNotFoundError, PermissionError):
            ssl_context.load_verify_locations("/etc/ssl/certs/ca-certificates.crt")

        return ssl_context

    async def _fetch_sitemap(
        self, sitemap_url: str, auth_headers: dict[str, str] | None = None
    ) -> list[str]:
        logger.info(f"Fetching sitemap from: {sitemap_url}")

        # Use system CA bundle for SSL verification
        ssl_context = self._create_ssl_context()

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
        self,
        url: str,
        auth_headers: dict[str, str] | None = None,
        conditional_headers: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        logger.debug(f"Scraping page: {url}")

        # Use system CA bundle for SSL verification
        ssl_context = self._create_ssl_context()

        # Merge auth headers and conditional headers
        headers = {**(auth_headers or {}), **(conditional_headers or {})}

        async with httpx.AsyncClient(
            timeout=30.0, verify=ssl_context, headers=headers
        ) as client:
            try:
                response = await client.get(url, follow_redirects=True)

                # Handle 304 Not Modified - page unchanged!
                if response.status_code == 304:
                    logger.debug(f"Page not modified (304): {url}")
                    return {"not_modified": True, "url": url}

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

        # Extract HTTP caching headers for future conditional requests
        last_modified = response.headers.get("Last-Modified")
        etag = response.headers.get("ETag")

        return {
            "content": text,
            "title": title,
            "description": description,
            "url": url,
            "length": len(text),
            "last_modified": last_modified,
            "etag": etag,
        }

    def _filter_urls(
        self, urls: list[str], include_patterns: list[str], exclude_patterns: list[str]
    ) -> list[str]:
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

    def _extract_google_doc_id(self, url: str) -> tuple[str | None, str | None]:
        """
        Extract Google Workspace document ID and type from URL.

        Returns:
            Tuple of (document_id, doc_type) or (None, None) if not a Google doc
            doc_type can be: 'document', 'spreadsheets', 'presentation', 'file'
        """
        # Patterns for Google Workspace URLs
        patterns = [
            (r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)", "document"),
            (r"docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]+)", "spreadsheets"),
            (r"docs\.google\.com/presentation/d/([a-zA-Z0-9_-]+)", "presentation"),
            (r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)", "file"),
        ]

        for pattern, doc_type in patterns:
            match = re.search(pattern, url)
            if match:
                doc_id = match.group(1)
                logger.debug(f"Detected Google {doc_type}: {doc_id} from {url}")
                return doc_id, doc_type

        return None, None

    def _enqueue_google_doc_jobs(
        self, doc_ids: set[str], credential_id: str, metadata: dict | None = None
    ) -> tuple[int, int]:
        """
        Enqueue daily recurring jobs for discovered Google Docs.
        Checks if job already exists before creating to avoid duplicates.

        Args:
            doc_ids: Set of Google document IDs
            credential_id: OAuth credential ID to use for ingestion
            metadata: Additional metadata to add to documents

        Returns:
            Tuple of (created_count, skipped_count)
        """
        if not doc_ids:
            return 0, 0

        logger.info(
            f"Checking/enqueueing jobs for {len(doc_ids)} discovered Google Docs..."
        )

        from jobs.job_registry import get_job_registry

        job_registry = get_job_registry()
        created_count = 0
        skipped_count = 0

        # Get all existing jobs to check for duplicates
        existing_jobs = job_registry.scheduler_service.get_jobs()

        for doc_id in doc_ids:
            # Check if job already exists for this doc ID
            job_exists = False

            for job in existing_jobs:
                # Check if job ID matches this doc and file_id parameter matches
                if (
                    job.id
                    and doc_id in job.id
                    and "gdrive_ingest" in job.id
                    and hasattr(job, "kwargs")
                    and job.kwargs.get("params", {}).get("file_id") == doc_id
                ):
                    job_exists = True
                    logger.debug(
                        f"Job already exists for Google Doc {doc_id}, skipping"
                    )
                    skipped_count += 1
                    break

            if not job_exists:
                # Create new daily job for this doc
                job_params = {
                    "file_id": doc_id,
                    "credential_id": credential_id,
                    "metadata": {
                        **(metadata or {}),
                        "source": "website_scrape_auto_discovery",
                    },
                }

                schedule = {
                    "trigger": "interval",
                    "days": 1,  # Run once per day
                }

                try:
                    job_registry.create_job(
                        job_type="gdrive_ingest",
                        schedule=schedule,
                        params=job_params,
                    )
                    logger.info(f"📄 Created daily job for Google Doc: {doc_id}")
                    created_count += 1
                except Exception as e:
                    logger.error(f"Failed to create job for doc {doc_id}: {e}")

        return created_count, skipped_count

    async def _crawl_site(
        self,
        start_url: str,
        max_pages: int | None,
        include_patterns: list[str],
        exclude_patterns: list[str],
        auth_headers: dict[str, str] | None = None,
    ) -> list[str]:
        # Import Crawlee only when needed (avoids import at top level)
        import asyncio  # noqa: PLC0415

        from crawlee.crawlers import (  # noqa: PLC0415
            BeautifulSoupCrawler,
            BeautifulSoupCrawlingContext,
        )
        from crawlee.errors import SessionError  # noqa: PLC0415

        logger.info(f"No sitemap found, crawling site starting from: {start_url}")

        # Track discovered URLs
        discovered_urls = []

        # Track discovered Google Docs
        discovered_google_docs = set()

        # Track rate limit backoff
        rate_limit_backoff_count = 0
        backoff_delays = [60, 120, 180, 300, 600]  # 1min, 2min, 3min, 5min, 10min

        async def request_handler(context: BeautifulSoupCrawlingContext) -> None:
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

            # Check if this URL contains Google Docs links
            soup = context.soup
            if soup:
                # Find all links in the page
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    doc_id, doc_type = self._extract_google_doc_id(href)
                    if doc_id:
                        discovered_google_docs.add(doc_id)
                        logger.info(
                            f"📄 Found Google {doc_type}: {doc_id} on page {url}"
                        )

            # Enqueue links from this page (Crawlee handles deduplication)
            # Note: Auth headers need to be passed via user_data and then applied in request
            await context.enqueue_links(
                strategy="same-domain",  # Only follow links on same domain
            )

        async def error_handler(
            context: BeautifulSoupCrawlingContext, error: Exception
        ) -> None:
            """Handle errors including rate limiting with exponential backoff."""
            nonlocal rate_limit_backoff_count

            # Check if this is a rate limit error (HTTP 429)
            if isinstance(error, SessionError) and "429" in str(error):
                # Calculate backoff delay (use last delay if we've exhausted the list)
                delay_index = min(rate_limit_backoff_count, len(backoff_delays) - 1)
                delay_seconds = backoff_delays[delay_index]
                rate_limit_backoff_count += 1

                logger.warning(
                    f"⏳ Rate limited (429) - backing off for {delay_seconds}s "
                    f"(backoff #{rate_limit_backoff_count}): {context.request.url}"
                )

                # Wait for backoff period
                await asyncio.sleep(delay_seconds)

                # Re-enqueue the request to retry
                await context.add_requests([context.request.url])
                logger.info(f"Retrying after backoff: {context.request.url}")
            else:
                # For non-rate-limit errors, log and continue
                logger.error(f"Crawl error for {context.request.url}: {error}")

        # Configure crawler with auth headers baked into configuration
        if auth_headers:
            logger.info(
                "Configuring crawler with OAuth authentication for all requests"
            )

            # Create configuration dict with headers
            crawler_config = {
                "max_requests_per_crawl": max_pages,
                "max_request_retries": 5,
                "max_requests_per_minute": 30,
                "request_handler": request_handler,
                "error_handler": error_handler,
                # Configure default headers for all requests
                "additional_http_headers": auth_headers,
            }

            crawler = BeautifulSoupCrawler(**crawler_config)
        else:
            crawler = BeautifulSoupCrawler(
                max_requests_per_crawl=max_pages,
                max_request_retries=5,
                max_requests_per_minute=30,
                request_handler=request_handler,
                error_handler=error_handler,
            )

        # Run crawler
        try:
            await crawler.run([start_url])
        except Exception as e:
            logger.error(f"Crawler error: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")

        logger.info(
            f"Crawling complete: discovered {len(discovered_urls)} pages, "
            f"{len(discovered_google_docs)} Google Docs"
        )
        return discovered_urls, discovered_google_docs

    async def _execute_job(self) -> dict[str, Any]:
        tracking_service = WebPageTrackingService()

        logger.info("Initializing vector database connection...")
        await self.vector_client.initialize()

        website_url = self.params.get("website_url")
        sitemap_url = self.params.get("sitemap_url")
        max_pages = self.params.get("max_pages", None)  # None = unlimited
        include_patterns = self.params.get("include_patterns", [])
        exclude_patterns = self.params.get("exclude_patterns", [])
        metadata = self.params.get("metadata", {})
        force_rescrape = self.params.get("force_rescrape", False)
        credential_id = self.params.get("credential_id")

        auth_headers = {}
        if credential_id:
            logger.info(f"Loading OAuth credential: {credential_id}")
            try:
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

        if not sitemap_url:
            base_url = website_url.rstrip("/")
            sitemap_url = f"{base_url}/sitemap.xml"
            logger.info(f"No sitemap_url provided, trying: {sitemap_url}")

        logger.info(
            f"Starting website scraping: url={website_url}, "
            f"sitemap={sitemap_url}, max_pages={max_pages or 'unlimited'}"
        )

        urls = await self._fetch_sitemap(sitemap_url, auth_headers)

        if not urls:
            # Try alternative sitemap locations
            logger.info("No URLs found in sitemap.xml, trying /sitemap_index.xml...")
            alternative_url = f"{website_url.rstrip('/')}/sitemap_index.xml"
            urls = await self._fetch_sitemap(alternative_url, auth_headers)

        # Track discovered Google Docs
        discovered_google_docs = set()

        # If no sitemap found, fall back to manual crawling
        if not urls:
            logger.info(
                "No sitemap found, falling back to manual site crawling from base URL"
            )
            # website_url is guaranteed to be a string by validate_params()
            urls, discovered_google_docs = await self._crawl_site(
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

        if include_patterns or exclude_patterns:
            original_count = len(urls)
            urls = self._filter_urls(urls, include_patterns, exclude_patterns)
            logger.info(
                f"Filtered {original_count} URLs to {len(urls)} "
                f"(include={include_patterns}, exclude={exclude_patterns})"
            )

        if max_pages is not None and len(urls) > max_pages:
            logger.info(f"Limiting to {max_pages} pages (found {len(urls)})")
            urls = urls[:max_pages]
        else:
            logger.info(f"Processing all {len(urls)} URLs from sitemap (no limit)")

        domain = tracking_service.extract_domain(website_url)
        scraped_pages = []
        failed_count = 0
        not_modified_count = 0

        for i, url in enumerate(urls, 1):
            logger.info(f"Scraping page {i}/{len(urls)}: {url}")

            # Get conditional headers for this URL (304 Not Modified support)
            conditional_headers = (
                {} if force_rescrape else tracking_service.get_conditional_headers(url)
            )

            if conditional_headers:
                logger.debug(
                    f"Using conditional headers: {list(conditional_headers.keys())}"
                )

            page_data = await self._scrape_page(url, auth_headers, conditional_headers)

            if not page_data:
                failed_count += 1
                continue

            # Handle 304 Not Modified response (page unchanged - FREE!)
            if page_data.get("not_modified"):
                logger.info(f"⏭️  Not modified (304): {url}")
                not_modified_count += 1
                continue

            scraped_pages.append(page_data)

        logger.info(
            f"Scraped {len(scraped_pages)} pages, {not_modified_count} not modified (304), "
            f"{failed_count} failed. Now checking content hashes..."
        )

        pages_to_embed = []
        skipped_count = 0

        for page in scraped_pages:
            if not force_rescrape:
                # Check content hash - skip embedding if unchanged
                needs_rescrape, existing_uuid = (
                    tracking_service.check_page_needs_rescrape(
                        page["url"], page["content"]
                    )
                )
                if not needs_rescrape:
                    logger.info(f"⏭️  Skipping unchanged content: {page['url']}")
                    skipped_count += 1
                    continue

            pages_to_embed.append(page)

        total_skipped = skipped_count + not_modified_count

        logger.info(
            f"Optimization results: {len(pages_to_embed)} new/changed pages, "
            f"{not_modified_count} skipped (304 Not Modified), "
            f"{skipped_count} skipped (content hash), "
            f"total savings: {total_skipped}/{len(urls)} pages"
        )

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

        texts = []
        metadata_list = []
        vector_ids = []
        page_chunk_counts = []  # Track chunks per page for recording

        for page in pages_to_embed:
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
                chunk_id = str(uuid_lib.uuid5(uuid_lib.UUID(vector_uuid), f"chunk_{i}"))
                vector_ids.append(chunk_id)

        # Generate embeddings and upsert to Qdrant (only for new/changed pages)
        if pages_to_embed:
            logger.info(
                f"Generating embeddings for {len(texts)} chunks from {len(pages_to_embed)} pages..."
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
        else:
            logger.info("No new/changed pages to embed - all content unchanged")
            success_count = 0
            error_count = 0

        # Record successful scrapes in tracking table (with HTTP headers for conditional requests)
        for i, page in enumerate(pages_to_embed):
            try:
                vector_uuid = tracking_service.generate_base_uuid(page["url"])
                tracking_service.record_page_scrape(
                    url=page["url"],
                    page_title=page["title"],
                    content=page["content"],
                    vector_uuid=vector_uuid,
                    chunk_count=page_chunk_counts[i],  # Actual chunk count
                    last_modified=page.get(
                        "last_modified"
                    ),  # Store for future 304 checks
                    etag=page.get("etag"),  # Store for future 304 checks
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

        # Enqueue daily jobs for discovered Google Docs
        google_docs_jobs_created = 0
        google_docs_jobs_skipped = 0

        if discovered_google_docs and credential_id:
            logger.info(
                f"📄 Processing {len(discovered_google_docs)} discovered Google Workspace documents..."
            )
            try:
                google_docs_jobs_created, google_docs_jobs_skipped = (
                    self._enqueue_google_doc_jobs(
                        discovered_google_docs, credential_id, metadata
                    )
                )

                logger.info(
                    f"Google Docs job scheduling complete: {google_docs_jobs_created} jobs created, "
                    f"{google_docs_jobs_skipped} already scheduled"
                )
            except Exception as e:
                logger.error(f"Error enqueueing Google Docs jobs: {e}")
        elif discovered_google_docs and not credential_id:
            logger.warning(
                f"Found {len(discovered_google_docs)} Google Docs but no credential_id provided - skipping"
            )

        total_processed = len(scraped_pages) + total_skipped + failed_count
        total_success = len(pages_to_embed)
        total_failed = failed_count

        message_parts = [
            f"Embedded {len(pages_to_embed)} new/changed pages",
            f"skipped {not_modified_count} (304)",
            f"{skipped_count} (hash)",
            f"removed {removed_count}",
        ]
        if discovered_google_docs:
            message_parts.append(
                f"Google Docs: {google_docs_jobs_created} jobs created, {google_docs_jobs_skipped} already scheduled"
            )

        return {
            # Standardized fields for task run tracking
            "records_processed": total_processed,
            "records_success": total_success,
            "records_failed": total_failed,
            # Job-specific details
            "records_skipped": total_skipped,
            "success": True,
            "message": ", ".join(message_parts),
            "website_url": website_url,
            "sitemap_url": sitemap_url,
            "pages_scraped": len(scraped_pages),
            "pages_embedded": len(pages_to_embed),
            "pages_not_modified": not_modified_count,  # 304 responses (no download!)
            "pages_skipped_hash": skipped_count,  # Content hash unchanged
            "pages_skipped_total": total_skipped,
            "pages_removed": removed_count,
            "pages_failed": failed_count,
            "pages_indexed": success_count,
            "index_errors": error_count,
            "force_rescrape": force_rescrape,
            "google_docs_discovered": len(discovered_google_docs),
            "google_docs_jobs_created": google_docs_jobs_created,
            "google_docs_jobs_skipped": google_docs_jobs_skipped,
            "details": {
                "total_urls_in_sitemap": len(urls),
                "urls_filtered_out": len(urls)
                - len(scraped_pages)
                - total_skipped
                - failed_count,
                "sample_embedded": [page["url"] for page in pages_to_embed[:5]],
                "change_detection_enabled": not force_rescrape,
                "conditional_requests_enabled": not force_rescrape,
            },
        }
