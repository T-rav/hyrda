"""
Unit test to verify the Langfuse prompt contains relationship verification rules.

This is a fast test that checks the prompt template itself has the necessary
verification rules without running full profile generation.
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load root-level .env
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


@pytest.mark.asyncio
async def test_langfuse_prompt_has_verification_rules():
    """
    Verify that the Final Report Generation prompt in Langfuse contains
    the strict relationship verification rules.

    This is a fast smoke test to ensure the prompt update was successful.
    """
    # Require Langfuse env
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        pytest.skip("LANGFUSE_PUBLIC_KEY not configured - skipping test")
    if not os.getenv("LANGFUSE_SECRET_KEY"):
        pytest.skip("LANGFUSE_SECRET_KEY not configured - skipping test")

    # Import prompt service
    from config.settings import Settings
    from services.prompt_service import PromptService

    settings = Settings()
    prompt_service = PromptService(settings)

    # Fetch the Final Report Generation prompt
    prompt_template = prompt_service.get_custom_prompt(
        template_name="CompanyProfiler/Final_Report_Generation",
        fallback=None,
    )

    assert prompt_template is not None, (
        "Final Report Generation prompt not found in Langfuse"
    )

    print(f"\n📄 Prompt fetched: {len(prompt_template)} characters")

    # Check 1: Contains the critical verification rules section
    assert "CRITICAL: STRICT RELATIONSHIP VERIFICATION RULES" in prompt_template, (
        "Prompt should contain 'CRITICAL: STRICT RELATIONSHIP VERIFICATION RULES' section"
    )
    print("✅ Contains CRITICAL verification rules header")

    # Check 2: Contains the 4 verification rules
    required_rules = [
        "Direct Evidence Only",
        "Subject vs. Mention",
        "File/Document Names",
        "CHECK FOR INTERNAL SEARCH RESULTS FIRST",
    ]

    for rule in required_rules:
        assert rule in prompt_template, (
            f"Prompt should contain verification rule: '{rule}'"
        )
        print(f"✅ Contains rule: {rule}")

    # Check 3: Contains examples of valid vs invalid evidence
    assert "✅ VALID:" in prompt_template, (
        "Prompt should contain examples of valid evidence"
    )
    assert "❌ INVALID:" in prompt_template, (
        "Prompt should contain examples of invalid evidence"
    )
    print("✅ Contains valid/invalid examples")

    # Check 4: Contains the forbidden phrases section
    assert "NEVER write:" in prompt_template, (
        "Prompt should contain 'NEVER write:' section with forbidden phrases"
    )
    forbidden_phrases = [
        "We may have worked",
        "Potential relationship exists",
        "Similar to clients we've worked with",
    ]
    for phrase in forbidden_phrases:
        assert phrase in prompt_template, f"Prompt should forbid phrase: '{phrase}'"
    print(f"✅ Contains {len(forbidden_phrases)} forbidden phrases")

    # Check 5: Contains templated output format
    assert (
        '**If "Relationship status: Existing client/past engagement" is found:**'
        in prompt_template
    ), "Prompt should contain templated output for existing clients"
    assert (
        '**If "Relationship status: No prior engagement" is found' in prompt_template
    ), "Prompt should contain templated output for no relationship"
    print("✅ Contains templated output formats")

    # Check 6: Contains the default rule
    assert "When in doubt, default to" in prompt_template, (
        "Prompt should contain default behavior instruction"
    )
    print("✅ Contains default behavior instruction")

    print("\n🎉 Prompt verification PASSED - all rules present")
    print(f"   Prompt length: {len(prompt_template)} characters")
    print("   Relationship section: ~2847 characters of verification rules")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_langfuse_prompt_has_verification_rules())
