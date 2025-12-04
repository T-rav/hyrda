#!/usr/bin/env python3
"""
Update the Final Report Generation prompt in Langfuse to add relationship verification.

This script adds a new section to the prompt that instructs the LLM to:
1. Only claim relationships when there's DIRECT evidence of past work
2. Verify the company name is the SUBJECT of case studies/projects, not just mentioned
3. Distinguish between "we worked with X" vs "X was mentioned in context of Y"
"""

import os
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from dotenv import load_dotenv
from langfuse import Langfuse

# Load environment variables
load_dotenv()


def get_enhanced_relationship_section() -> str:
    """Get the enhanced relationship section with strict verification rules."""
    return """## Relationships via 8th Light Network

**CRITICAL: STRICT RELATIONSHIP VERIFICATION RULES**

Before claiming ANY relationship with this company, you MUST verify:

1. **Direct Evidence Only**: Only claim a relationship if you find EXPLICIT evidence that 8th Light worked WITH this specific company
   - ✅ VALID: "AllCampus Case Study - We built Partner Hub application for AllCampus"
   - ❌ INVALID: "Vail Resorts mentioned in AllCampus case study" (Vail is not the client)
   - ❌ INVALID: "We have case studies" (doesn't specify this company)

2. **Subject vs. Mention**: The company must be the SUBJECT of the work, not just mentioned
   - ✅ VALID: "Vail Resorts - Project Summary: We modernized their booking platform"
   - ❌ INVALID: "Worked with ski industry clients like Vail Resorts and others" (generic mention)
   - ❌ INVALID: "Similar to work we did with Vail Resorts" (comparison, not direct work)

3. **File/Document Names**: Check if the company name appears in TITLES/FILENAMES with project indicators
   - ✅ VALID: "[Company Name] Case Study.pdf", "[Company Name] Project Retrospective.docx"
   - ❌ INVALID: "Case Study.pdf" (no company name in filename, even if mentioned inside)

4. **CHECK FOR INTERNAL SEARCH RESULTS FIRST**:
   - Look for sections labeled "Internal Knowledge Base Search" in your research notes
   - These sections will have an explicit "Relationship status:" line at the top:
     * "Relationship status: Existing client/past engagement" → Relationship exists
     * "Relationship status: No prior engagement" → NO relationship exists
   - Trust this status line - it's based on deep analysis of internal documents

**HOW TO WRITE THIS SECTION:**

**If "Relationship status: Existing client/past engagement" is found:**
```
## Relationships via 8th Light Network

✅ **8th Light has an existing relationship with [Company]**

Based on internal documentation:
- [Specific project 1]: [Brief description from case study]
- [Specific project 2]: [Brief description from case study]
- [Technologies/deliverables]: [What we built/delivered]

Source: Internal case study "[Document Name]"
```

**If "Relationship status: No prior engagement" is found OR no internal search results exist:**
```
## Relationships via 8th Light Network

❌ **No prior engagement found**

Internal knowledge base search did not identify any past projects, case studies, or direct client work with [Company]. While [Company] may operate in industries where 8th Light has expertise, there is no documented history of collaboration.
```

**NEVER write:**
- ❌ "We may have worked with them"
- ❌ "Potential relationship exists"
- ❌ "Similar to clients we've worked with"
- ❌ Generic statements like "We work with companies in this industry"

**When in doubt, default to "No prior engagement found" rather than claiming a false relationship.**
"""


def update_langfuse_prompt(dry_run: bool = False) -> None:
    """
    Update the Final Report Generation prompt in Langfuse.

    Args:
        dry_run: If True, only show what would be updated without making changes
    """
    # Initialize Langfuse client
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not public_key or not secret_key:
        print("❌ Error: LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set")
        sys.exit(1)

    langfuse = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=host,
    )

    prompt_name = "CompanyProfiler/Final_Report_Generation"

    try:
        # Fetch the current prompt
        print(f"📥 Fetching current prompt: {prompt_name}")
        current_prompt = langfuse.get_prompt(prompt_name)

        if not current_prompt:
            print(f"❌ Error: Prompt '{prompt_name}' not found in Langfuse")
            sys.exit(1)

        current_content = current_prompt.prompt
        print(f"✅ Current prompt fetched (version {current_prompt.version})")
        print(f"   Length: {len(current_content)} characters")

        # Check if the relationship section already has the new rules
        if "CRITICAL: STRICT RELATIONSHIP VERIFICATION RULES" in current_content:
            print("\n✅ Prompt already contains strict relationship verification rules")
            print("   No update needed.")
            return

        # Find the existing relationship section
        relationship_marker = "## Relationships via 8th Light Network"

        if relationship_marker not in current_content:
            print("\n❌ Error: Could not find relationship section marker in prompt")
            print(f"   Expected to find: '{relationship_marker}'")
            sys.exit(1)

        # Find the end of the relationship section (next ## heading or end of prompt)
        import re

        relationship_start = current_content.index(relationship_marker)
        # Find the next section (starts with ##)
        next_section_match = re.search(
            r"\n## [^R]",
            current_content[relationship_start + len(relationship_marker) :],
        )

        if next_section_match:
            relationship_end = (
                relationship_start
                + len(relationship_marker)
                + next_section_match.start()
            )
            old_relationship_section = current_content[
                relationship_start:relationship_end
            ]
        else:
            # Relationship section is at the end
            old_relationship_section = current_content[relationship_start:]
            relationship_end = len(current_content)

        # Get the enhanced section
        new_relationship_section = get_enhanced_relationship_section()

        # Replace the old section with the new one
        updated_content = (
            current_content[:relationship_start]
            + new_relationship_section
            + current_content[relationship_end:]
        )

        print("\n📝 Changes to be made:")
        print(
            f"   - Old relationship section: {len(old_relationship_section)} characters"
        )
        print(
            f"   - New relationship section: {len(new_relationship_section)} characters"
        )
        print(
            f"   - Total prompt length: {len(current_content)} → {len(updated_content)} characters"
        )

        if dry_run:
            print("\n🔍 DRY RUN MODE - Showing new relationship section:")
            print("=" * 80)
            print(new_relationship_section)
            print("=" * 80)
            print("\n✅ Dry run complete. Run without --dry-run to apply changes.")
            return

        # Create a new version of the prompt using create_prompt
        # This creates a new version while preserving the prompt name
        print("\n📤 Uploading new prompt version...")

        langfuse.create_prompt(
            name=prompt_name,
            prompt=updated_content,
            labels=["relationship-verification-fix"],
        )

        print(
            "✅ Successfully created new prompt version with relationship verification rules"
        )
        print(f"   Prompt: {prompt_name}")
        print("   New version will be created in Langfuse")
        print("\n⚠️  IMPORTANT:")
        print(f"   1. Go to Langfuse UI → Prompts → {prompt_name}")
        print("   2. Find the newest version (just created)")
        print("   3. Click 'Promote to production' or 'Set as active' to make it live")
        print(
            "   4. The bot will automatically pick up the new version on next profile generation"
        )

    except Exception as e:
        print(f"\n❌ Error updating prompt: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Update Final Report Generation prompt with relationship verification rules"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    args = parser.parse_args()

    print("🚀 Final Report Prompt Updater")
    print("=" * 80)

    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")

    update_langfuse_prompt(dry_run=args.dry_run)
