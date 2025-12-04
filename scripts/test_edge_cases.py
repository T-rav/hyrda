#!/usr/bin/env python3
"""Test edge cases for company name extraction."""

import asyncio
from dotenv import load_dotenv

load_dotenv()

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))



async def test_extraction_logic():
    """Test the company name extraction logic directly."""

    # Simulate the extraction logic
    def extract_company_name(query: str) -> str:
        """Replicate the extraction logic from internal_search.py."""
        company_name = None
        q_lower = query.lower()

        if q_lower.startswith("profile "):
            after = q_lower[len("profile ") :]
            if " and " in after:
                company_name = after.split(" and ", 1)[0].strip()
            else:
                company_name = after.strip()

        if not company_name:
            stop_words = {
                "existing",
                "client",
                "relationship",
                "projects",
                "case",
                "studies",
                "study",
                "engagement",
                "work",
                "history",
                "past",
                "previous",
                "information",
                "about",
                "details",
                "background",
                "overview",
                "profile",
                "company",
                "research",
            }
            tokens = q_lower.split()
            company_tokens = []
            for token in tokens:
                clean_token = token.strip("\"'(),.:;")
                if clean_token in stop_words:
                    break
                company_tokens.append(clean_token)

            company_name = " ".join(company_tokens) if company_tokens else None

        return company_name.strip().strip("\"' ") if company_name else ""

    test_cases = [
        # Normal cases
        ("Baker College existing client relationship", "baker college"),
        ("Vail Resorts past projects", "vail resorts"),
        ("American Express case studies", "american express"),
        # Edge case: Company name with stop word
        ("Past Perfect Software existing client", ""),  # BUG: stops at "past"
        ("History Channel projects", ""),  # BUG: stops at "history"
        ("Client Solutions Inc case studies", ""),  # BUG: stops at "client"
        # Edge case: Single word company
        ("Apple projects", "apple"),
        ("Microsoft case studies", "microsoft"),
        # Edge case: Profile format
        ("profile Baker College", "baker college"),
        ("profile American Express and financial services", "american express"),
        # Edge case: All stop words
        ("existing client relationship projects", ""),
        # Edge case: Punctuation
        ("J.P. Morgan case studies", "j.p. morgan"),
        ("Baker College (Baker.edu) projects", "baker college"),
    ]

    print("=" * 80)
    print("Company Name Extraction Edge Cases")
    print("=" * 80)

    bugs_found = []

    for query, expected in test_cases:
        extracted = extract_company_name(query)
        status = "✅" if extracted == expected else "❌"

        if extracted != expected:
            bugs_found.append((query, expected, extracted))

        print(f"\n{status} Query: {query}")
        print(f"   Expected: '{expected}'")
        print(f"   Extracted: '{extracted}'")

    if bugs_found:
        print("\n" + "=" * 80)
        print(f"⚠️  FOUND {len(bugs_found)} EDGE CASES THAT MAY NEED FIXING:")
        print("=" * 80)
        for query, expected, extracted in bugs_found:
            print(f"\nQuery: {query}")
            print(f"  Expected: '{expected}' but got '{extracted}'")
            if not extracted and expected:
                print("  Issue: Company name contains stop word - gets truncated")
            elif extracted != expected:
                print("  Issue: Extraction logic doesn't handle this format")

    return bugs_found


if __name__ == "__main__":
    bugs = asyncio.run(test_extraction_logic())
    if bugs:
        print(f"\n⚠️  Found {len(bugs)} potential edge cases")
        sys.exit(1)
    else:
        print("\n✅ All test cases passed!")
        sys.exit(0)
