"""
SEC Edgar Client

Client for fetching SEC filings from the Edgar API.
Free API, no authentication required, just needs a User-Agent header.
"""

import asyncio
import logging
import re
from functools import lru_cache
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SECEdgarClient:
    """Client for SEC Edgar API."""

    def __init__(self, user_agent: str = "Research Bot research@example.com"):
        """
        Initialize SEC Edgar client.

        Args:
            user_agent: User-Agent header (required by SEC)
                       Format: "8th Light insightmesh@8thlight.com"
        """
        self.base_url = "https://data.sec.gov"
        self.archive_url = "https://www.sec.gov/Archives/edgar/data"
        self.headers = {"User-Agent": user_agent}
        self.rate_limit_delay = 0.1  # SEC requests 10 requests/second max

    async def get_company_info(self, cik: str) -> dict[str, Any]:
        """
        Get company information and recent filings.

        Args:
            cik: Central Index Key (can be with or without leading zeros)

        Returns:
            Dictionary with company info and recent filings
        """
        # Pad CIK to 10 digits
        cik_padded = cik.zfill(10)
        url = f"{self.base_url}/submissions/CIK{cik_padded}.json"

        logger.info(f"Fetching company info for CIK {cik}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()

            await asyncio.sleep(self.rate_limit_delay)  # Rate limiting

            return response.json()

    async def get_company_facts(self, cik: str) -> dict[str, Any] | None:
        """
        Get company financial facts from SEC Company Facts API.

        Returns structured XBRL data (500+ standardized metrics) in JSON format.
        Includes revenue, assets, R&D spending, margins, etc. across all years.

        Args:
            cik: Central Index Key

        Returns:
            Dictionary with company facts data, or None if not available

        Example response structure:
            {
                "cik": 320193,
                "entityName": "Apple Inc.",
                "facts": {
                    "us-gaap": {
                        "Revenues": {
                            "label": "Revenue",
                            "description": "...",
                            "units": {
                                "USD": [
                                    {"end": "2024-09-28", "val": 391035000000, "form": "10-K", "fy": 2024},
                                    ...
                                ]
                            }
                        },
                        "ResearchAndDevelopmentExpense": {...},
                        ...
                    }
                }
            }
        """
        cik_padded = cik.zfill(10)
        url = f"{self.base_url}/api/xbrl/companyfacts/CIK{cik_padded}.json"

        logger.info(f"Fetching company facts for CIK {cik}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()

                await asyncio.sleep(self.rate_limit_delay)  # Rate limiting

                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Company facts not available for CIK {cik}")
                return None
            raise

    async def get_recent_filings(
        self, cik: str, filing_type: str = "10-K", limit: int = 5
    ) -> list[dict[str, Any]]:
        """
        Get recent filings of a specific type for a company.

        Args:
            cik: Central Index Key
            filing_type: Type of filing (10-K, 10-Q, 8-K, DEF 14A, etc.)
            limit: Maximum number of filings to return

        Returns:
            List of filing metadata dictionaries
        """
        company_data = await self.get_company_info(cik)

        filings = []
        recent = company_data.get("filings", {}).get("recent", {})

        if not recent:
            return []

        # Iterate through recent filings
        forms = recent.get("form", [])
        filing_dates = recent.get("filingDate", [])
        accession_numbers = recent.get("accessionNumber", [])
        primary_documents = recent.get("primaryDocument", [])
        primary_doc_descriptions = recent.get("primaryDocDescription", [])

        for i, form in enumerate(forms):
            if form == filing_type and len(filings) < limit:
                accession = accession_numbers[i]
                filings.append(
                    {
                        "cik": cik,
                        "company_name": company_data.get("name", "Unknown"),
                        "form": form,
                        "filing_date": filing_dates[i],
                        "accession_number": accession,
                        "primary_document": primary_documents[i],
                        "description": primary_doc_descriptions[i],
                        "url": self._build_document_url(
                            cik, accession, primary_documents[i]
                        ),
                    }
                )

        logger.info(f"Found {len(filings)} {filing_type} filings for CIK {cik}")
        return filings

    def _build_document_url(
        self, cik: str, accession_number: str, filename: str
    ) -> str:
        """
        Build the URL to access a specific document.

        Args:
            cik: Central Index Key
            accession_number: SEC accession number (with dashes)
            filename: Primary document filename

        Returns:
            Full URL to the document
        """
        # Remove dashes from accession number for URL
        accession_clean = accession_number.replace("-", "")

        # CIK as integer (no leading zeros)
        cik_int = str(int(cik))

        return f"{self.archive_url}/{cik_int}/{accession_clean}/{filename}"

    async def download_filing(
        self, cik: str, accession_number: str, filename: str
    ) -> str:
        """
        Download the full text of a filing.

        Args:
            cik: Central Index Key
            accession_number: SEC accession number
            filename: Document filename

        Returns:
            Full text content of the filing
        """
        url = self._build_document_url(cik, accession_number, filename)

        logger.info(f"Downloading filing from {url}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()

            await asyncio.sleep(self.rate_limit_delay)  # Rate limiting

            content = response.text
            logger.info(f"Downloaded {len(content)} characters")

            return content

    def parse_html_filing(self, html_content: str) -> str:
        """
        Parse HTML filing and extract clean text.

        Args:
            html_content: Raw HTML content from SEC filing

        Returns:
            Clean text content
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "head"]):
            element.decompose()

        # Get text
        text = soup.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        text = re.sub(r" +", " ", text)

        return text

    async def get_filing_with_content(
        self, cik: str, filing_type: str = "10-K", index: int = 0
    ) -> dict[str, Any] | None:
        """
        Get a specific filing with its full content.

        Args:
            cik: Central Index Key
            filing_type: Type of filing (10-K, 10-Q, 8-K)
            index: Which filing to get (0 = most recent, 1 = second most recent, etc.)

        Returns:
            Dictionary with filing metadata and content, or None if not found
        """
        filings = await self.get_recent_filings(cik, filing_type, limit=index + 1)

        if len(filings) <= index:
            logger.warning(
                f"No {filing_type} filing found at index {index} for CIK {cik}"
            )
            return None

        filing = filings[index]

        # Download the content
        content = await self.download_filing(
            cik, filing["accession_number"], filing["primary_document"]
        )

        # Parse HTML to clean text if it's HTML
        if filing["primary_document"].endswith(".htm") or filing[
            "primary_document"
        ].endswith(".html"):
            content = self.parse_html_filing(content)

        filing["content"] = content
        filing["content_length"] = len(content)

        return filing

    @staticmethod
    @lru_cache(maxsize=1)
    def _load_sec_ticker_mapping() -> dict[str, str]:
        """
        Load the official SEC ticker-to-CIK mapping.

        Downloads from SEC's company_tickers.json (13,000+ companies).
        Cached after first call for performance.

        Returns:
            Dictionary mapping ticker -> CIK (zero-padded to 10 digits)
        """
        import httpx

        url = "https://www.sec.gov/files/company_tickers.json"
        headers = {"User-Agent": "Research Bot research@example.com"}

        try:
            logger.info("Downloading SEC ticker mapping (13,000+ companies)...")
            response = httpx.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()

            # SEC format: {0: {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc"}, ...}
            data = response.json()

            # Convert to {ticker: CIK} mapping with zero-padded CIKs
            ticker_map = {}
            for entry in data.values():
                ticker = entry["ticker"].upper()
                cik = str(entry["cik_str"]).zfill(10)  # Pad to 10 digits
                ticker_map[ticker] = cik

            logger.info(f"Loaded {len(ticker_map)} ticker-to-CIK mappings")
            return ticker_map

        except Exception as e:
            logger.error(f"Failed to load SEC ticker mapping: {e}")
            logger.warning("Falling back to hardcoded tickers")

            # Fallback to known tickers if SEC API fails
            return {
                "AAPL": "0000320193",  # Apple
                "MSFT": "0000789019",  # Microsoft
                "GOOGL": "0001652044",  # Alphabet (Google)
                "AMZN": "0001018724",  # Amazon
                "META": "0001326801",  # Meta (Facebook)
                "TSLA": "0001318605",  # Tesla
                "NVDA": "0001045810",  # NVIDIA
                "NFLX": "0001065280",  # Netflix
                "CRM": "0001108524",  # Salesforce
                "ORCL": "0001341439",  # Oracle
            }

    @staticmethod
    def lookup_cik(ticker_symbol: str) -> str | None:
        """
        Look up CIK from ticker symbol using SEC's official company tickers.

        Supports 13,000+ publicly traded companies (large, mid, small cap).
        Downloads official SEC mapping on first call, then caches.

        Args:
            ticker_symbol: Stock ticker symbol (e.g., "AAPL", "COST", "ZM")

        Returns:
            CIK string (zero-padded to 10 digits) or None if not found

        Examples:
            >>> SECEdgarClient.lookup_cik("AAPL")  # Apple
            "0000320193"
            >>> SECEdgarClient.lookup_cik("ZM")    # Zoom (mid-cap)
            "0001585521"
        """
        ticker_map = SECEdgarClient._load_sec_ticker_mapping()
        return ticker_map.get(ticker_symbol.upper())

    @staticmethod
    def get_all_tickers() -> dict[str, str]:
        """
        Get all public company tickers and their CIKs from SEC.

        Downloads official SEC company tickers list (13,000+ companies).
        Cached after first call for performance.

        Returns:
            Dictionary mapping ticker symbols to CIKs (e.g., {"AAPL": "0000320193", ...})

        Examples:
            >>> tickers = SECEdgarClient.get_all_tickers()
            >>> len(tickers)
            10142
            >>> tickers["AAPL"]
            "0000320193"
        """
        return SECEdgarClient._load_sec_ticker_mapping()
