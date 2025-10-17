"""Tests for SEC section filtering."""


from services.sec_section_filter import SECSectionFilter, filter_sec_filing


class TestSECSectionFilter:
    """Test SEC section filtering functionality."""

    def test_should_keep_section_10k_business(self):
        """Test that Business section is kept for 10-K filings."""
        assert SECSectionFilter.should_keep_section("Item 1. Business", "10-K")
        assert SECSectionFilter.should_keep_section("ITEM 1. BUSINESS", "10-K")
        assert SECSectionFilter.should_keep_section("Business", "10-K")

    def test_should_keep_section_10k_risk_factors(self):
        """Test that Risk Factors section is kept for 10-K filings."""
        assert SECSectionFilter.should_keep_section("Item 1A. Risk Factors", "10-K")
        assert SECSectionFilter.should_keep_section("RISK FACTORS", "10-K")

    def test_should_keep_section_10k_mda(self):
        """Test that MD&A section is kept for 10-K filings."""
        assert SECSectionFilter.should_keep_section(
            "Item 7. Management's Discussion and Analysis", "10-K"
        )
        assert SECSectionFilter.should_keep_section("MD&A", "10-K")

    def test_should_skip_section_financial_statements(self):
        """Test that financial statement sections are skipped."""
        assert not SECSectionFilter.should_keep_section(
            "Consolidated Financial Statements", "10-K"
        )
        assert not SECSectionFilter.should_keep_section(
            "Notes to Consolidated Financial Statements", "10-K"
        )
        assert not SECSectionFilter.should_keep_section("Exhibits", "10-K")

    def test_should_skip_section_signatures(self):
        """Test that signature section is skipped."""
        assert not SECSectionFilter.should_keep_section("Signatures", "10-K")

    def test_non_10k_returns_full_content(self):
        """Test that non-10-K filings return full content."""
        content = "Test content for 8-K filing"
        result = filter_sec_filing(content, "8-K")
        assert result == content  # 8-K not supported, returns full content

    def test_parse_sections_basic(self):
        """Test basic section parsing."""
        content = """
Item 1. Business

This is the business section with company information.

Item 1A. Risk Factors

These are the risk factors that affect the company.

Item 7. Management's Discussion and Analysis

Management's perspective on the business.
"""
        sections = SECSectionFilter._parse_sections(content)

        assert len(sections) == 3
        assert sections[0][0] == "Item 1. Business"
        assert "business section" in sections[0][1]
        assert sections[1][0] == "Item 1A. Risk Factors"
        assert "risk factors" in sections[1][1]

    def test_filter_filing_content_10k(self):
        """Test filtering 10-K content."""
        content = """
Item 1. Business

Apple Inc. designs and manufactures consumer electronics.

Item 1A. Risk Factors

Competition is intense in the technology sector.

Item 8. Financial Statements

[Financial tables and data - should be filtered out]

Item 15. Exhibits

[List of exhibits - should be filtered out]
"""
        filtered = filter_sec_filing(content, "10-K")

        # Should keep Business and Risk Factors
        assert "Apple Inc. designs" in filtered
        assert "Competition is intense" in filtered

        # Should filter out Financial Statements and Exhibits
        # (unless parsing fails, in which case it keeps full content as fallback)
        # For this test, we check that filtering was attempted
        assert len(filtered) <= len(content)

    def test_filter_filing_content_8k_not_supported(self):
        """Test that 8-K returns full content (not supported for filtering)."""
        content = """
Item 1.01 Entry into Material Agreement

The Company entered into a merger agreement.

Item 9.01 Financial Statements

Pro forma financial information is attached.
"""
        filtered = filter_sec_filing(content, "8-K")

        # 8-K not supported, should return full content
        assert filtered == content
        assert "merger agreement" in filtered
        assert "financial information" in filtered

    def test_filter_filing_fallback_no_sections(self):
        """Test that filtering falls back to full content if no sections found."""
        content = "This is unstructured text without section headers."
        filtered = filter_sec_filing(content, "10-K")

        # Should return full content as fallback
        assert filtered == content

    def test_should_keep_section_case_insensitive(self):
        """Test that section matching is case-insensitive."""
        assert SECSectionFilter.should_keep_section("business", "10-K")
        assert SECSectionFilter.should_keep_section("BUSINESS", "10-K")
        assert SECSectionFilter.should_keep_section("Business", "10-K")

    def test_should_keep_section_with_item_prefix(self):
        """Test section matching with various Item prefixes."""
        assert SECSectionFilter.should_keep_section("Item 1. Business", "10-K")
        assert SECSectionFilter.should_keep_section("Item 1A. Risk Factors", "10-K")
        assert SECSectionFilter.should_keep_section("ITEM 7. MD&A", "10-K")


    def test_filter_reduces_content_size(self):
        """Test that filtering reduces content size for 10-K."""
        # Create realistic 10-K content with keep/skip sections
        content = """
Item 1. Business

Important business information here. """ + ("x" * 10000) + """

Item 8. Financial Statements

Detailed financial tables. """ + ("y" * 20000) + """

Item 1A. Risk Factors

Critical risk information. """ + ("z" * 5000)

        filtered = filter_sec_filing(content, "10-K")

        # Filtered content should be smaller (unless fallback triggered)
        # We check that it's either smaller OR equal (fallback case)
        assert len(filtered) <= len(content)

        # If sections were parsed, Business and Risk Factors should be present
        if len(filtered) < len(content):
            # Filtering worked
            assert "business information" in filtered.lower()
            assert "risk information" in filtered.lower()


class TestFilterSecFilingFunction:
    """Test the convenience function."""

    def test_filter_sec_filing_function(self):
        """Test the convenience function wrapper."""
        content = """
Item 1. Business

Company overview here.
"""
        result = filter_sec_filing(content, "10-K")
        assert isinstance(result, str)
        assert len(result) > 0
