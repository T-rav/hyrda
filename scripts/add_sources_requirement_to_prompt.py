#!/usr/bin/env python3
"""
Update the Final Report Generation prompt in Langfuse to require Sources section.

This prevents the first-time quality control failure by explicitly instructing
the LLM to include a properly formatted Sources section with all citations.
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


def get_sources_section_requirement() -> str:
    """Get the sources section requirement text to add to prompt."""
    return """
## CRITICAL: Sources Section (Required)

**YOUR REPORT MUST END WITH A PROPERLY FORMATTED SOURCES SECTION**

At the end of your report, add a `## Sources` section that lists ALL sources used in your research:

```markdown
## Sources

1. [Title/Description] - URL or internal document reference
2. [Title/Description] - URL or internal document reference
3. [Title/Description] - URL or internal document reference
... (continue for all sources)
```

**Requirements:**
- Include at least 10 source entries
- Use numbered list format (1., 2., 3., etc.)
- Each source should correspond to citations [1], [2], [3] used throughout the report
- Include both external URLs and internal document references
- Format: `[Number]. [Source Title/Description] - [URL or "Internal: Document Name"]`

**Example:**
```markdown
## Sources

1. Company Website - Homepage - https://company.com
2. LinkedIn Company Profile - https://linkedin.com/company/example
3. Internal: AllCampus Case Study.pdf
4. TechCrunch Article - Company raises $50M - https://techcrunch.com/...
5. Company Blog Post - Engineering Culture - https://company.com/blog/...
```

**IMPORTANT:** If you omit the Sources section, quality control will FAIL and you'll be asked to revise the entire report. Save time by including it from the start.
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

        # Check if the sources requirement already exists
        if "## CRITICAL: Sources Section (Required)" in current_content:
            print("\n✅ Prompt already contains Sources section requirement")
            print("   No update needed.")
            return

        # Get the sources requirement text
        sources_requirement = get_sources_section_requirement()

        # Add it at the end of the prompt (before any final reminders)
        # Look for common ending markers
        import re

        # Try to find a good insertion point (before final reminders/notes)
        insertion_markers = [
            "## Final Reminders",
            "## Important Notes",
            "Remember:",
            "IMPORTANT:",
        ]

        insertion_point = None
        for marker in insertion_markers:
            if marker in current_content:
                insertion_point = current_content.index(marker)
                break

        # If no marker found, append at the end
        if insertion_point is None:
            insertion_point = len(current_content)
            updated_content = current_content + "\n\n" + sources_requirement
        else:
            updated_content = (
                current_content[:insertion_point]
                + sources_requirement
                + "\n\n"
                + current_content[insertion_point:]
            )

        print("\n📝 Changes to be made:")
        print(f"   - Sources requirement length: {len(sources_requirement)} characters")
        print(
            f"   - Total prompt length: {len(current_content)} → {len(updated_content)} characters"
        )
        print(
            f"   - Insertion point: {insertion_point} ({'end of prompt' if insertion_point == len(current_content) else 'before final section'})"
        )

        if dry_run:
            print("\n🔍 DRY RUN MODE - Showing sources requirement to be added:")
            print("=" * 80)
            print(sources_requirement)
            print("=" * 80)
            print("\n✅ Dry run complete. Run without --dry-run to apply changes.")
            return

        # Create a new version of the prompt
        print("\n📤 Uploading new prompt version...")

        langfuse.create_prompt(
            name=prompt_name,
            prompt=updated_content,
            labels=["sources-requirement-fix", "quality-control"],
        )

        print(
            "✅ Successfully created new prompt version with Sources section requirement"
        )
        print(f"   Prompt: {prompt_name}")
        print("   New version created in Langfuse")
        print("\n⚠️  IMPORTANT:")
        print(f"   1. Go to Langfuse UI → Prompts → {prompt_name}")
        print("   2. Find the newest version (just created)")
        print("   3. Click 'Promote to production' or 'Set as active' to make it live")
        print(
            "   4. The bot will automatically pick up the new version on next profile generation"
        )
        print(
            "\n✅ This should prevent quality control from failing on first attempt due to missing Sources section"
        )

    except Exception as e:
        print(f"\n❌ Error updating prompt: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Add Sources section requirement to Final Report Generation prompt"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    args = parser.parse_args()

    print("🚀 Sources Requirement Prompt Updater")
    print("=" * 80)

    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")

    update_langfuse_prompt(dry_run=args.dry_run)
