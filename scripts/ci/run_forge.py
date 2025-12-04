#!/usr/bin/env python3
"""
Run Forge quality audit in CI via Anthropic API.
Uses the Task tool to invoke the Forge agent.
"""
import os
import sys
from anthropic import Anthropic

def main():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    client = Anthropic(api_key=api_key)

    # Invoke Forge agent via Task tool
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8192,
        messages=[{
            "role": "user",
            "content": """Use the Task tool to run the Forge quality agent in report-only mode.

Task parameters:
- subagent_type: "forge"
- description: "CI quality gate check"
- prompt: "Run comprehensive quality audit in report-only mode. Count Critical and Warning violations. Generate report to .claude/audit-reports/ci-report.md. Return violation counts."

After the Forge agent completes, check the violations:
- If Critical violations == 0 AND Warning violations == 0: Print "PASS" and I'll exit 0
- If any violations found: Print "FAIL: X critical, Y warnings" and I'll exit 1

Run the agent now."""
        }]
    )

    output = response.content[0].text
    print(output)

    # Check for PASS/FAIL in response
    if "PASS" in output and "0 critical" in output.lower() and "0 warning" in output.lower():
        print("\n✅ Quality gate passed: No violations found")
        sys.exit(0)
    else:
        print("\n❌ Quality gate failed: Violations found")
        sys.exit(1)

if __name__ == "__main__":
    main()
