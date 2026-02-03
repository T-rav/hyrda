#!/usr/bin/env python3
"""
Fix the Final Report Generation prompt to properly trust internal search results.

The issue: The enhanced prompt is being TOO strict and overriding the internal
search tool's relationship detection. When internal_search_tool returns
"Relationship status: Existing client", the final report MUST trust that.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "bot"))

from dotenv import load_dotenv
from langfuse import Langfuse

load_dotenv()


def get_fixed_relationship_section() -> str:
    return """## Relationships via 8th Light Network

**CRITICAL: TRUST THE INTERNAL SEARCH RESULTS**

The internal search tool has ALREADY analyzed the knowledge base and determined the relationship status. You MUST follow its guidance:

1. **Check for "Relationship status:" line in research notes**:
   - If you see "Relationship status: Existing client/past engagement" → Write EXISTING relationship section
   - If you see "Relationship status: No prior engagement" → Write NO relationship section

2. **When writing EXISTING relationship section**:
   ```
   ## Relationships via 8th Light Network

   ✅ **8th Light has an existing relationship with [Company]**

   Based on internal documentation:
   - [Project name/details from research notes]
   - [Specific deliverables/technologies from research notes]
   - [Team members/timeline if available]

   Source: Internal case study/project records
   ```

3. **When writing NO relationship section**:
   ```
   ## Relationships via 8th Light Network

   ❌ **No prior engagement found**

   Internal knowledge base search did not identify any past projects, case studies, or direct client work with [Company]. While [Company] may operate in industries where 8th Light has expertise, there is no documented history of collaboration.
   ```

**NEVER**:
- ❌ Second-guess the internal search relationship status
- ❌ Use speculative language like "may have worked with"
- ❌ Claim relationships without "Relationship status: Existing client" in notes
- ❌ Deny relationships when "Relationship status: Existing client" is present

**The internal search tool is authoritative - trust its relationship status determination.**
"""


def fix_langfuse_prompt() -> None:
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
        print(f"📥 Fetching current prompt: {prompt_name}")
        current_prompt = langfuse.get_prompt(prompt_name)

        if not current_prompt:
            print(f"❌ Error: Prompt '{prompt_name}' not found in Langfuse")
            sys.exit(1)

        current_content = current_prompt.prompt
        print(f"✅ Current prompt fetched (version {current_prompt.version})")

        # Find and replace the relationship section
        import re
        relationship_marker = "## Relationships via 8th Light Network"

        if relationship_marker not in current_content:
            print(f"❌ Error: Could not find relationship section in prompt")
            sys.exit(1)

        # Find the next section
        relationship_start = current_content.index(relationship_marker)
        next_section_match = re.search(r'\n## [^R]', current_content[relationship_start + len(relationship_marker):])

        if next_section_match:
            relationship_end = relationship_start + len(relationship_marker) + next_section_match.start()
        else:
            relationship_end = len(current_content)

        # Get the fixed section
        new_relationship_section = get_fixed_relationship_section()

        # Replace
        updated_content = (
            current_content[:relationship_start] +
            new_relationship_section +
            current_content[relationship_end:]
        )

        print(f"\n📝 Creating new prompt version...")
        langfuse.create_prompt(
            name=prompt_name,
            prompt=updated_content,
            labels=["relationship-trust-fix"],
        )

        print(f"✅ Successfully created new prompt version")
        print(f"\n⚠️  IMPORTANT: Go to Langfuse UI and promote this version to production")
        print(f"   The new version trusts internal search relationship status")

    except Exception as e:
        print(f"\n❌ Error fixing prompt: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("🔧 Fixing Final Report Prompt to Trust Internal Search")
    print("=" * 80)
    fix_langfuse_prompt()
