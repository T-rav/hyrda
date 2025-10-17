"""
SEC Document Builder

Builds comprehensive, searchable documents from SEC filings by combining:
1. Narrative text from 10-K/10-Q/8-K filings (using edgartools)
2. Financial metrics from SEC Company Facts API (structured XBRL data)

Output format is optimized for vector search and LLM consumption.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SECDocumentBuilder:
    """Builds searchable documents from SEC filings."""

    # Key financial metrics to extract from Company Facts API
    KEY_FINANCIAL_METRICS = {
        "Revenues": "Revenue / Sales",
        "NetIncomeLoss": "Net Income",
        "Assets": "Total Assets",
        "AssetsCurrent": "Current Assets",
        "Liabilities": "Total Liabilities",
        "StockholdersEquity": "Stockholders' Equity",
        "CashAndCashEquivalentsAtCarryingValue": "Cash and Cash Equivalents",
        "ResearchAndDevelopmentExpense": "R&D Expense",
        "OperatingExpenses": "Operating Expenses",
        "OperatingIncomeLoss": "Operating Income",
        "GrossProfit": "Gross Profit",
        "EarningsPerShareBasic": "EPS (Basic)",
        "EarningsPerShareDiluted": "EPS (Diluted)",
        "CommonStockSharesOutstanding": "Shares Outstanding",
        "PropertyPlantAndEquipmentNet": "Property, Plant & Equipment (Net)",
        "LongTermDebt": "Long-Term Debt",
        "CurrentDebt": "Current Debt",
    }

    def __init__(self):
        """Initialize document builder."""
        pass

    def build_financial_summary(self, company_facts: dict[str, Any] | None, years: int = 3) -> str:
        """
        Build a text summary of key financial metrics from Company Facts API.

        Args:
            company_facts: Company facts data from SEC API
            years: Number of years of history to include

        Returns:
            Formatted text summary of financial metrics
        """
        if not company_facts:
            return "Financial data not available.\n"

        entity_name = company_facts.get("entityName", "Unknown")
        facts = company_facts.get("facts", {})
        us_gaap = facts.get("us-gaap", {})

        summary = f"=== FINANCIAL SUMMARY: {entity_name} ===\n\n"

        for gaap_key, display_name in self.KEY_FINANCIAL_METRICS.items():
            if gaap_key not in us_gaap:
                continue

            metric_data = us_gaap[gaap_key]
            units = metric_data.get("units", {})

            # Try USD first, then shares
            values = units.get("USD", units.get("shares", []))

            if not values:
                continue

            # Get last N annual reports (10-K)
            annual_values = [v for v in values if v.get("form") == "10-K"]
            annual_values = sorted(annual_values, key=lambda x: x.get("end", ""), reverse=True)[:years]

            if not annual_values:
                continue

            summary += f"**{display_name}**\n"
            for v in annual_values:
                end_date = v.get("end", "N/A")
                fy = v.get("fy", "")
                val = v.get("val", 0)

                # Format value
                if gaap_key in ["EarningsPerShareBasic", "EarningsPerShareDiluted"]:
                    val_str = f"${val:.2f}"
                elif "shares" in units:
                    val_str = f"{val:,.0f} shares"
                elif val >= 1_000_000_000:
                    val_str = f"${val/1_000_000_000:.2f}B"
                elif val >= 1_000_000:
                    val_str = f"${val/1_000_000:.2f}M"
                else:
                    val_str = f"${val:,.0f}"

                summary += f"  FY{fy} ({end_date}): {val_str}\n"

            summary += "\n"

        return summary

    def build_10k_document(
        self,
        ticker_symbol: str,
        company_name: str,
        cik: str,
        filing_date: str,
        html_content: str,
        company_facts: dict[str, Any] | None = None,
    ) -> str:
        """
        Build a comprehensive 10-K document from HTML filing and company facts.

        Args:
            ticker_symbol: Stock ticker (e.g., "AAPL")
            company_name: Company name
            cik: Central Index Key
            filing_date: Filing date (YYYY-MM-DD)
            html_content: Raw HTML content from SEC filing
            company_facts: Optional company facts data from SEC API

        Returns:
            Formatted document text optimized for vector search
        """
        # Use HTML parser directly since we already have the HTML content
        # (edgartools is designed to fetch filings itself, not parse pre-fetched HTML)
        logger.info(f"Using fallback HTML parser for {ticker_symbol} 10-K")
        return self._build_document_fallback(ticker_symbol, company_name, cik, filing_date, html_content, "10-K", company_facts)

    def build_10q_document(
        self,
        ticker_symbol: str,
        company_name: str,
        cik: str,
        filing_date: str,
        html_content: str,
        company_facts: dict[str, Any] | None = None,
    ) -> str:
        """
        Build a 10-Q document from HTML filing and company facts.

        Args:
            ticker_symbol: Stock ticker
            company_name: Company name
            cik: Central Index Key
            filing_date: Filing date
            html_content: Raw HTML content
            company_facts: Optional company facts data

        Returns:
            Formatted document text
        """
        # Use HTML parser directly
        logger.info(f"Using fallback HTML parser for {ticker_symbol} 10-Q")
        return self._build_document_fallback(ticker_symbol, company_name, cik, filing_date, html_content, "10-Q", company_facts)

    def build_8k_document(
        self,
        ticker_symbol: str,
        company_name: str,
        cik: str,
        filing_date: str,
        html_content: str,
    ) -> str:
        """
        Build an 8-K document from HTML filing.

        8-K reports contain material events (acquisitions, executive changes, etc.)

        Args:
            ticker_symbol: Stock ticker
            company_name: Company name
            cik: Central Index Key
            filing_date: Filing date
            html_content: Raw HTML content

        Returns:
            Formatted document text
        """
        # Use HTML parser directly
        logger.info(f"Using fallback HTML parser for {ticker_symbol} 8-K")
        return self._build_document_fallback(ticker_symbol, company_name, cik, filing_date, html_content, "8-K", None)

    def _build_document_fallback(
        self,
        ticker_symbol: str,
        company_name: str,
        cik: str,
        filing_date: str,
        html_content: str,
        filing_type: str,
        company_facts: dict[str, Any] | None = None,
    ) -> str:
        """
        Fallback method using simple HTML parsing if edgartools fails.

        Args:
            ticker_symbol: Stock ticker
            company_name: Company name
            cik: Central Index Key
            filing_date: Filing date
            html_content: Raw HTML content
            filing_type: Filing type (10-K, 10-Q, 8-K)
            company_facts: Optional company facts data

        Returns:
            Formatted document text
        """
        from bs4 import BeautifulSoup
        import re

        logger.info(f"Using fallback HTML parser for {ticker_symbol} {filing_type}")

        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script, style, and head elements
        for element in soup(["script", "style", "head"]):
            element.decompose()

        # Get text
        text = soup.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        text = re.sub(r" +", " ", text)

        # Build document
        doc = f"""Company: {company_name} ({ticker_symbol})
Filing Type: {filing_type}
Filing Date: {filing_date}
CIK: {cik}

"""

        if company_facts:
            doc += self.build_financial_summary(company_facts, years=3)
            doc += "\n"

        doc += f"=== FILING CONTENT ===\n{text}\n"

        logger.info(f"Built {filing_type} document (fallback) for {ticker_symbol}: {len(doc)} characters")
        return doc
