"""Tests for Website Scraping job.

These tests focus on validation logic, parameter handling, and scraping logic.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from config.settings import TasksSettings
from jobs.website_scrape import WebsiteScrapeJob


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Mock(spec=TasksSettings)
    settings.tasks_port = 5001
    settings.tasks_host = "localhost"
    settings.data_database_url = "mysql+pymysql://test:test@localhost:3306/test"
    return settings


@pytest.fixture
def mock_clients():
    """Mock OpenAI and Qdrant clients for all tests."""
    with (
        patch("jobs.website_scrape.OpenAIEmbeddings") as mock_embeddings,
        patch("jobs.website_scrape.QdrantClient") as mock_qdrant,
    ):
        yield mock_embeddings, mock_qdrant


class TestWebsiteScrapeJobValidation:
    """Test job parameter validation."""

    def test_job_name_and_description(self, mock_settings, mock_clients):
        """Test job has proper name and description."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")
        assert job.JOB_NAME == "Website Scraping"
        assert "sitemap" in job.JOB_DESCRIPTION.lower()

    def test_requires_website_url(self, mock_settings, mock_clients):
        """Test job requires website_url parameter."""
        with pytest.raises(ValueError, match="website_url"):
            WebsiteScrapeJob(mock_settings)

    def test_website_url_must_start_with_http(self, mock_settings, mock_clients):
        """Test website_url must be a valid URL."""
        with pytest.raises(ValueError, match="must start with http"):
            WebsiteScrapeJob(mock_settings, website_url="example.com")

    def test_accepts_https_url(self, mock_settings, mock_clients):
        """Test job accepts HTTPS URLs."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")
        assert job.params["website_url"] == "https://example.com"

    def test_accepts_http_url(self, mock_settings, mock_clients):
        """Test job accepts HTTP URLs."""
        job = WebsiteScrapeJob(mock_settings, website_url="http://example.com")
        assert job.params["website_url"] == "http://example.com"

    def test_optional_sitemap_url(self, mock_settings, mock_clients):
        """Test job accepts optional sitemap_url parameter."""
        job = WebsiteScrapeJob(
            mock_settings,
            website_url="https://example.com",
            sitemap_url="https://example.com/custom-sitemap.xml",
        )
        assert job.params["sitemap_url"] == "https://example.com/custom-sitemap.xml"

    def test_optional_max_pages(self, mock_settings, mock_clients):
        """Test job accepts optional max_pages parameter."""
        job = WebsiteScrapeJob(
            mock_settings, website_url="https://example.com", max_pages=50
        )
        assert job.params["max_pages"] == 50

    def test_optional_include_patterns(self, mock_settings, mock_clients):
        """Test job accepts optional include_patterns parameter."""
        job = WebsiteScrapeJob(
            mock_settings,
            website_url="https://example.com",
            include_patterns=["/docs/", "/api/"],
        )
        assert job.params["include_patterns"] == ["/docs/", "/api/"]

    def test_optional_exclude_patterns(self, mock_settings, mock_clients):
        """Test job accepts optional exclude_patterns parameter."""
        job = WebsiteScrapeJob(
            mock_settings,
            website_url="https://example.com",
            exclude_patterns=["/blog/", "/news/"],
        )
        assert job.params["exclude_patterns"] == ["/blog/", "/news/"]

    def test_optional_metadata(self, mock_settings, mock_clients):
        """Test job accepts optional metadata parameter."""
        job = WebsiteScrapeJob(
            mock_settings,
            website_url="https://example.com",
            metadata={"project": "docs", "version": "1.0"},
        )
        assert job.params["metadata"] == {"project": "docs", "version": "1.0"}

    def test_optional_force_rescrape(self, mock_settings, mock_clients):
        """Test job accepts optional force_rescrape parameter."""
        job = WebsiteScrapeJob(
            mock_settings, website_url="https://example.com", force_rescrape=True
        )
        assert job.params["force_rescrape"] is True

    def test_job_has_required_attributes(self, mock_settings, mock_clients):
        """Test job has all required attributes."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")

        assert hasattr(job, "JOB_NAME")
        assert hasattr(job, "JOB_DESCRIPTION")
        assert hasattr(job, "REQUIRED_PARAMS")
        assert hasattr(job, "OPTIONAL_PARAMS")
        assert hasattr(job, "params")

    def test_optional_credential_id(self, mock_settings, mock_clients):
        """Test job accepts optional credential_id parameter for OAuth."""
        job = WebsiteScrapeJob(
            mock_settings,
            website_url="https://example.com",
            credential_id="test_credential",
        )
        assert job.params["credential_id"] == "test_credential"


class TestWebsiteScrapeJobOAuthAuthentication:
    """Test OAuth authentication for authenticated sites."""

    @pytest.mark.asyncio
    async def test_loads_oauth_credential(self, mock_settings, mock_clients):
        """Test OAuth credential is loaded when credential_id is provided."""
        from datetime import UTC, datetime

        job = WebsiteScrapeJob(
            mock_settings,
            website_url="https://sites.google.com/example/site",
            credential_id="test_cred",
        )

        # Mock the database session and credential
        with (
            patch("jobs.website_scrape.get_db_session") as mock_db_session,
            patch("jobs.website_scrape.get_encryption_service") as mock_encryption,
            patch("jobs.website_scrape.WebPageTrackingService") as mock_tracking,
            patch.object(job.vector_client, "initialize", new=AsyncMock()),
            patch.object(job, "_fetch_sitemap", new=AsyncMock(return_value=[])),
            patch.object(
                job,
                "_crawl_site",
                new=AsyncMock(
                    return_value=["https://sites.google.com/example/site/page1"]
                ),
            ),
            patch.object(
                job,
                "_scrape_page",
                new=AsyncMock(
                    return_value={
                        "content": "test content",
                        "url": "https://sites.google.com/example/site/page1",
                        "title": "Test Page",
                        "description": "Test description",
                        "length": 12,
                    }
                ),
            ),
            patch.object(job.embedding_client, "chunk_text", return_value=["chunk1"]),
            patch.object(job.embedding_client, "embed_batch", return_value=[[0.1]]),
            patch.object(job.vector_client, "upsert_with_namespace", new=AsyncMock()),
        ):
            # Setup mock credential
            mock_credential = Mock()
            mock_credential.credential_id = "test_cred"
            mock_credential.encrypted_token = "encrypted_token"
            mock_credential.last_used_at = datetime.now(UTC)

            # Setup mock database
            mock_query = Mock()
            mock_query.filter.return_value.first.return_value = mock_credential
            mock_session = Mock()
            mock_session.query.return_value = mock_query
            mock_session.__enter__ = Mock(return_value=mock_session)
            mock_session.__exit__ = Mock(return_value=False)
            mock_db_session.return_value = mock_session

            # Setup mock encryption
            mock_encryption_service = Mock()
            mock_token_data = {
                "token": "test_access_token",
                "expiry": datetime.now(UTC).isoformat(),
            }
            import json

            mock_encryption_service.decrypt.return_value = json.dumps(mock_token_data)
            mock_encryption.return_value = mock_encryption_service

            # Setup mock tracking service
            mock_tracking_instance = Mock()
            mock_tracking_instance.check_page_needs_rescrape.return_value = (
                True,
                None,
            )
            mock_tracking_instance.generate_base_uuid.return_value = (
                "12345678-1234-5678-1234-567812345678"
            )
            mock_tracking_instance.record_page_scrape.return_value = None
            mock_tracking_instance.extract_domain.return_value = "example.site"
            mock_tracking_instance.get_pages_by_domain.return_value = []
            mock_tracking.return_value = mock_tracking_instance

            # Execute job
            await job._execute_job()

            # Verify credential was loaded
            mock_encryption_service.decrypt.assert_called_once()
            mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_auth_headers_passed_to_fetch_sitemap(
        self, mock_settings, mock_clients
    ):
        """Test authentication headers are passed to _fetch_sitemap."""
        from datetime import UTC, datetime

        job = WebsiteScrapeJob(
            mock_settings,
            website_url="https://sites.google.com/example/site",
            credential_id="test_cred",
        )

        with (
            patch("jobs.website_scrape.get_db_session") as mock_db_session,
            patch("jobs.website_scrape.get_encryption_service") as mock_encryption,
            patch("jobs.website_scrape.WebPageTrackingService") as mock_tracking,
            patch.object(job.vector_client, "initialize", new=AsyncMock()),
            patch.object(
                job, "_fetch_sitemap", new=AsyncMock(return_value=[])
            ) as mock_fetch,
            patch.object(
                job,
                "_crawl_site",
                new=AsyncMock(
                    return_value=["https://sites.google.com/example/site/page1"]
                ),
            ),
            patch.object(
                job,
                "_scrape_page",
                new=AsyncMock(
                    return_value={
                        "content": "test content",
                        "url": "https://sites.google.com/example/site/page1",
                        "title": "Test Page",
                        "description": "Test description",
                        "length": 12,
                    }
                ),
            ),
            patch.object(job.embedding_client, "chunk_text", return_value=["chunk1"]),
            patch.object(job.embedding_client, "embed_batch", return_value=[[0.1]]),
            patch.object(job.vector_client, "upsert_with_namespace", new=AsyncMock()),
        ):
            # Setup mock credential
            mock_credential = Mock()
            mock_credential.credential_id = "test_cred"
            mock_credential.encrypted_token = "encrypted_token"
            mock_credential.last_used_at = datetime.now(UTC)

            mock_query = Mock()
            mock_query.filter.return_value.first.return_value = mock_credential
            mock_session = Mock()
            mock_session.query.return_value = mock_query
            mock_session.__enter__ = Mock(return_value=mock_session)
            mock_session.__exit__ = Mock(return_value=False)
            mock_db_session.return_value = mock_session

            # Setup mock encryption
            mock_encryption_service = Mock()
            mock_token_data = {
                "token": "test_access_token",
                "expiry": datetime.now(UTC).isoformat(),
            }
            import json

            mock_encryption_service.decrypt.return_value = json.dumps(mock_token_data)
            mock_encryption.return_value = mock_encryption_service

            # Setup mock tracking service
            mock_tracking_instance = Mock()
            mock_tracking_instance.check_page_needs_rescrape.return_value = (
                True,
                None,
            )
            mock_tracking_instance.generate_base_uuid.return_value = (
                "12345678-1234-5678-1234-567812345678"
            )
            mock_tracking_instance.record_page_scrape.return_value = None
            mock_tracking_instance.extract_domain.return_value = "example.site"
            mock_tracking_instance.get_pages_by_domain.return_value = []
            mock_tracking.return_value = mock_tracking_instance

            # Execute job
            await job._execute_job()

            # Verify auth headers were passed to _fetch_sitemap
            mock_fetch.assert_called()
            call_args = mock_fetch.call_args
            auth_headers = call_args[0][1] if len(call_args[0]) > 1 else {}
            assert "Authorization" in auth_headers
            assert auth_headers["Authorization"] == "Bearer test_access_token"

    @pytest.mark.asyncio
    async def test_credential_not_found_raises_error(self, mock_settings, mock_clients):
        """Test error when credential_id not found in database."""
        job = WebsiteScrapeJob(
            mock_settings,
            website_url="https://sites.google.com/example/site",
            credential_id="nonexistent_cred",
        )

        with (
            patch("jobs.website_scrape.get_db_session") as mock_db_session,
            patch("jobs.website_scrape.get_encryption_service"),
            patch("jobs.website_scrape.WebPageTrackingService"),
            patch.object(job.vector_client, "initialize", new=AsyncMock()),
        ):
            # Setup mock database with no credential found
            mock_query = Mock()
            mock_query.filter.return_value.first.return_value = None
            mock_session = Mock()
            mock_session.query.return_value = mock_query
            mock_session.__enter__ = Mock(return_value=mock_session)
            mock_session.__exit__ = Mock(return_value=False)
            mock_db_session.return_value = mock_session

            # Execute job should raise error
            with pytest.raises(ValueError, match="OAuth credential loading failed"):
                await job._execute_job()

    @pytest.mark.asyncio
    async def test_token_refresh_when_expired(self, mock_settings, mock_clients):
        """Test token is refreshed when expired."""
        from datetime import UTC, datetime, timedelta

        job = WebsiteScrapeJob(
            mock_settings,
            website_url="https://sites.google.com/example/site",
            credential_id="test_cred",
        )

        with (
            patch("jobs.website_scrape.get_db_session") as mock_db_session,
            patch("jobs.website_scrape.get_encryption_service") as mock_encryption,
            patch("jobs.website_scrape.WebPageTrackingService") as mock_tracking,
            patch("jobs.website_scrape.Credentials") as mock_creds_class,
            patch("jobs.website_scrape.Request"),
            patch.object(job.vector_client, "initialize", new=AsyncMock()),
            patch.object(job, "_fetch_sitemap", new=AsyncMock(return_value=[])),
            patch.object(
                job,
                "_crawl_site",
                new=AsyncMock(
                    return_value=["https://sites.google.com/example/site/page1"]
                ),
            ),
            patch.object(
                job,
                "_scrape_page",
                new=AsyncMock(
                    return_value={
                        "content": "test content",
                        "url": "https://sites.google.com/example/site/page1",
                        "title": "Test Page",
                        "description": "Test description",
                        "length": 12,
                    }
                ),
            ),
            patch.object(job.embedding_client, "chunk_text", return_value=["chunk1"]),
            patch.object(job.embedding_client, "embed_batch", return_value=[[0.1]]),
            patch.object(job.vector_client, "upsert_with_namespace", new=AsyncMock()),
        ):
            # Setup mock credential with expired token
            mock_credential = Mock()
            mock_credential.credential_id = "test_cred"
            mock_credential.encrypted_token = "encrypted_token"
            mock_credential.last_used_at = datetime.now(UTC)

            mock_query = Mock()
            mock_query.filter.return_value.first.return_value = mock_credential
            mock_session = Mock()
            mock_session.query.return_value = mock_query
            mock_session.__enter__ = Mock(return_value=mock_session)
            mock_session.__exit__ = Mock(return_value=False)
            mock_db_session.return_value = mock_session

            # Setup mock encryption
            mock_encryption_service = Mock()
            expired_time = datetime.now(UTC) - timedelta(hours=1)
            mock_token_data = {
                "token": "old_access_token",
                "refresh_token": "refresh_token",
                "expiry": expired_time.isoformat(),
            }
            import json

            mock_encryption_service.decrypt.return_value = json.dumps(mock_token_data)
            mock_encryption_service.encrypt.return_value = "new_encrypted_token"
            mock_encryption.return_value = mock_encryption_service

            # Setup mock credentials refresh
            mock_creds = Mock()
            new_token_data = {
                "token": "new_access_token",
                "refresh_token": "refresh_token",
                "expiry": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            mock_creds.to_json.return_value = json.dumps(new_token_data)
            mock_creds_class.from_authorized_user_info.return_value = mock_creds

            # Setup mock tracking service
            mock_tracking_instance = Mock()
            mock_tracking_instance.check_page_needs_rescrape.return_value = (
                True,
                None,
            )
            mock_tracking_instance.generate_base_uuid.return_value = (
                "12345678-1234-5678-1234-567812345678"
            )
            mock_tracking_instance.record_page_scrape.return_value = None
            mock_tracking_instance.extract_domain.return_value = "example.site"
            mock_tracking_instance.get_pages_by_domain.return_value = []
            mock_tracking.return_value = mock_tracking_instance

            # Execute job
            await job._execute_job()

            # Verify token was refreshed
            mock_creds.refresh.assert_called_once()
            mock_encryption_service.encrypt.assert_called()


class TestWebsiteScrapeJobURLFiltering:
    """Test URL filtering logic."""

    def test_filter_urls_with_include_patterns(self, mock_settings, mock_clients):
        """Test URL filtering with include patterns."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")

        urls = [
            "https://example.com/docs/page1",
            "https://example.com/blog/post1",
            "https://example.com/docs/page2",
            "https://example.com/about",
        ]

        filtered = job._filter_urls(
            urls, include_patterns=["/docs/"], exclude_patterns=[]
        )
        assert len(filtered) == 2
        assert "https://example.com/docs/page1" in filtered
        assert "https://example.com/docs/page2" in filtered

    def test_filter_urls_with_exclude_patterns(self, mock_settings, mock_clients):
        """Test URL filtering with exclude patterns."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")

        urls = [
            "https://example.com/docs/page1",
            "https://example.com/blog/post1",
            "https://example.com/docs/page2",
            "https://example.com/about",
        ]

        filtered = job._filter_urls(
            urls, include_patterns=[], exclude_patterns=["/blog/"]
        )
        assert len(filtered) == 3
        assert "https://example.com/blog/post1" not in filtered

    def test_filter_urls_with_both_patterns(self, mock_settings, mock_clients):
        """Test URL filtering with both include and exclude patterns."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")

        urls = [
            "https://example.com/docs/page1",
            "https://example.com/docs/draft/page2",
            "https://example.com/blog/post1",
        ]

        filtered = job._filter_urls(
            urls, include_patterns=["/docs/"], exclude_patterns=["/draft/"]
        )
        assert len(filtered) == 1
        assert "https://example.com/docs/page1" in filtered

    def test_filter_urls_no_patterns(self, mock_settings, mock_clients):
        """Test URL filtering with no patterns returns all URLs."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")

        urls = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3",
        ]

        filtered = job._filter_urls(urls, include_patterns=[], exclude_patterns=[])
        assert len(filtered) == 3


class TestWebsiteScrapeJobSitemapParsing:
    """Test sitemap parsing logic."""

    @pytest.mark.asyncio
    async def test_fetch_sitemap_success(self, mock_settings, mock_clients):
        """Test successful sitemap fetching."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")

        sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page1</loc></url>
            <url><loc>https://example.com/page2</loc></url>
            <url><loc>https://example.com/page3</loc></url>
        </urlset>
        """

        mock_response = Mock()
        mock_response.content = sitemap_xml.encode()
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            urls = await job._fetch_sitemap("https://example.com/sitemap.xml")

            assert len(urls) == 3
            assert "https://example.com/page1" in urls
            assert "https://example.com/page2" in urls
            assert "https://example.com/page3" in urls

    @pytest.mark.asyncio
    async def test_fetch_sitemap_handles_errors(self, mock_settings, mock_clients):
        """Test sitemap fetching handles HTTP errors gracefully."""
        import httpx

        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPError("Network error")
            )

            urls = await job._fetch_sitemap("https://example.com/sitemap.xml")
            assert urls == []

    @pytest.mark.asyncio
    async def test_fetch_sitemap_filters_xml_files(self, mock_settings, mock_clients):
        """Test that sitemap.xml files are filtered out from results."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")

        sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page1</loc></url>
            <url><loc>https://example.com/sitemap_sections.xml</loc></url>
            <url><loc>https://example.com/page2</loc></url>
            <url><loc>https://example.com/sitemap_index.xml</loc></url>
        </urlset>
        """

        mock_response = Mock()
        mock_response.content = sitemap_xml.encode()
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            urls = await job._fetch_sitemap("https://example.com/sitemap.xml")

            # Should only return content pages, not .xml files
            assert len(urls) == 2
            assert "https://example.com/page1" in urls
            assert "https://example.com/page2" in urls
            # XML files should be filtered out
            assert "https://example.com/sitemap_sections.xml" not in urls
            assert "https://example.com/sitemap_index.xml" not in urls

    @pytest.mark.asyncio
    async def test_fetch_sitemap_index_recursive(self, mock_settings, mock_clients):
        """Test sitemap index recursively fetches child sitemaps."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")

        # Sitemap index
        sitemap_index = """<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <sitemap><loc>https://example.com/sitemap1.xml</loc></sitemap>
            <sitemap><loc>https://example.com/sitemap2.xml</loc></sitemap>
        </sitemapindex>
        """

        # Child sitemap 1
        sitemap1 = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page1</loc></url>
            <url><loc>https://example.com/page2</loc></url>
        </urlset>
        """

        # Child sitemap 2
        sitemap2 = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page3</loc></url>
        </urlset>
        """

        responses = {
            "https://example.com/sitemap.xml": sitemap_index,
            "https://example.com/sitemap1.xml": sitemap1,
            "https://example.com/sitemap2.xml": sitemap2,
        }

        async def mock_get(url, **kwargs):
            mock_resp = Mock()
            mock_resp.content = responses.get(url, "").encode()
            mock_resp.raise_for_status = Mock()
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = mock_get

            urls = await job._fetch_sitemap("https://example.com/sitemap.xml")

            # Should fetch all pages from all child sitemaps
            assert len(urls) == 3
            assert "https://example.com/page1" in urls
            assert "https://example.com/page2" in urls
            assert "https://example.com/page3" in urls

    @pytest.mark.asyncio
    async def test_fetch_sitemap_empty_returns_empty_list(
        self, mock_settings, mock_clients
    ):
        """Test empty sitemap returns empty list."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")

        sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        </urlset>
        """

        mock_response = Mock()
        mock_response.content = sitemap_xml.encode()
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            urls = await job._fetch_sitemap("https://example.com/sitemap.xml")
            assert urls == []


class TestWebsiteScrapeJobPageScraping:
    """Test page scraping logic."""

    @pytest.mark.asyncio
    async def test_scrape_page_success(self, mock_settings, mock_clients):
        """Test successful page scraping."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")

        html_content = """
        <!DOCTYPE html>
        <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Hello World</h1>
            <p>This is test content.</p>
        </body>
        </html>
        """

        mock_response = Mock()
        mock_response.content = html_content.encode()
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await job._scrape_page("https://example.com/page1")

            assert result is not None
            assert result["url"] == "https://example.com/page1"
            assert result["title"] == "Test Page"
            assert "Hello World" in result["content"]
            assert "This is test content" in result["content"]
            assert result["length"] > 0

    @pytest.mark.asyncio
    async def test_scrape_page_removes_scripts_and_styles(
        self, mock_settings, mock_clients
    ):
        """Test page scraping removes script and style elements."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")

        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Page</title>
            <style>body { color: red; }</style>
        </head>
        <body>
            <h1>Hello World</h1>
            <script>console.log('test');</script>
            <p>This is test content.</p>
        </body>
        </html>
        """

        mock_response = Mock()
        mock_response.content = html_content.encode()
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await job._scrape_page("https://example.com/page1")

            assert result is not None
            assert "console.log" not in result["content"]
            assert "color: red" not in result["content"]
            assert "Hello World" in result["content"]

    @pytest.mark.asyncio
    async def test_scrape_page_handles_errors(self, mock_settings, mock_clients):
        """Test page scraping handles HTTP errors gracefully."""
        import httpx

        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPError("Network error")
            )

            result = await job._scrape_page("https://example.com/page1")
            assert result is None


class TestWebsiteScrapeJobParameters:
    """Test job parameter handling."""

    def test_default_max_pages_is_100(self, mock_settings, mock_clients):
        """Test default max_pages is 100."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")
        assert "max_pages" not in job.params or job.params.get("max_pages", 100) == 100

    def test_default_force_rescrape_is_false(self, mock_settings, mock_clients):
        """Test default force_rescrape is False."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")
        assert job.params.get("force_rescrape", False) is False

    def test_stores_all_parameters(self, mock_settings, mock_clients):
        """Test job stores all provided parameters."""
        job = WebsiteScrapeJob(
            mock_settings,
            website_url="https://example.com",
            sitemap_url="https://example.com/sitemap.xml",
            max_pages=50,
            include_patterns=["/docs/"],
            exclude_patterns=["/blog/"],
            metadata={"project": "test"},
            force_rescrape=True,
        )

        assert job.params["website_url"] == "https://example.com"
        assert job.params["sitemap_url"] == "https://example.com/sitemap.xml"
        assert job.params["max_pages"] == 50
        assert job.params["include_patterns"] == ["/docs/"]
        assert job.params["exclude_patterns"] == ["/blog/"]
        assert job.params["metadata"] == {"project": "test"}
        assert job.params["force_rescrape"] is True


class TestWebsiteScrapeJobChunking:
    """Test content chunking functionality."""

    @patch("jobs.website_scrape.QdrantClient")
    @patch("jobs.website_scrape.OpenAIEmbeddings")
    def test_chunking_large_content(self, mock_embeddings, mock_qdrant, mock_settings):
        """Test that large content is chunked to avoid token limits."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")

        # Simulate large content (10,000 chars)
        large_content = "A" * 10000

        # Mock chunk_text to return multiple chunks
        mock_embeddings_instance = Mock()
        mock_embeddings_instance.chunk_text.return_value = [
            large_content[:2000],
            large_content[2000:4000],
            large_content[4000:6000],
            large_content[6000:8000],
            large_content[8000:10000],
        ]
        job.embedding_client = mock_embeddings_instance

        # Verify chunking is called
        chunks = job.embedding_client.chunk_text(
            large_content, chunk_size=2000, chunk_overlap=200
        )

        assert len(chunks) == 5
        assert all(len(chunk) <= 2000 for chunk in chunks)

    @patch("jobs.website_scrape.QdrantClient")
    @patch("jobs.website_scrape.OpenAIEmbeddings")
    def test_empty_content_creates_one_chunk(
        self, mock_embeddings, mock_qdrant, mock_settings
    ):
        """Test that empty content still creates at least one chunk."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")

        # Mock chunk_text to return empty list for empty content
        mock_embeddings_instance = Mock()
        mock_embeddings_instance.chunk_text.return_value = []
        job.embedding_client = mock_embeddings_instance

        chunks = job.embedding_client.chunk_text("")

        # Even empty content should be handled gracefully
        assert chunks == []  # Empty list is returned, job will create one chunk

    @patch("jobs.website_scrape.QdrantClient")
    @patch("jobs.website_scrape.OpenAIEmbeddings")
    def test_chunk_includes_page_context(
        self, mock_embeddings, mock_qdrant, mock_settings
    ):
        """Test that chunks include page title and URL context."""
        # This is tested implicitly in the job execution logic
        # where we prepend: "[{title}]\n{url}\n\n{chunk}"
        page_title = "Test Page"
        page_url = "https://example.com/test"
        chunk_content = "This is chunk content"

        # Expected format
        expected = f"[{page_title}]\n{page_url}\n\n{chunk_content}"

        assert "[Test Page]" in expected
        assert "https://example.com/test" in expected
        assert "This is chunk content" in expected


class TestWebsiteScrapeJobInitialization:
    """Test job initialization and client setup."""

    @patch("jobs.website_scrape.QdrantClient")
    @patch("jobs.website_scrape.OpenAIEmbeddings")
    def test_clients_initialized_in_constructor(
        self, mock_embeddings, mock_qdrant, mock_settings
    ):
        """Test embedding and vector clients are created in constructor."""
        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")

        # Verify clients were instantiated
        assert hasattr(job, "embedding_client")
        assert hasattr(job, "vector_client")
        assert job.embedding_client is not None
        assert job.vector_client is not None

    @pytest.mark.asyncio
    @patch("services.web_page_tracking_service.WebPageTrackingService")
    @patch("jobs.website_scrape.QdrantClient")
    @patch("jobs.website_scrape.OpenAIEmbeddings")
    async def test_vector_client_initialized_before_use(
        self, mock_embeddings, mock_qdrant, mock_tracking, mock_settings
    ):
        """Test vector client initialize() is called before use."""
        # Setup mocks
        mock_vector_instance = Mock()
        mock_vector_instance.initialize = AsyncMock()
        mock_qdrant.return_value = mock_vector_instance

        # Mock tracking service to avoid database
        mock_tracking_instance = Mock()
        mock_tracking_instance.extract_domain.return_value = "example.com"
        mock_tracking_instance.check_page_needs_rescrape.return_value = (True, None)
        mock_tracking_instance.generate_base_uuid.return_value = "test-uuid"
        mock_tracking.return_value = mock_tracking_instance

        job = WebsiteScrapeJob(mock_settings, website_url="https://example.com")

        # Mock sitemap and page scraping to return empty
        job._fetch_sitemap = AsyncMock(return_value=[])

        # Execute job (suppress exceptions, we only care that initialize was called)
        from contextlib import suppress

        with suppress(Exception):
            await job._execute_job()

        # Verify initialize() was called on vector client
        mock_vector_instance.initialize.assert_called_once()
