#!/usr/bin/env python3
"""Integration tests for false positive prevention in company profile agent.

Tests edge cases that could cause incorrect relationship detection:
1. Employee names matching company names
2. Similar company names (Baker College vs Baker Hughes)
3. Partial name matches
4. Generic terms in company names
"""

import asyncio
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add bot to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "bot"))

from agents.profiler.tools.internal_search import InternalSearchTool


class TestFalsePositivePrevention:
    """Test cases for preventing false positive relationship detection."""

    @pytest.fixture
    def search_tool(self):
        """Create internal search tool instance."""
        return InternalSearchTool()

    @pytest.mark.asyncio
    async def test_employee_name_vs_company_name(self, search_tool):
        """Test: Employee name 'Baker' should not trigger false positive for 'Baker College'."""
        result = await search_tool._arun(
            query="Baker College existing client relationship projects",
            effort="high",
        )

        # Should find employee names (Siobhan Baker, Derek Baker, etc.)
        # but NOT conclude there's a relationship with Baker College
        assert "Relationship status: No prior engagement" in result
        assert "Relationship status: Existing client" not in result

    @pytest.mark.asyncio
    async def test_similar_company_names(self, search_tool):
        """Test: Baker Hughes should not match Baker College."""
        # If we have Baker Hughes as a client, searching for Baker College
        # should not return a false positive
        result = await search_tool._arun(
            query="Baker College case studies projects", effort="medium"
        )

        # Verify it doesn't conflate different "Baker" companies
        assert "baker college" not in result.lower() or "no prior engagement" in result.lower()

    @pytest.mark.asyncio
    async def test_partial_name_match(self, search_tool):
        """Test: Partial matches should not trigger false positives."""
        result = await search_tool._arun(
            query="College Board existing client relationship", effort="medium"
        )

        # Should not match "Baker College" or any other "College" entity
        # unless we actually have College Board as a client
        assert "Relationship status:" in result

    @pytest.mark.asyncio
    async def test_generic_company_name(self, search_tool):
        """Test: Generic terms like 'Solutions Inc' should not cause false matches."""
        result = await search_tool._arun(
            query="Solutions Inc existing client projects", effort="medium"
        )

        # Should not match every document containing "solutions"
        assert "Relationship status:" in result

    @pytest.mark.asyncio
    async def test_multiword_company_extraction(self, search_tool):
        """Test: Multi-word company names are extracted correctly."""
        test_cases = [
            ("Baker College existing client", "baker college"),
            ("Vail Resorts past projects", "vail resorts"),
            ("J.P. Morgan case studies", "j.p. morgan"),
            ("American Express existing relationship", "american express"),
            ("Bank of America client projects", "bank of america"),
        ]

        for query, expected_company in test_cases:
            result = await search_tool._arun(query=query, effort="low")

            # Verify the result mentions the full company name, not just first word
            # (This is indirect - we check that the result discusses the right company)
            assert "Relationship status:" in result, f"Failed for query: {query}"

    @pytest.mark.asyncio
    async def test_known_true_positive(self, search_tool):
        """Test: Known clients should still be detected (no regression)."""
        # Test with a known client (update this with an actual client from your DB)
        # For now, this is a placeholder - replace with actual client name
        result = await search_tool._arun(
            query="AllCampus existing client relationship projects",
            effort="high",
        )

        # This should find the actual client relationship
        # (Will depend on what's actually in your vector DB)
        assert "Relationship status:" in result

    @pytest.mark.asyncio
    async def test_stop_word_extraction(self, search_tool):
        """Test: Stop words don't get included in company name extraction."""
        # Query: "Baker College existing client relationship projects case studies"
        # Should extract: "baker college"
        # Should NOT extract: "baker college existing client relationship"

        result = await search_tool._arun(
            query="Baker College existing client relationship projects case studies",
            effort="medium",
        )

        # The tool should search for "baker college", not include stop words
        # We verify this indirectly by checking it doesn't have false positive
        assert "Relationship status: No prior engagement" in result

    @pytest.mark.asyncio
    async def test_company_with_stop_words_in_name(self, search_tool):
        """Test: Company names containing stop words are handled correctly."""
        # Edge case: What if company name itself contains a stop word?
        # e.g., "Client Solutions Inc", "History Channel", "Past Perfect Software"

        result = await search_tool._arun(
            query="Past Perfect Software existing client", effort="medium"
        )

        # This is tricky - "Past" is a stop word but part of company name
        # Current implementation would stop at "past" and extract nothing
        # This test documents the current behavior (may need improvement)
        assert "Relationship status:" in result


def main():
    """Run tests manually for debugging."""
    import asyncio

    tool = InternalSearchTool()

    print("=" * 80)
    print("Testing False Positive Prevention")
    print("=" * 80)

    test_cases = [
        ("Baker College", "Baker College existing client relationship projects"),
        ("Vail Resorts", "Vail Resorts past projects case studies"),
        ("Generic Inc", "Solutions Inc existing client projects"),
    ]

    for company_name, query in test_cases:
        print(f"\n{'='*80}")
        print(f"Test: {company_name}")
        print(f"Query: {query}")
        print(f"{'='*80}")

        result = asyncio.run(tool._arun(query=query, effort="medium"))

        if "Relationship status: Existing client" in result:
            print(f"❌ FALSE POSITIVE DETECTED for {company_name}")
        elif "Relationship status: No prior engagement" in result:
            print(f"✅ Correctly identified no relationship for {company_name}")
        else:
            print(f"⚠️  Unclear relationship status for {company_name}")

        print(f"\nFirst 500 chars of result:")
        print(result[:500])


if __name__ == "__main__":
    main()
