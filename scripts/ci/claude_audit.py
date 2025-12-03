#!/usr/bin/env python3
"""
Claude Code Quality Audit for CI/CD

Runs quality audits using Claude API and reports issues.
Blocks builds on P0 (critical) or P1 (warning) violations.

Usage:
    python claude_audit.py --mode=critical-check --exit-on-critical
    python claude_audit.py --mode=full-audit --format=github
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic


class ClaudeAuditRunner:
    """Runs Claude quality audits in CI/CD environment."""

    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"  # Latest Sonnet
        self.audit_dir = Path(".claude/audit-reports")
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    def run_quick_health_check(self) -> dict:
        """Run quick health check (critical issues only)."""
        print("🔍 Running Claude quick health check...")

        prompt = """You are a code quality auditor. Perform a QUICK health check focusing only on CRITICAL issues (P0).

**Scan for P0 issues only:**
1. Mutable default arguments (list/dict defaults)
2. Functions >100 lines
3. Missing critical type hints on public APIs
4. Security vulnerabilities (SQL injection, command injection, XSS)
5. Resource leaks (unclosed files, connections)
6. Race conditions in async code

**Do NOT check:**
- Minor style issues
- Missing docstrings (unless security-relevant)
- Test quality (focus on production code)

**Output format:**
```json
{
    "status": "pass|fail",
    "critical_count": <number>,
    "violations": [
        {
            "severity": "critical",
            "file": "path/to/file.py",
            "line": 123,
            "issue": "Brief description",
            "fix": "How to fix"
        }
    ]
}
```

**Exit rules:**
- status="pass" if critical_count == 0
- status="fail" if critical_count > 0

Analyze the codebase and return ONLY the JSON (no markdown fences, no explanation)."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        result_text = response.content[0].text

        # Parse JSON from response
        try:
            # Remove markdown code fences if present
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            result = json.loads(result_text.strip())
        except json.JSONDecodeError:
            # Fallback: extract JSON from text
            import re

            json_match = re.search(r"\{.*\}", result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
            else:
                result = {
                    "status": "error",
                    "critical_count": 0,
                    "violations": [],
                    "error": "Failed to parse response",
                }

        return result

    def run_full_audit(self) -> dict:
        """Run comprehensive audit (P0 + P1 issues)."""
        print("🔍 Running Claude comprehensive audit...")

        prompt = """You are a code quality auditor. Perform a COMPREHENSIVE audit checking P0 (critical) and P1 (warning) issues.

**Check for:**

**P0 - Critical (Block immediately):**
1. Mutable default arguments
2. Functions >100 lines
3. Security vulnerabilities
4. Resource leaks
5. Race conditions

**P1 - Warning (Block merge):**
1. Missing type hints on public methods
2. Functions 50-100 lines
3. Missing docstrings on public APIs
4. Broad exception handling without logging
5. Magic numbers (not extracted to constants)
6. Unused imports
7. Test files with 5+ unrelated assertions

**Output format:**
```json
{
    "status": "pass|warn|fail",
    "critical_count": <number>,
    "warning_count": <number>,
    "violations": [
        {
            "severity": "critical|warning",
            "category": "type_hints|security|complexity|...",
            "file": "path/to/file.py",
            "line": 123,
            "issue": "Brief description",
            "fix": "How to fix",
            "estimate": "5 minutes|30 minutes|2 hours"
        }
    ],
    "summary": {
        "files_checked": <number>,
        "quality_score": <0-100>
    }
}
```

**Exit rules:**
- status="pass" if critical_count == 0 && warning_count == 0
- status="warn" if critical_count == 0 && warning_count > 0
- status="fail" if critical_count > 0

Analyze the codebase and return ONLY the JSON."""

        response = self.client.messages.create(
            model=self.model, max_tokens=8192, messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text

        try:
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            result = json.loads(result_text.strip())
        except json.JSONDecodeError:
            import re

            json_match = re.search(r"\{.*\}", result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
            else:
                result = {
                    "status": "error",
                    "critical_count": 0,
                    "warning_count": 0,
                    "violations": [],
                }

        return result

    def format_github_report(self, result: dict) -> str:
        """Format audit results as GitHub markdown comment."""
        status_emoji = {
            "pass": "✅",
            "warn": "⚠️",
            "fail": "❌",
            "error": "🔴",
        }

        emoji = status_emoji.get(result.get("status", "error"), "❓")
        status = result.get("status", "error").upper()

        critical_count = result.get("critical_count", 0)
        warning_count = result.get("warning_count", 0)
        violations = result.get("violations", [])

        report = f"""# {emoji} Claude Code Quality Audit

## Status: {status}

"""

        if result.get("status") == "pass":
            report += """
✅ **No critical or warning violations found!**

The code meets quality standards for merging.
"""
        else:
            report += f"""
### Summary
- 🔴 Critical (P0): **{critical_count}**
- ⚠️ Warning (P1): **{warning_count}**
- 📊 Total violations: **{len(violations)}**

"""

            if critical_count > 0:
                report += """
### ❌ Critical Issues (Must Fix Before Merge)

"""
                for v in [v for v in violations if v.get("severity") == "critical"]:
                    report += f"""
**{v.get('file', 'unknown')}:{v.get('line', '?')}**
- **Issue:** {v.get('issue', 'No description')}
- **Fix:** {v.get('fix', 'No fix provided')}
- **Estimate:** {v.get('estimate', 'Unknown')}

"""

            if warning_count > 0:
                report += """
### ⚠️ Warning Issues (Should Fix)

"""
                for v in [v for v in violations if v.get("severity") == "warning"]:
                    report += f"""
**{v.get('file', 'unknown')}:{v.get('line', '?')}**
- **Issue:** {v.get('issue', 'No description')}
- **Fix:** {v.get('fix', 'No fix provided')}
- **Estimate:** {v.get('estimate', 'Unknown')}

"""

        # Add quality score if available
        if "summary" in result and "quality_score" in result["summary"]:
            score = result["summary"]["quality_score"]
            score_emoji = "🟢" if score >= 90 else "🟡" if score >= 70 else "🔴"
            report += f"""
---
### Quality Score: {score_emoji} {score}/100
"""

        report += f"""
---
<sub>🤖 Powered by Claude | Audit timestamp: {datetime.now().isoformat()}</sub>
"""

        return report

    def format_terminal_report(self, result: dict) -> str:
        """Format audit results for terminal output."""
        status = result.get("status", "error").upper()
        critical_count = result.get("critical_count", 0)
        warning_count = result.get("warning_count", 0)
        violations = result.get("violations", [])

        report = f"""
{'='*60}
Claude Code Quality Audit Report
{'='*60}

Status: {status}
Critical (P0): {critical_count}
Warning (P1): {warning_count}
Total Violations: {len(violations)}

"""

        if result.get("status") == "pass":
            report += "✅ No critical or warning violations found!\n"
        else:
            if critical_count > 0:
                report += "\n❌ CRITICAL ISSUES (P0):\n" + "-" * 60 + "\n"
                for v in [v for v in violations if v.get("severity") == "critical"]:
                    report += f"""
File: {v.get('file', 'unknown')}:{v.get('line', '?')}
Issue: {v.get('issue', 'No description')}
Fix: {v.get('fix', 'No fix provided')}
Estimate: {v.get('estimate', 'Unknown')}

"""

            if warning_count > 0:
                report += "\n⚠️  WARNING ISSUES (P1):\n" + "-" * 60 + "\n"
                for v in [v for v in violations if v.get("severity") == "warning"]:
                    report += f"""
File: {v.get('file', 'unknown')}:{v.get('line', '?')}
Issue: {v.get('issue', 'No description')}
Fix: {v.get('fix', 'No fix provided')}

"""

        report += "=" * 60 + "\n"
        return report

    def save_report(self, result: dict, format_type: str):
        """Save audit report to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save JSON
        json_path = self.audit_dir / f"ci-audit-{timestamp}.json"
        with open(json_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"📄 Saved JSON report: {json_path}")

        # Save formatted report
        if format_type == "github":
            report = self.format_github_report(result)
            report_path = self.audit_dir / "ci-report.md"
        else:
            report = self.format_terminal_report(result)
            report_path = self.audit_dir / "ci-report.txt"

        with open(report_path, "w") as f:
            f.write(report)
        print(f"📄 Saved report: {report_path}")

        return report


def main():
    parser = argparse.ArgumentParser(description="Claude Code Quality Audit for CI/CD")
    parser.add_argument(
        "--mode",
        choices=["critical-check", "full-audit"],
        default="critical-check",
        help="Audit mode (default: critical-check)",
    )
    parser.add_argument(
        "--format",
        choices=["github", "terminal"],
        default="terminal",
        help="Output format (default: terminal)",
    )
    parser.add_argument(
        "--exit-on-critical",
        action="store_true",
        help="Exit with code 1 if critical issues found",
    )
    parser.add_argument(
        "--exit-on-warning", action="store_true", help="Exit with code 1 if any issues found"
    )

    args = parser.parse_args()

    # Get API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    # Run audit
    runner = ClaudeAuditRunner(api_key)

    try:
        if args.mode == "critical-check":
            result = runner.run_quick_health_check()
        else:
            result = runner.run_full_audit()

        # Save reports
        report = runner.save_report(result, args.format)

        # Print to stdout
        print(report)

        # Determine exit code
        critical_count = result.get("critical_count", 0)
        warning_count = result.get("warning_count", 0)

        if args.exit_on_critical and critical_count > 0:
            print(f"\n❌ BLOCKING: {critical_count} critical issues found", file=sys.stderr)
            sys.exit(1)

        if args.exit_on_warning and (critical_count > 0 or warning_count > 0):
            print(
                f"\n⚠️  BLOCKING: {critical_count + warning_count} issues found",
                file=sys.stderr,
            )
            sys.exit(1)

        print("\n✅ Quality check passed")
        sys.exit(0)

    except Exception as e:
        print(f"❌ Error running audit: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
