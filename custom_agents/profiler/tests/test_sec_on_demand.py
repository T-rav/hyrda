"""Tests for SEC on-demand fetcher with edgartools and MinIO caching."""

import json
from unittest.mock import MagicMock, patch

import pytest

from profiler.services.sec_on_demand import SECOnDemandFetcher


class TestSECOnDemandFetcher:
    """Tests for SECOnDemandFetcher class."""

    @pytest.fixture
    def fetcher(self):
        """Create fetcher instance."""
        return SECOnDemandFetcher()

    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client."""
        return MagicMock()

    @pytest.fixture
    def sample_filing_data(self):
        """Sample filing data for tests."""
        return {
            "type": "10-K",
            "date": "2024-10-15",
            "content": "Sample 10-K content with financial data...",
            "content_length": 42,
            "url": "https://www.sec.gov/Archives/edgar/data/909832/000090983224000012/cost-20240901.htm",
            "accession_number": "0000909832-24-000012",
            "company": "COSTCO WHOLESALE CORP",
        }


class TestCacheKeyGeneration:
    """Tests for cache key generation."""

    def test_cache_key_format(self):
        """Test cache key is generated correctly."""
        fetcher = SECOnDemandFetcher()
        key = fetcher._get_cache_key("COST", "10-K", "0000909832-24-000012")
        assert key == "COST/10-K/000090983224000012.json"

    def test_cache_key_uppercase_ticker(self):
        """Test ticker is uppercased in cache key."""
        fetcher = SECOnDemandFetcher()
        key = fetcher._get_cache_key("cost", "10-K", "0000909832-24-000012")
        assert key == "COST/10-K/000090983224000012.json"

    def test_cache_key_removes_dashes_from_accession(self):
        """Test dashes are removed from accession number."""
        fetcher = SECOnDemandFetcher()
        key = fetcher._get_cache_key("AAPL", "8-K", "0000320193-24-000001")
        assert "0000320193-24-000001" not in key
        assert "000032019324000001" in key


class TestCacheOperations:
    """Tests for MinIO cache operations."""

    def test_get_from_cache_hit(self):
        """Test cache hit returns cached data."""
        fetcher = SECOnDemandFetcher()
        cached_data = {"type": "10-K", "content": "cached content"}

        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(cached_data).encode("utf-8"))
        }

        with patch.object(fetcher, "_get_s3_client", return_value=mock_s3):
            result = fetcher._get_from_cache("COST", "10-K", "0000909832-24-000012")

        assert result == cached_data
        mock_s3.get_object.assert_called_once()

    def test_get_from_cache_miss(self):
        """Test cache miss returns None."""
        from botocore.exceptions import ClientError

        fetcher = SECOnDemandFetcher()

        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "GetObject"
        )

        with patch.object(fetcher, "_get_s3_client", return_value=mock_s3):
            result = fetcher._get_from_cache("COST", "10-K", "nonexistent")

        assert result is None

    def test_save_to_cache(self):
        """Test saving filing to cache."""
        fetcher = SECOnDemandFetcher()
        filing_data = {"type": "10-K", "content": "test content"}

        mock_s3 = MagicMock()

        with patch.object(fetcher, "_get_s3_client", return_value=mock_s3):
            fetcher._save_to_cache("COST", "10-K", "0000909832-24-000012", filing_data)

        mock_s3.put_object.assert_called_once()
        call_args = mock_s3.put_object.call_args
        assert call_args.kwargs["Bucket"] == "sec-filings-cache"
        assert "COST/10-K/" in call_args.kwargs["Key"]
        assert call_args.kwargs["ContentType"] == "application/json"


class TestCompanyFilingsFetch:
    """Tests for fetching company filings."""

    @pytest.mark.asyncio
    async def test_fetch_filings_uses_cache(self):
        """Test that cached filings are returned without SEC API call."""
        fetcher = SECOnDemandFetcher()
        cached_10k = {
            "type": "10-K",
            "date": "2024-10-15",
            "content": "cached 10-K content",
            "content_length": 100,
            "url": "https://sec.gov/test",
            "accession_number": "0000909832-24-000012",
            "company": "COSTCO",
        }

        # Mock Company class
        mock_company = MagicMock()
        mock_company.name = "COSTCO WHOLESALE CORP"
        mock_company.cik = "0000909832"
        mock_company.tickers = ["COST"]

        mock_filing = MagicMock()
        mock_filing.accession_number = "0000909832-24-000012"
        mock_filing.filing_date = "2024-10-15"

        mock_filings = MagicMock()
        mock_filings.head.return_value = [mock_filing]
        mock_filings.__iter__ = lambda self: iter([mock_filing])
        mock_filings.__len__ = lambda self: 1

        mock_company.get_filings.return_value = mock_filings

        with patch("profiler.services.sec_on_demand.Company", return_value=mock_company):
            with patch.object(fetcher, "_get_from_cache", return_value=cached_10k):
                result = await fetcher.get_company_filings_for_research("COST")

        assert result["company_name"] == "COSTCO WHOLESALE CORP"
        assert len(result["filings"]) >= 1
        assert result["filings"][0]["content"] == "cached 10-K content"

    @pytest.mark.asyncio
    async def test_fetch_filings_cache_miss_fetches_from_sec(self):
        """Test that cache miss triggers SEC API fetch."""
        fetcher = SECOnDemandFetcher()

        # Mock Company class
        mock_company = MagicMock()
        mock_company.name = "APPLE INC"
        mock_company.cik = "0000320193"
        mock_company.tickers = ["AAPL"]

        mock_filing = MagicMock()
        mock_filing.accession_number = "0000320193-24-000001"
        mock_filing.filing_date = "2024-11-01"
        mock_filing.filing_homepage = "https://sec.gov/test"
        mock_filing.text.return_value = "Fresh 10-K content from SEC"

        mock_filings = MagicMock()
        mock_filings.head.return_value = [mock_filing]
        mock_filings.__iter__ = lambda self: iter([mock_filing])
        mock_filings.__len__ = lambda self: 1

        mock_company.get_filings.return_value = mock_filings

        with patch("profiler.services.sec_on_demand.Company", return_value=mock_company):
            with patch.object(fetcher, "_get_from_cache", return_value=None):
                with patch.object(fetcher, "_save_to_cache") as mock_save:
                    result = await fetcher.get_company_filings_for_research("AAPL")

        # Verify SEC API was called
        mock_filing.text.assert_called()
        # Verify result was cached
        mock_save.assert_called()
        assert "Fresh 10-K content from SEC" in result["filings"][0]["content"]

    @pytest.mark.asyncio
    async def test_fetch_filings_invalid_ticker(self):
        """Test error handling for invalid ticker."""
        fetcher = SECOnDemandFetcher()

        with patch("profiler.services.sec_on_demand.Company", side_effect=Exception("Company not found")):
            with pytest.raises(ValueError, match="Could not find company"):
                await fetcher.get_company_filings_for_research("INVALIDTICKER")


class TestSearchFilings:
    """Tests for searching within filings."""

    @pytest.mark.asyncio
    async def test_search_finds_matching_content(self):
        """Test search returns excerpts containing query."""
        fetcher = SECOnDemandFetcher()

        mock_filings_data = {
            "company_name": "TEST CORP",
            "cik": "0001234567",
            "ticker": "TEST",
            "filings": [
                {
                    "type": "10-K",
                    "date": "2024-01-15",
                    "content": "This filing discusses artificial intelligence initiatives and machine learning investments.",
                    "accession_number": "0001234567-24-000001",
                    "url": "https://sec.gov/test",
                }
            ],
            "total_filings": 1,
        }

        with patch.object(fetcher, "get_company_filings_for_research", return_value=mock_filings_data):
            results = await fetcher.search_filings("TEST", "artificial intelligence")

        assert len(results) == 1
        assert "artificial intelligence" in results[0]["excerpt"].lower()

    @pytest.mark.asyncio
    async def test_search_no_matches(self):
        """Test search returns empty list when no matches."""
        fetcher = SECOnDemandFetcher()

        mock_filings_data = {
            "company_name": "TEST CORP",
            "cik": "0001234567",
            "ticker": "TEST",
            "filings": [
                {
                    "type": "10-K",
                    "date": "2024-01-15",
                    "content": "This filing discusses financial performance.",
                    "accession_number": "0001234567-24-000001",
                    "url": "https://sec.gov/test",
                }
            ],
            "total_filings": 1,
        }

        with patch.object(fetcher, "get_company_filings_for_research", return_value=mock_filings_data):
            results = await fetcher.search_filings("TEST", "blockchain technology")

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_filters_by_form_type(self):
        """Test search only searches specified form types."""
        fetcher = SECOnDemandFetcher()

        mock_filings_data = {
            "company_name": "TEST CORP",
            "cik": "0001234567",
            "ticker": "TEST",
            "filings": [
                {
                    "type": "10-K",
                    "date": "2024-01-15",
                    "content": "Annual report with keyword test",
                    "accession_number": "0001234567-24-000001",
                    "url": "https://sec.gov/test1",
                },
                {
                    "type": "8-K",
                    "date": "2024-02-15",
                    "content": "Current report with keyword test",
                    "accession_number": "0001234567-24-000002",
                    "url": "https://sec.gov/test2",
                },
            ],
            "total_filings": 2,
        }

        with patch.object(fetcher, "get_company_filings_for_research", return_value=mock_filings_data):
            # Only search 10-K
            results = await fetcher.search_filings("TEST", "keyword", form_types=["10-K"])

        assert len(results) == 1
        assert results[0]["type"] == "10-K"
