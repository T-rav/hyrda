"""SEC Document Fetcher using EdgarTools library.

Fetches and processes SEC filings using the edgartools package.
Caches filings in MinIO for faster subsequent lookups.
"""

import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError
from edgar import Company, set_identity

logger = logging.getLogger(__name__)

# Set SEC identity (required by SEC EDGAR API)
set_identity("insightmesh@8thlight.com")


class SECOnDemandFetcher:
    """Fetch SEC documents using edgartools with MinIO caching."""

    def __init__(self, user_agent: str = "8th Light InsightMesh insightmesh@8thlight.com"):
        """Initialize SEC fetcher with MinIO caching.

        Args:
            user_agent: User-Agent header (used for identity)
        """
        # MinIO configuration
        self.s3_endpoint = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
        self.s3_access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.s3_secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.sec_bucket = os.getenv("SEC_CACHE_BUCKET", "sec-filings-cache")
        self._s3_client = None

    def _get_s3_client(self):
        """Get or create S3 client."""
        if self._s3_client is None:
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=self.s3_endpoint,
                aws_access_key_id=self.s3_access_key,
                aws_secret_access_key=self.s3_secret_key,
            )
            # Ensure bucket exists
            try:
                self._s3_client.head_bucket(Bucket=self.sec_bucket)
            except ClientError:
                try:
                    self._s3_client.create_bucket(Bucket=self.sec_bucket)
                    logger.info(f"Created SEC cache bucket: {self.sec_bucket}")
                except Exception as e:
                    logger.warning(f"Could not create SEC cache bucket: {e}")
        return self._s3_client

    def _get_cache_key(self, ticker: str, form: str, accession: str) -> str:
        """Generate cache key for a filing."""
        safe_accession = accession.replace("-", "")
        return f"{ticker.upper()}/{form}/{safe_accession}.json"

    def _get_from_cache(self, ticker: str, form: str, accession: str) -> dict | None:
        """Get filing from MinIO cache."""
        try:
            s3 = self._get_s3_client()
            key = self._get_cache_key(ticker, form, accession)
            response = s3.get_object(Bucket=self.sec_bucket, Key=key)
            data = json.loads(response["Body"].read().decode("utf-8"))
            logger.info(f"📦 Cache HIT for {form} {accession}")
            return data
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.debug(f"Cache MISS for {form} {accession}")
            else:
                logger.warning(f"Cache error for {accession}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to read from SEC cache: {e}")
            return None

    def _save_to_cache(self, ticker: str, form: str, accession: str, filing_data: dict) -> None:
        """Save filing to MinIO cache."""
        try:
            s3 = self._get_s3_client()
            key = self._get_cache_key(ticker, form, accession)
            s3.put_object(
                Bucket=self.sec_bucket,
                Key=key,
                Body=json.dumps(filing_data, default=str).encode("utf-8"),
                ContentType="application/json",
            )
            logger.info(f"💾 Cached {form} {accession} ({len(filing_data.get('content', ''))} chars)")
        except Exception as e:
            logger.warning(f"Failed to cache SEC filing {accession}: {e}")

    async def get_company_filings_for_research(
        self, ticker_or_cik: str, query: str | None = None
    ) -> dict[str, Any]:
        """Fetch SEC filings for a company using edgartools.

        Fetches:
        - Latest 10-K (annual report)
        - 4 most recent 8-Ks (material events)

        Args:
            ticker_or_cik: Company ticker symbol or CIK
            query: Optional query (for logging)

        Returns:
            Dictionary with filing contents and metadata
        """
        logger.info(f"Fetching SEC filings for {ticker_or_cik} using edgartools")

        try:
            # Create company object
            company = Company(ticker_or_cik)
            company_name = company.name
            ticker = company.tickers[0] if company.tickers else ticker_or_cik.upper()

            logger.info(f"Found company: {company_name} (CIK: {company.cik})")
        except Exception as e:
            logger.error(f"Could not find company {ticker_or_cik}: {e}")
            raise ValueError(f"Could not find company: {ticker_or_cik}") from e

        all_filings = []

        # Fetch latest 10-K
        try:
            ten_k_filings = company.get_filings(form="10-K").head(1)
            logger.info(f"Found {len(ten_k_filings)} 10-K filing(s)")

            for filing in ten_k_filings:
                accession = filing.accession_number

                # Check cache first
                cached = self._get_from_cache(ticker, "10-K", accession)
                if cached:
                    all_filings.append(cached)
                    continue

                # Fetch from SEC
                try:
                    content = filing.text()
                    filing_data = {
                        "type": "10-K",
                        "date": str(filing.filing_date),
                        "content": content,
                        "content_length": len(content),
                        "url": filing.filing_homepage,
                        "accession_number": accession,
                        "company": company_name,
                    }
                    self._save_to_cache(ticker, "10-K", accession, filing_data)
                    all_filings.append(filing_data)
                    logger.info(f"✅ Fetched 10-K from {filing.filing_date} ({len(content):,} chars)")
                except Exception as e:
                    logger.error(f"Failed to fetch 10-K content: {e}")

        except Exception as e:
            logger.warning(f"Could not fetch 10-K filings: {e}")

        # Fetch recent 8-Ks
        try:
            eight_k_filings = company.get_filings(form="8-K").head(4)
            logger.info(f"Found {len(eight_k_filings)} 8-K filing(s)")

            for filing in eight_k_filings:
                accession = filing.accession_number

                # Check cache first
                cached = self._get_from_cache(ticker, "8-K", accession)
                if cached:
                    all_filings.append(cached)
                    continue

                # Fetch from SEC
                try:
                    content = filing.text()
                    filing_data = {
                        "type": "8-K",
                        "date": str(filing.filing_date),
                        "content": content,
                        "content_length": len(content),
                        "url": filing.filing_homepage,
                        "accession_number": accession,
                        "company": company_name,
                    }
                    self._save_to_cache(ticker, "8-K", accession, filing_data)
                    all_filings.append(filing_data)
                    logger.info(f"✅ Fetched 8-K from {filing.filing_date} ({len(content):,} chars)")
                except Exception as e:
                    logger.error(f"Failed to fetch 8-K content: {e}")

        except Exception as e:
            logger.warning(f"Could not fetch 8-K filings: {e}")

        return {
            "company_name": company_name,
            "cik": company.cik,
            "ticker": ticker,
            "filings": all_filings,
            "total_filings": len(all_filings),
        }

    async def search_filings(
        self, ticker_or_cik: str, query: str, form_types: list[str] | None = None
    ) -> list[dict]:
        """Search SEC filings for specific content.

        Args:
            ticker_or_cik: Company ticker or CIK
            query: Search query
            form_types: Filing types to search (default: 10-K, 8-K)

        Returns:
            List of relevant filing excerpts
        """
        if form_types is None:
            form_types = ["10-K", "8-K"]

        # Get filings
        filings_data = await self.get_company_filings_for_research(ticker_or_cik, query)
        filings = filings_data.get("filings", [])

        # Simple search through content
        results = []
        query_lower = query.lower()

        for filing in filings:
            if filing["type"] not in form_types:
                continue

            content = filing.get("content", "")
            if query_lower in content.lower():
                # Find relevant excerpt
                idx = content.lower().find(query_lower)
                start = max(0, idx - 500)
                end = min(len(content), idx + 1500)
                excerpt = content[start:end]

                results.append({
                    "type": filing["type"],
                    "date": filing["date"],
                    "accession_number": filing["accession_number"],
                    "excerpt": excerpt,
                    "url": filing["url"],
                })

        logger.info(f"Found {len(results)} relevant sections for '{query}'")
        return results
