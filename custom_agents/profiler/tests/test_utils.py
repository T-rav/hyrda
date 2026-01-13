"""Tests for company profile utils module."""

from unittest.mock import Mock, patch

import pytest

from agents.profiler.utils import extract_company_from_url


@pytest.mark.asyncio
class TestExtractCompanyFromUrl:
    """Tests for extract_company_from_url function."""

    async def test_extract_from_og_site_name(self):
        """Test extraction from og:site_name meta tag."""
        mock_html = """
        <html>
            <head>
                <meta property="og:site_name" content="Costco Wholesale" />
                <title>Welcome to Costco</title>
            </head>
        </html>
        """

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.content = mock_html.encode()
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = await extract_company_from_url("www.costco.com")

            assert result == "Costco Wholesale"
            mock_get.assert_called_once()

    async def test_extract_from_twitter_site(self):
        """Test extraction from twitter:site meta tag."""
        mock_html = """
        <html>
            <head>
                <meta name="twitter:site" content="@stripe" />
                <title>Stripe - Payment Processing</title>
            </head>
        </html>
        """

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.content = mock_html.encode()
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = await extract_company_from_url("https://stripe.com")

            # Should strip @ symbol
            assert result == "stripe"

    async def test_extract_from_title_tag(self):
        """Test extraction from title tag with cleanup."""
        mock_html = """
        <html>
            <head>
                <title>Tesla, Inc. | Official Site</title>
            </head>
        </html>
        """

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.content = mock_html.encode()
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = await extract_company_from_url("tesla.com")

            # Should remove " | Official Site"
            assert result == "Tesla, Inc."

    async def test_extract_from_og_title_fallback(self):
        """Test extraction from og:title as fallback."""
        mock_html = """
        <html>
            <head>
                <meta property="og:title" content="Microsoft Corporation" />
                <title>Home</title>
            </head>
        </html>
        """

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.content = mock_html.encode()
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = await extract_company_from_url("https://www.microsoft.com")

            assert result == "Microsoft Corporation"

    async def test_adds_https_to_url_without_protocol(self):
        """Test that URLs without protocol get https:// added."""
        mock_html = """
        <html>
            <head>
                <meta property="og:site_name" content="Example" />
            </head>
        </html>
        """

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.content = mock_html.encode()
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            await extract_company_from_url("example.com")

            # Should have called with https://
            called_url = mock_get.call_args[0][0]
            assert called_url == "https://example.com"

    async def test_returns_none_on_http_error(self):
        """Test that HTTP errors return None."""
        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Connection error")

            result = await extract_company_from_url("https://invalid-url.com")

            assert result is None

    async def test_returns_none_when_no_company_name_found(self):
        """Test returns None when page has no extractable company name."""
        mock_html = """
        <html>
            <head>
                <title></title>
            </head>
        </html>
        """

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.content = mock_html.encode()
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = await extract_company_from_url("https://example.com")

            assert result is None

    async def test_timeout_set_to_10_seconds(self):
        """Test that requests use a 10 second timeout."""
        mock_html = """
        <html>
            <head>
                <meta property="og:site_name" content="Test" />
            </head>
        </html>
        """

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.content = mock_html.encode()
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            await extract_company_from_url("https://example.com")

            # Verify timeout parameter
            assert mock_get.call_args[1]["timeout"] == 10

    async def test_user_agent_header_set(self):
        """Test that User-Agent header is set."""
        mock_html = """
        <html>
            <head>
                <meta property="og:site_name" content="Test" />
            </head>
        </html>
        """

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.content = mock_html.encode()
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            await extract_company_from_url("https://example.com")

            # Verify User-Agent header
            headers = mock_get.call_args[1]["headers"]
            assert "User-Agent" in headers
            assert "Mozilla" in headers["User-Agent"]
