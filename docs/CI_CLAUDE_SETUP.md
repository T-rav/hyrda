# Claude Code Audit CI/CD Integration

Automated code quality auditing using Claude API in your CI/CD pipeline.

## What It Does

**Automatic Quality Gate:**
- ✅ Runs on every pull request
- ✅ Scans for P0 (critical) and P1 (warning) violations
- ✅ Blocks merge if issues found
- ✅ Posts results as PR comment
- ✅ Generates detailed audit reports

**Checks:**
- 🔴 P0 (Critical): Mutable defaults, security vulnerabilities, functions >100 lines
- ⚠️ P1 (Warning): Missing type hints, no docstrings, magic numbers, unused imports

## Setup Instructions

### Step 1: Get Anthropic API Key

1. Go to https://console.anthropic.com/
2. Create an account or sign in
3. Navigate to "API Keys"
4. Create a new API key
5. Copy the key (starts with `sk-ant-api...`)

### Step 2: Add API Key to GitHub Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `ANTHROPIC_API_KEY`
5. Value: Paste your API key
6. Click **Add secret**

### Step 3: Enable Workflow

The workflow is already configured in `.github/workflows/quality-gate.yml`.

It will automatically run on:
- ✅ Pull requests (open, update, reopen)
- ✅ Pushes to `main` or `develop` branches

### Step 4: Test It

Create a test PR with a known violation:

```python
# File: test_violation.py

# P0 Violation: Mutable default argument
def bad_function(items=[]):  # ❌ Critical!
    items.append(1)
    return items

# P1 Violation: Missing type hints
def another_function(x, y):  # ⚠️ Warning
    return x + y
```

The CI will:
1. Detect violations
2. Block the PR
3. Post a comment with details
4. Generate audit report artifact

## Workflow Modes

### Mode 1: Quick Health Check (Default)
```yaml
--mode=critical-check --exit-on-critical
```

**Speed:** ~30 seconds
**Checks:** P0 (critical) only
**Blocks on:** Critical issues

**Use for:**
- Pull request checks
- Pre-merge gates
- Fast feedback

### Mode 2: Full Audit
```yaml
--mode=full-audit --exit-on-warning
```

**Speed:** ~2 minutes
**Checks:** P0 + P1 (critical + warnings)
**Blocks on:** Any issues

**Use for:**
- Release branches
- Main/develop branch pushes
- Comprehensive quality checks

## Example PR Comment

When violations are found, Claude posts a comment:

```markdown
# ❌ Claude Code Quality Audit

## Status: FAIL

### Summary
- 🔴 Critical (P0): **2**
- ⚠️ Warning (P1): **5**
- 📊 Total violations: **7**

### ❌ Critical Issues (Must Fix Before Merge)

**tasks/jobs/base_job.py:25**
- **Issue:** Mutable default argument: `REQUIRED_PARAMS: list = []`
- **Fix:** Use `None` and initialize in `__init__`: `self.required_params = []`
- **Estimate:** 5 minutes

**bot/services/auth.py:142**
- **Issue:** Function too large (150 lines)
- **Fix:** Split into smaller functions: extract validation, processing, response
- **Estimate:** 30 minutes

### ⚠️ Warning Issues (Should Fix)

**bot/services/llm_service.py:45**
- **Issue:** Missing return type hint
- **Fix:** Add `-> str` return type annotation
- **Estimate:** 5 minutes

[... more warnings ...]

---
### Quality Score: 🔴 65/100

---
🤖 Powered by Claude | Audit timestamp: 2025-12-03T20:00:00
```

## Configuration Options

### Custom Thresholds

Edit `.github/workflows/quality-gate.yml`:

```yaml
- name: Run Claude Quality Audit
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    python scripts/ci/claude_audit.py \
      --mode=full-audit \           # critical-check or full-audit
      --format=github \             # github or terminal
      --exit-on-warning             # Block on P1 issues too
```

### Disable for Specific Branches

```yaml
on:
  pull_request:
    branches:
      - main
      - develop
    # Exclude:
    paths-ignore:
      - 'docs/**'
      - '*.md'
```

### Adjust Timeout

```yaml
jobs:
  claude-quality-audit:
    timeout-minutes: 15  # Adjust as needed
```

## Running Locally

Test the audit locally before pushing:

```bash
# Set API key
export ANTHROPIC_API_KEY="sk-ant-api..."

# Run quick check
python scripts/ci/claude_audit.py \
  --mode=critical-check \
  --format=terminal \
  --exit-on-critical

# Run full audit
python scripts/ci/claude_audit.py \
  --mode=full-audit \
  --format=terminal \
  --exit-on-warning
```

## Cost Estimation

### API Usage per Run:

**Quick Health Check:**
- Model: Claude Sonnet 4.5
- Input tokens: ~500
- Output tokens: ~500
- Cost: ~$0.02 per run

**Full Audit:**
- Model: Claude Sonnet 4.5
- Input tokens: ~1,500
- Output tokens: ~2,000
- Cost: ~$0.06 per run

### Monthly Estimates:

**For 100 PRs/month:**
- Quick checks: 100 × $0.02 = **$2.00/month**
- Full audits: 100 × $0.06 = **$6.00/month**

**For 500 PRs/month:**
- Quick checks: 500 × $0.02 = **$10/month**
- Full audits: 500 × $0.06 = **$30/month**

Very affordable for automated quality gates!

## Troubleshooting

### Issue: API Key Not Working

**Error:** `Error: ANTHROPIC_API_KEY environment variable not set`

**Solution:**
1. Verify secret name is exactly `ANTHROPIC_API_KEY`
2. Check API key starts with `sk-ant-api...`
3. Ensure key has not expired
4. Regenerate key if needed

### Issue: Workflow Not Running

**Problem:** PR opened but no quality gate check

**Solution:**
1. Check workflow file exists: `.github/workflows/quality-gate.yml`
2. Verify workflow is enabled in **Actions** tab
3. Check branch filters match your PR base branch
4. Look for workflow run in **Actions** tab for errors

### Issue: False Positives

**Problem:** Claude flags non-issues

**Solution:**
1. Review the violation in detail
2. If truly false positive, add to exclusions
3. Report pattern to improve audit prompts
4. Use `# noqa: <reason>` comment to suppress

### Issue: Slow Audit Times

**Problem:** Audit takes >5 minutes

**Solution:**
1. Use `--mode=critical-check` for faster runs
2. Increase timeout in workflow: `timeout-minutes: 20`
3. Consider caching dependencies
4. Check Anthropic API status page

## Advanced: Custom Audit Rules

Extend `scripts/ci/claude_audit.py` to add custom rules:

```python
def run_custom_audit(self) -> dict:
    """Run custom audit with project-specific rules."""
    prompt = f"""
    Check for custom violations:
    1. All API endpoints must have rate limiting
    2. All database queries must use parameterized queries
    3. All secrets must use environment variables

    Codebase: {self.get_codebase_snapshot()}

    Return JSON with violations.
    """
    # ... implementation
```

## Monitoring & Reports

### View Audit History

All audit reports are saved as artifacts:
1. Go to **Actions** tab
2. Click on a workflow run
3. Download **claude-audit-report** artifact
4. Contains:
   - `ci-audit-TIMESTAMP.json` - Structured data
   - `ci-report.md` - Human-readable report

### Track Quality Trends

Collect audit results over time:
```bash
# Download all audit artifacts
gh run list --workflow=quality-gate.yml | \
  while read -r run; do
    gh run download "$run" --name claude-audit-report
  done

# Analyze trends
python scripts/analyze_quality_trends.py
```

## Best Practices

### 1. Start with Quick Checks
- Begin with `--mode=critical-check` only
- Add `--exit-on-warning` once team adapts
- Gradually increase strictness

### 2. Educate Team
- Share audit reports in team meetings
- Explain why violations matter
- Celebrate quality improvements

### 3. Fix Existing Issues First
- Run audit on main branch
- Create issues for all violations
- Fix before enforcing on PRs

### 4. Document Exceptions
- If violation is acceptable, document why
- Add comments explaining context
- Use suppression sparingly

### 5. Regular Review
- Monthly review of audit patterns
- Adjust rules based on feedback
- Update prompts for accuracy

## Integration with Other Tools

### Combine with Pre-Commit Hooks
```bash
# .git/hooks/pre-commit
python scripts/ci/claude_audit.py --mode=critical-check
```

### Slack Notifications
```yaml
- name: Notify Slack on failure
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    payload: |
      {
        "text": "❌ Quality gate failed on PR #${{ github.event.number }}"
      }
```

### Dashboard Integration
Export metrics to monitoring dashboard:
```python
# scripts/export_metrics.py
import json
from pathlib import Path

reports = Path(".claude/audit-reports").glob("*.json")
metrics = {
    "critical_count": sum(r["critical_count"] for r in reports),
    "warning_count": sum(r["warning_count"] for r in reports),
    # ... more metrics
}
# Push to Datadog, Prometheus, etc.
```

## Support

**Issues with setup?**
- Check GitHub Actions logs for errors
- Verify API key in Secrets
- Test locally first

**Questions about violations?**
- Review audit report details
- Check code-audit.md for standards
- Ask team lead for clarification

**Feature requests?**
- Open issue with enhancement label
- Describe desired behavior
- Suggest implementation if possible

---

## Summary

With Claude integrated into your CI/CD:
- 🔍 **Automatic** quality checks on every PR
- 🚫 **Blocks** merges with critical issues
- 📊 **Reports** detailed violations with fixes
- 💰 **Affordable** (~$2-10/month for 100 PRs)
- ⚡ **Fast** (~30 seconds for quick check)

**Quality gate that actually works!**
