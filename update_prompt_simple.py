import os
import sys
from langfuse import Langfuse

print("🚀 Starting Langfuse prompt update...")

# Get env vars
public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
secret_key = os.getenv("LANGFUSE_SECRET_KEY")
host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

if not public_key or not secret_key:
    print("❌ Error: Missing Langfuse credentials")
    sys.exit(1)

langfuse = Langfuse(public_key=public_key, secret_key=secret_key, host=host)

prompt_name = "CompanyProfiler/Final_Report_Generation"
print(f"📥 Fetching prompt: {prompt_name}")

current_prompt = langfuse.get_prompt(prompt_name)
print(f"✅ Fetched version {current_prompt.version}, length: {len(current_prompt.prompt)}")

# Check if already has Sources requirement
if "## CRITICAL: Sources Section (Required)" in current_prompt.prompt:
    print("✅ Prompt already has Sources requirement - no update needed")
    sys.exit(0)

print("📤 Creating new version with Sources requirement...")

sources_text = """

## CRITICAL: Sources Section (Required)

**YOUR REPORT MUST END WITH A PROPERLY FORMATTED SOURCES SECTION**

At the end of your report, add a `## Sources` section that lists ALL sources used in your research.

**Requirements:**
- Include at least 10 source entries
- Use numbered list format (1., 2., 3., etc.)
- Each source should correspond to citations [1], [2], [3] used throughout the report
- Include both external URLs and internal document references

**IMPORTANT:** If you omit the Sources section, quality control will FAIL and you'll be asked to revise the entire report.
"""

updated_content = current_prompt.prompt + sources_text

langfuse.create_prompt(
    name=prompt_name,
    prompt=updated_content,
    labels=["sources-requirement", "quality-control-fix"],
)

print("✅ New prompt version created successfully!")
print(f"   Old length: {len(current_prompt.prompt)} → New: {len(updated_content)}")
print("\n⚠️  NEXT STEP: Go to Langfuse UI and promote the new version to production")
