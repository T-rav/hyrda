"""Tests for SEC on-demand service."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from agents.company_profile.services.sec_on_demand import SECOnDemandFetcher


class TestSECCIKLookup:
    """Tests for CIK lookup functionality."""

    @pytest.mark.asyncio
    async def test_lookup_cik_by_ticker(self):
        """Test CIK lookup with exact ticker symbol match."""
        service = SECOnDemandFetcher()

        # Mock SEC company tickers JSON response
        mock_data = {
            "0": {
                "cik_str": 909832,
                "ticker": "COST",
                "title": "Costco Wholesale Corp",
            },
            "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json = Mock(return_value=mock_data)
            mock_response.raise_for_status = Mock()

            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=Mock(get=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock()

            # Test exact ticker match
            cik = await service._lookup_cik("COST")

            assert cik == "0000909832"

    @pytest.mark.asyncio
    async def test_lookup_cik_by_company_name(self):
        """Test CIK lookup with fuzzy company name match."""
        service = SECOnDemandFetcher()

        mock_data = {
            "0": {
                "cik_str": 909832,
                "ticker": "COST",
                "title": "Costco Wholesale Corp",
            },
            "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json = Mock(return_value=mock_data)
            mock_response.raise_for_status = Mock()

            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=Mock(get=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock()

            # Test fuzzy company name match
            cik = await service._lookup_cik("Costco")

            assert cik == "0000909832"

    @pytest.mark.asyncio
    async def test_lookup_cik_case_insensitive_ticker(self):
        """Test that ticker lookup is case-insensitive."""
        service = SECOnDemandFetcher()

        mock_data = {
            "0": {
                "cik_str": 909832,
                "ticker": "COST",
                "title": "Costco Wholesale Corp",
            },
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json = Mock(return_value=mock_data)
            mock_response.raise_for_status = Mock()

            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=Mock(get=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock()

            # Test lowercase ticker
            cik = await service._lookup_cik("cost")

            assert cik == "0000909832"

    @pytest.mark.asyncio
    async def test_lookup_cik_not_found(self):
        """Test CIK lookup returns None when identifier not found."""
        service = SECOnDemandFetcher()

        mock_data = {
            "0": {
                "cik_str": 909832,
                "ticker": "COST",
                "title": "Costco Wholesale Corp",
            },
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json = Mock(return_value=mock_data)
            mock_response.raise_for_status = Mock()

            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=Mock(get=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock()

            # Test non-existent identifier
            cik = await service._lookup_cik("NONEXISTENT")

            assert cik is None

    @pytest.mark.asyncio
    async def test_lookup_cik_handles_api_error(self):
        """Test CIK lookup handles SEC API errors gracefully."""
        service = SECOnDemandFetcher()

        with patch("httpx.AsyncClient") as mock_client:
            # Simulate API error
            mock_client.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("SEC API unavailable")
            )
            mock_client.return_value.__aexit__ = AsyncMock()

            # Should return None on error, not raise
            cik = await service._lookup_cik("COST")

            assert cik is None

    @pytest.mark.asyncio
    async def test_lookup_cik_company_name_substring_match(self):
        """Test that company name matching works with substring."""
        service = SECOnDemandFetcher()

        mock_data = {
            "0": {
                "cik_str": 789019,
                "ticker": "MSFT",
                "title": "Microsoft Corporation",
            },
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json = Mock(return_value=mock_data)
            mock_response.raise_for_status = Mock()

            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=Mock(get=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock()

            # "Microsoft" is substring of "Microsoft Corporation"
            cik = await service._lookup_cik("Microsoft")

            assert cik == "0000789019"

    @pytest.mark.asyncio
    async def test_lookup_cik_first_word_match(self):
        """Test that company name matching works with first word of company name."""
        service = SECOnDemandFetcher()

        mock_data = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc"},
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json = Mock(return_value=mock_data)
            mock_response.raise_for_status = Mock()

            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=Mock(get=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock()

            # "Apple" matches first word of "Apple Inc"
            cik = await service._lookup_cik("Apple")

            assert cik == "0000320193"
