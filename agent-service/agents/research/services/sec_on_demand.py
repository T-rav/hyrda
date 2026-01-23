"""On-Demand SEC Document Fetcher for Deep Research

Fetches and processes SEC filings just-in-time for research queries.
No persistence - all vectorization happens in-memory.
"""

import asyncio
import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SECOnDemandFetcher:
    """Fetch SEC documents on-demand for research without persistence."""

    def __init__(
        self, user_agent: str = "8th Light InsightMesh insightmesh@8thlight.com"
    ):
        """
        Initialize SEC on-demand fetcher.

        Args:
            user_agent: User-Agent header (required by SEC)
        """
        self.base_url = "https://data.sec.gov"
        self.archive_url = "https://www.sec.gov/Archives/edgar/data"
        self.headers = {"User-Agent": user_agent}
        self.rate_limit_delay = 0.1  # SEC requests 10 requests/second max

    async def get_company_filings_for_research(
        self, ticker_or_cik: str, query: str | None = None
    ) -> dict[str, Any]:
        """
        Fetch latest SEC filings for a company for research purposes.

        Fetches:
        - Latest 10-K (annual report)
        - 4 most recent 8-Ks (material events)

        All processing is done in-memory with no persistence.

        Args:
            ticker_or_cik: Company ticker symbol or CIK
            query: Optional query to focus on relevant sections

        Returns:
            Dictionary with filing contents and metadata
        """
        # Look up CIK if ticker provided
        if not ticker_or_cik.isdigit():
            cik = await self._lookup_cik(ticker_or_cik)
            if not cik:
                raise ValueError(f"Could not find CIK for ticker: {ticker_or_cik}")
        else:
            cik = ticker_or_cik.zfill(10)

        logger.info(f"Fetching SEC filings for CIK {cik}")

        # Fetch company info and recent filings
        company_data = await self._get_company_info(cik)
        company_name = company_data.get("name", "Unknown")

        # Fetch latest 10-K
        ten_k_filings = await self._get_recent_filings(cik, "10-K", limit=1)

        # Fetch 4 most recent 8-Ks
        eight_k_filings = await self._get_recent_filings(cik, "8-K", limit=4)

        logger.info(
            f"Found {len(ten_k_filings)} 10-K and {len(eight_k_filings)} 8-K filings"
        )

        # Download and process all filings
        all_filings = []

        for filing in ten_k_filings + eight_k_filings:
            try:
                content = await self._download_filing(
                    cik, filing["accession_number"], filing["primary_document"]
                )

                # Parse HTML to clean text
                if filing["primary_document"].endswith((".htm", ".html")):
                    content = self._parse_html_filing(content)

                filing_data = {
                    "type": filing["form"],
                    "date": filing["filing_date"],
                    "content": content,
                    "content_length": len(content),
                    "url": filing["url"],
                    "accession_number": filing["accession_number"],
                }

                all_filings.append(filing_data)
                logger.info(
                    f"✅ Downloaded {filing['form']} from {filing['filing_date']} "
                    f"({len(content):,} characters)"
                )

            except Exception as e:
                logger.error(
                    f"Failed to download {filing['form']} {filing['accession_number']}: {e}"
                )
                continue

        return {
            "company_name": company_name,
            "cik": cik,
            "filings": all_filings,
            "total_filings": len(all_filings),
            "total_characters": sum(f["content_length"] for f in all_filings),
        }

    async def _get_company_info(self, cik: str) -> dict[str, Any]:
        """Fetch company information from SEC API."""
        cik_padded = cik.zfill(10)
        url = f"{self.base_url}/submissions/CIK{cik_padded}.json"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            await asyncio.sleep(self.rate_limit_delay)
            return response.json()

    async def _get_recent_filings(
        self, cik: str, filing_type: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Get recent filings of a specific type."""
        company_data = await self._get_company_info(cik)

        filings = []
        recent = company_data.get("filings", {}).get("recent", {})

        if not recent:
            return []

        forms = recent.get("form", [])
        filing_dates = recent.get("filingDate", [])
        accession_numbers = recent.get("accessionNumber", [])
        primary_documents = recent.get("primaryDocument", [])

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
                        "url": self._build_document_url(
                            cik, accession, primary_documents[i]
                        ),
                    }
                )

        return filings

    def _build_document_url(
        self, cik: str, accession_number: str, filename: str
    ) -> str:
        """Build URL to access a specific document."""
        accession_clean = accession_number.replace("-", "")
        cik_int = str(int(cik))
        return f"{self.archive_url}/{cik_int}/{accession_clean}/{filename}"

    async def _download_filing(
        self, cik: str, accession_number: str, filename: str
    ) -> str:
        """Download the full text of a filing."""
        url = self._build_document_url(cik, accession_number, filename)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            await asyncio.sleep(self.rate_limit_delay)
            return response.text

    def _parse_html_filing(self, html_content: str) -> str:
        """Parse HTML filing and extract clean text."""
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "head"]):
            element.decompose()

        # Get text
        text = soup.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        import re

        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        text = re.sub(r" +", " ", text)

        return text

    async def _lookup_cik(self, identifier: str) -> str | None:
        """Look up CIK from ticker symbol or company name using SEC's official mapping.

        Args:
            identifier: Ticker symbol (e.g., "COST") or company name (e.g., "Costco")

        Returns:
            CIK string zero-padded to 10 digits, or None if not found
        """
        url = "https://www.sec.gov/files/company_tickers.json"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()

                data = response.json()

                # First try exact ticker match (case-insensitive)
                identifier_upper = identifier.upper()
                for entry in data.values():
                    if entry["ticker"].upper() == identifier_upper:
                        cik = str(entry["cik_str"]).zfill(10)
                        logger.info(f"Found CIK {cik} for ticker '{identifier}'")
                        return cik

                # If ticker not found, try fuzzy company name match
                identifier_lower = identifier.lower()
                for entry in data.values():
                    company_name = entry["title"].lower()
                    # Check if identifier is a substring of company name or vice versa
                    if (
                        identifier_lower in company_name
                        or company_name.split()[0] == identifier_lower
                    ):
                        cik = str(entry["cik_str"]).zfill(10)
                        logger.info(
                            f"Found CIK {cik} for company name '{identifier}' "
                            f"(matched: {entry['title']})"
                        )
                        return cik

                logger.warning(
                    f"No CIK found for '{identifier}'. "
                    f"Try using the ticker symbol (e.g., 'COST' instead of 'Costco')"
                )
                return None

        except Exception as e:
            logger.error(f"Failed to lookup CIK for {identifier}: {e}")
            return None

    def chunk_filing_content(
        self, content: str, chunk_size: int = 2000, overlap: int = 200
    ) -> list[str]:
        """
        Chunk filing content for vectorization.

        Args:
            content: Full filing text
            chunk_size: Maximum characters per chunk
            overlap: Characters to overlap between chunks

        Returns:
            List of text chunks
        """
        chunks = []
        start = 0

        while start < len(content):
            end = start + chunk_size
            chunk = content[start:end]

            # Try to break at paragraph boundary
            if end < len(content):
                last_newline = chunk.rfind("\n\n")
                if last_newline > chunk_size // 2:
                    chunk = chunk[:last_newline]
                    end = start + last_newline

            chunks.append(chunk.strip())
            start = end - overlap

        logger.info(f"Created {len(chunks)} chunks from {len(content):,} characters")
        return chunks
