"""
SEC Symbol Service

Service for managing the sec_symbol_data reference table.
Populates and maintains the mapping of ticker symbols to CIKs for all public companies.
"""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Mapped, mapped_column

# Add tasks directory to path for imports
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.base import Base, get_data_db_session  # noqa: E402
from sqlalchemy import Boolean, DateTime, Integer, String, text  # noqa: E402

logger = logging.getLogger(__name__)


class SECSymbol(Base):
    """Model for SEC symbol reference data."""

    __tablename__ = "sec_symbol_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker_symbol: Mapped[str] = mapped_column(
        String(10), nullable=False, unique=True, comment="Stock ticker symbol (e.g., AAPL)"
    )
    cik: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="Central Index Key (zero-padded to 10 digits) - NOT unique, companies can have multiple tickers",
    )
    company_name: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="Company name"
    )
    exchange: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="Exchange (NYSE, NASDAQ, etc.)"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="1", comment="Whether symbol is active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class SECSymbolService:
    """Service for managing SEC symbol reference data."""

    def __init__(self):
        """Initialize SEC symbol service."""
        pass

    @staticmethod
    def fetch_sec_ticker_mapping() -> dict[str, dict[str, Any]]:
        """
        Fetch the official SEC ticker-to-CIK mapping from SEC's company_tickers.json.

        Downloads the latest list of all public companies (~13,000+ companies).

        Returns:
            Dictionary mapping ticker -> {cik, company_name}

        Example:
            {
                "AAPL": {"cik": "0000320193", "company_name": "Apple Inc."},
                "MSFT": {"cik": "0000789019", "company_name": "Microsoft Corp"},
                ...
            }
        """
        import httpx

        url = "https://www.sec.gov/files/company_tickers.json"
        headers = {"User-Agent": "8th Light InsightMesh insightmesh@8thlight.com"}

        try:
            logger.info("Downloading SEC ticker mapping from company_tickers.json...")
            response = httpx.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()

            # SEC format: {0: {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc"}, ...}
            data = response.json()

            # Convert to {ticker: {cik, company_name, exchange}} mapping
            ticker_map = {}
            for entry in data.values():
                ticker = entry["ticker"].upper()
                cik = str(entry["cik_str"]).zfill(10)  # Pad to 10 digits
                company_name = entry["title"]

                ticker_map[ticker] = {
                    "cik": cik,
                    "company_name": company_name,
                    "exchange": None,  # Will populate below
                }

            logger.info(f"Loaded {len(ticker_map)} ticker-to-CIK mappings")

            # Fetch exchange data from company_tickers_exchange.json
            exchange_url = "https://www.sec.gov/files/company_tickers_exchange.json"
            try:
                logger.info("Fetching exchange data from company_tickers_exchange.json...")
                exchange_response = httpx.get(exchange_url, headers=headers, timeout=30.0)
                exchange_response.raise_for_status()

                # Format: {"fields": ["cik", "name", "ticker", "exchange"], "data": [[320193, "Apple Inc.", "AAPL", "Nasdaq"], ...]}
                exchange_data = exchange_response.json()

                if "data" in exchange_data and "fields" in exchange_data:
                    fields = exchange_data["fields"]
                    ticker_idx = fields.index("ticker")
                    exchange_idx = fields.index("exchange")

                    # Update ticker_map with exchange data
                    exchange_count = 0
                    for row in exchange_data["data"]:
                        ticker = str(row[ticker_idx]).upper()
                        exchange = row[exchange_idx]

                        if ticker in ticker_map and exchange:
                            ticker_map[ticker]["exchange"] = exchange
                            exchange_count += 1

                    logger.info(f"Added exchange data for {exchange_count} tickers")
                else:
                    logger.warning("Exchange data not in expected format")

            except Exception as e:
                logger.warning(f"Could not fetch exchange data (non-critical): {e}")
                # Continue without exchange data

            return ticker_map

        except Exception as e:
            logger.error(f"Failed to load SEC ticker mapping: {e}")
            raise

    def populate_symbol_table(self, force_refresh: bool = False) -> dict[str, Any]:
        """
        Populate the sec_symbol_data table with all public company tickers from SEC.

        Args:
            force_refresh: If True, delete existing data and repopulate

        Returns:
            Dictionary with statistics:
                {
                    "total_fetched": 13000,
                    "inserted": 13000,
                    "updated": 0,
                    "deleted": 0,
                    "errors": 0
                }
        """
        stats = {
            "total_fetched": 0,
            "inserted": 0,
            "updated": 0,
            "deleted": 0,
            "errors": 0,
        }

        try:
            # Fetch latest ticker mapping from SEC
            ticker_map = self.fetch_sec_ticker_mapping()
            stats["total_fetched"] = len(ticker_map)

            with get_data_db_session() as session:
                if force_refresh:
                    # Delete all existing data
                    result = session.execute(delete(SECSymbol))
                    stats["deleted"] = result.rowcount
                    logger.info(f"Deleted {stats['deleted']} existing symbols")

                # Get existing symbols for update/insert logic
                existing_stmt = select(SECSymbol.ticker_symbol, SECSymbol.cik)
                existing_result = session.execute(existing_stmt)
                existing_symbols = {
                    row.ticker_symbol: row.cik for row in existing_result
                }

                # Prepare bulk insert/update
                to_insert = []
                to_update = []

                for ticker, data in ticker_map.items():
                    cik = data["cik"]
                    company_name = data["company_name"]
                    exchange = data.get("exchange")

                    if ticker in existing_symbols:
                        # Update if CIK or name changed
                        if existing_symbols[ticker] != cik:
                            to_update.append(
                                {
                                    "ticker_symbol": ticker,
                                    "cik": cik,
                                    "company_name": company_name,
                                    "exchange": exchange,
                                    "is_active": True,
                                }
                            )
                    else:
                        # Insert new symbol
                        to_insert.append(
                            {
                                "ticker_symbol": ticker,
                                "cik": cik,
                                "company_name": company_name,
                                "exchange": exchange,
                                "is_active": True,
                            }
                        )

                # Bulk insert new symbols
                # Note: ticker_symbol is unique, so duplicates will be skipped
                if to_insert:
                    session.execute(insert(SECSymbol), to_insert)
                    stats["inserted"] = len(to_insert)
                    logger.info(f"Inserted {stats['inserted']} new symbols")

                # Bulk update existing symbols
                if to_update:
                    for symbol_data in to_update:
                        session.execute(
                            update(SECSymbol)
                            .where(
                                SECSymbol.ticker_symbol == symbol_data["ticker_symbol"]
                            )
                            .values(
                                cik=symbol_data["cik"],
                                company_name=symbol_data["company_name"],
                                exchange=symbol_data["exchange"],
                                is_active=symbol_data["is_active"],
                            )
                        )
                    stats["updated"] = len(to_update)
                    logger.info(f"Updated {stats['updated']} symbols")

                session.commit()

                logger.info(
                    f"SEC symbol table populated: {stats['inserted']} inserted, "
                    f"{stats['updated']} updated, {stats['deleted']} deleted"
                )

        except Exception as e:
            logger.error(f"Error populating symbol table: {e}")
            stats["errors"] = 1
            raise

        return stats

    def lookup_ticker(self, ticker_symbol: str) -> dict[str, Any] | None:
        """
        Look up company info by ticker symbol.

        Args:
            ticker_symbol: Stock ticker (e.g., "AAPL")

        Returns:
            Dictionary with {ticker, cik, company_name} or None if not found
        """
        with get_data_db_session() as session:
            stmt = select(SECSymbol).where(
                SECSymbol.ticker_symbol == ticker_symbol.upper()
            )
            result = session.execute(stmt).scalar_one_or_none()

            if result:
                return {
                    "ticker_symbol": result.ticker_symbol,
                    "cik": result.cik,
                    "company_name": result.company_name,
                    "exchange": result.exchange,
                    "is_active": result.is_active,
                }
            return None

    def lookup_cik(self, cik: str) -> dict[str, Any] | None:
        """
        Look up company info by CIK.

        Args:
            cik: Central Index Key (with or without padding)

        Returns:
            Dictionary with {ticker, cik, company_name} or None if not found
        """
        cik_padded = cik.zfill(10)

        with get_data_db_session() as session:
            stmt = select(SECSymbol).where(SECSymbol.cik == cik_padded)
            result = session.execute(stmt).scalar_one_or_none()

            if result:
                return {
                    "ticker_symbol": result.ticker_symbol,
                    "cik": result.cik,
                    "company_name": result.company_name,
                    "exchange": result.exchange,
                    "is_active": result.is_active,
                }
            return None

    def get_all_symbols(self, active_only: bool = True) -> list[dict[str, Any]]:
        """
        Get all symbols from the database.

        Args:
            active_only: If True, only return active symbols

        Returns:
            List of dictionaries with symbol data
        """
        with get_data_db_session() as session:
            stmt = select(SECSymbol)
            if active_only:
                stmt = stmt.where(SECSymbol.is_active == True)  # noqa: E712

            results = session.execute(stmt).scalars().all()

            return [
                {
                    "ticker_symbol": result.ticker_symbol,
                    "cik": result.cik,
                    "company_name": result.company_name,
                    "exchange": result.exchange,
                    "is_active": result.is_active,
                }
                for result in results
            ]
