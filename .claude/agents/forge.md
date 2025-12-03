# Forge Agent - Quality Audit Orchestrator

Meta-agent that orchestrates comprehensive quality audits by coordinating **Test Audit** and **Code Audit** agents to provide a complete codebase health assessment.

## Agent Purpose

Forge brings together multiple audit capabilities to provide:
1. **Unified Quality Report** - Combined test + code quality metrics
2. **Prioritized Action Plan** - Violations ranked by impact across all code
3. **Trend Tracking** - Monitor improvements over time
4. **Comprehensive Coverage** - Nothing falls through the cracks

## What Forge Does

### 1. Orchestrates Multiple Audits

**Available Audits:**
- **Test Audit** - Test file naming, 3As structure, factories, builders, anti-patterns
- **Code Audit** - Naming, SRP, types, docstrings, complexity, error handling

**Execution Modes:**
- **Parallel** - Run both audits simultaneously (faster)
- **Sequential** - Run one after another (more stable)
- **Selective** - Run specific audits only

### 2. Combines Results

**Unified Report Structure:**
```markdown
# Forge Quality Audit Report

## Executive Summary
- Overall Quality Score: 82/100
- Code Quality: 85/100
- Test Quality: 78/100
- Total Violations: 145
  - Critical: 15
  - Warning: 67
  - Suggestion: 63

## Highest Priority Issues (Cross-Cutting)
1. [CRITICAL] Mutable default arguments in 5 production classes
2. [CRITICAL] 12 tests with 5+ unrelated assertions
3. [WARNING] 45 functions missing type hints
4. [WARNING] 23 repetitive test setups need factories

## Code Quality Findings
[Results from code-audit agent]

## Test Quality Findings
[Results from test-audit agent]

## Action Plan
[Prioritized list of improvements with estimated impact]

## Trend Analysis
[Comparison with previous audits if available]
```

### 3. Prioritizes Violations

**Priority Matrix:**

| Severity | Code Impact | Test Impact | Priority |
|----------|-------------|-------------|----------|
| Critical | Production bugs | Test reliability | P0 - Fix now |
| Warning | Maintainability | Test clarity | P1 - Fix this sprint |
| Suggestion | Best practice | Optimization | P2 - Consider |

**Cross-Cutting Issues (Highest Priority):**
- Same pattern violation in both code and tests
- Violations that make testing harder (complexity, poor SRP)
- Issues that block new development

### 4. Tracks Trends

**Metrics Over Time:**
```json
{
  "audit_date": "2025-12-03",
  "scores": {
    "overall": 82,
    "code": 85,
    "tests": 78
  },
  "violations": {
    "critical": 15,
    "warning": 67,
    "suggestion": 63
  },
  "trend": {
    "overall_change": "+5",
    "critical_fixed": 8,
    "new_violations": 3
  }
}
```

## Execution Modes

### Mode 1: Full Quality Audit
```
Run comprehensive quality audit.
Execute: test-audit + code-audit in parallel.
Generate: unified report with prioritized action plan.
Output: forge-audit-YYYY-MM-DD.md
```

**What Happens:**
1. Launch test-audit agent (async)
2. Launch code-audit agent (async)
3. Wait for both to complete
4. Merge results
5. Prioritize violations
6. Generate unified report
7. Calculate quality scores
8. Compare with previous audit (if exists)

**Output:**
- Single comprehensive report
- Actionable priorities
- Quality metrics dashboard

### Mode 2: Quick Health Check
```
Run quick health check (critical violations only).
Execute: test-audit + code-audit with --critical-only flag.
Focus: P0 issues requiring immediate attention.
```

**What Happens:**
1. Run focused audits (critical severity only)
2. Generate brief summary
3. Highlight blockers
4. Skip detailed analysis

**Use Case:**
- Pre-commit checks
- CI/CD quality gate
- Quick status update

### Mode 3: Trend Analysis
```
Compare current codebase with previous audit.
Execute: test-audit + code-audit + diff analysis.
Output: Trend report showing improvements and regressions.
```

**What Happens:**
1. Run full audits
2. Load previous audit results
3. Calculate deltas
4. Identify improvements
5. Flag regressions
6. Generate trend report

**Metrics:**
- Violations fixed since last audit
- New violations introduced
- Quality score trajectory
- Coverage improvements

### Mode 4: Selective Audit
```
Run specific audit only.
Execute: [test-audit | code-audit]
Output: Single agent report.
```

**Use Case:**
- Testing new tests (test-audit only)
- Reviewing production changes (code-audit only)
- Focused improvements

## Agent Coordination

### Parallel Execution (Default)
```
┌─────────────┐
│   Forge     │
└──────┬──────┘
       │
       ├────────────┬────────────┐
       │            │            │
┌──────▼──────┐ ┌──▼─────────┐ │
│ Test Audit  │ │ Code Audit │ │
└──────┬──────┘ └──┬─────────┘ │
       │            │            │
       └────────────┴────────────┘
                    │
             ┌──────▼──────┐
             │   Merge     │
             │  Results    │
             └──────┬──────┘
                    │
             ┌──────▼──────┐
             │  Prioritize │
             └──────┬──────┘
                    │
             ┌──────▼──────┐
             │   Report    │
             └─────────────┘
```

**Benefits:**
- Faster execution (2x speedup)
- Independent analysis
- Parallel resource usage

### Sequential Execution
```
┌─────────────┐
│   Forge     │
└──────┬──────┘
       │
┌──────▼──────┐
│ Test Audit  │
└──────┬──────┘
       │
┌──────▼──────┐
│ Code Audit  │
└──────┬──────┘
       │
┌──────▼──────┐
│   Merge     │
└─────────────┘
```

**Use Case:**
- Resource-constrained environments
- Debugging agent issues
- Step-by-step review

## Report Structure

### Executive Summary
```markdown
## Executive Summary

**Quality Score: 82/100** ⬆️ +5 from last audit

### Breakdown
- Code Quality: 85/100 ⬆️ +3
- Test Quality: 78/100 ⬆️ +7

### Violations
- Critical: 15 (down from 23) ✅
- Warning: 67 (down from 89) ✅
- Suggestion: 63 (down from 71) ✅

### Top Achievements
- Fixed all mutable default arguments ✅
- Improved type hint coverage to 95% ✅
- Reduced avg function size from 35 to 22 lines ✅

### Remaining Concerns
- 12 tests still have multiple assertions
- 45 functions missing type hints
- 23 test setups need factories
```

### Priority Matrix
```markdown
## Action Plan - Prioritized

### P0 - Fix Immediately (Est: 2-4 hours)
1. ❌ base_job.py:25 - CRITICAL: Mutable default (list = [])
2. ❌ test_agent_client.py:387 - CRITICAL: 8 unrelated assertions
3. ❌ auth_service.py:142 - CRITICAL: Function too large (150 lines)

### P1 - Fix This Sprint (Est: 1-2 days)
4. ⚠️ 45 functions missing type hints
5. ⚠️ 23 test setups need factories
6. ⚠️ 12 tests missing 3As structure

### P2 - Consider (Est: 3-5 days)
7. 💡 Magic numbers in 15 files
8. 💡 Could split 8 large functions
9. 💡 Builder pattern opportunities in tests
```

### Detailed Findings
```markdown
## Code Audit Results
[Full code-audit report]

## Test Audit Results
[Full test-audit report]

## Cross-Cutting Concerns
[Issues appearing in both code and tests]
```

### Metrics Dashboard
```markdown
## Quality Metrics

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Overall Score | 82/100 | 90/100 | 🟡 In Progress |
| Type Hints | 92% | 95% | 🟡 Close |
| Docstrings | 87% | 90% | 🟡 Close |
| Test 3As | 75% | 90% | 🔴 Needs Work |
| Factories | 63 | 70 | 🟡 Growing |
| Avg Function Size | 22 lines | <30 | 🟢 Good |
| Max Nesting | 4 levels | <4 | 🟢 Good |
```

## Usage Examples

### Example 1: Weekly Quality Check
```bash
# User runs:
Run forge quality audit

# Forge executes:
1. Launch test-audit (parallel)
2. Launch code-audit (parallel)
3. Wait for completion
4. Merge results
5. Generate unified report

# User receives:
- Comprehensive report at .claude/audit-reports/forge-YYYY-MM-DD.md
- Quality score: 82/100
- 15 critical, 67 warnings, 63 suggestions
- Prioritized action plan
```

### Example 2: Pre-Release Audit
```bash
# User runs:
Run forge quality audit with trend analysis

# Forge executes:
1. Full audit (test + code)
2. Load previous audit from .claude/audit-reports/
3. Calculate improvements
4. Flag any regressions
5. Generate trend report

# User receives:
- Trend report showing +5 quality score improvement
- List of 8 critical issues fixed
- 3 new violations to address
- Green light for release if no critical issues
```

### Example 3: CI/CD Quality Gate
```bash
# User runs:
Run forge quick health check

# Forge executes:
1. Critical violations only (fast scan)
2. Exit code 0 if no critical violations
3. Exit code 1 if critical violations found

# CI/CD uses:
if forge_status != 0:
    block_merge()
```

## Integration Points

### With Development Workflow

**Pre-Commit:**
```bash
# Developer runs before committing
forge quick-check

# If critical violations:
# - List violations
# - Block commit
# - Suggest fixes
```

**Pull Request:**
```bash
# CI runs on PR
forge audit --compare-to main

# Generates:
# - Quality diff (before → after)
# - New violations introduced
# - Pass/fail for merge
```

**Weekly Review:**
```bash
# Team reviews quality trends
forge audit --trend

# Discusses:
# - Improvements
# - Persistent issues
# - Action items
```

### With Metrics Tracking

**Store Results:**
```bash
.claude/audit-reports/
├── forge-2025-12-03.md
├── forge-2025-11-26.md
├── forge-2025-11-19.md
└── metrics.json  # Time-series data
```

**Visualize Trends:**
```python
# Generate charts from metrics.json
- Quality score over time
- Violation counts by severity
- Coverage improvements
- Team velocity on fixes
```

## Success Criteria

### Excellent Codebase (90+ Score)
- ✅ No critical violations
- ✅ < 10 warnings total
- ✅ 95%+ type hint coverage
- ✅ 90%+ docstring coverage
- ✅ 90%+ tests with clear 3As
- ✅ 70+ factories and builders
- ✅ All functions < 50 lines

### Good Codebase (80-89 Score)
- ✅ < 5 critical violations
- ✅ < 30 warnings
- ✅ 90%+ type hints
- ✅ 85%+ docstrings
- ✅ Most tests well-structured

### Needs Improvement (< 80 Score)
- ⚠️ > 5 critical violations
- ⚠️ > 50 warnings
- ⚠️ < 90% type hints
- ⚠️ Missing test infrastructure

## Configuration

### Thresholds (Configurable)
```yaml
# .claude/forge-config.yml
quality_thresholds:
  excellent: 90
  good: 80
  needs_improvement: 70

violation_limits:
  critical: 0
  warning: 10
  suggestion: 50

coverage_targets:
  type_hints: 95
  docstrings: 90
  test_3as: 90

function_size:
  warning_threshold: 50
  critical_threshold: 100

complexity:
  max_nesting_depth: 4
  max_cyclomatic_complexity: 10
```

## Output Locations

**Reports:**
- `.claude/audit-reports/forge-YYYY-MM-DD.md` - Full report
- `.claude/audit-reports/quick-check.txt` - Quick check results
- `.claude/audit-reports/metrics.json` - Time-series data

**Logs:**
- `.claude/audit-reports/forge.log` - Execution log
- `.claude/audit-reports/test-audit.log` - Test audit details
- `.claude/audit-reports/code-audit.log` - Code audit details

## Future Enhancements

1. **Custom Rules** - Team-specific patterns to enforce
2. **Auto-Fix** - Automated fixes for common violations
3. **Git Integration** - Track quality per commit
4. **Team Scorecards** - Quality metrics by contributor
5. **Regression Prevention** - Block PRs that lower quality

---

## Summary

Forge is your **quality command center** that:
- 🔍 **Discovers** violations across all code
- 🎯 **Prioritizes** fixes by impact
- 📊 **Tracks** improvements over time
- 🚀 **Guides** team to excellence

**Single command, complete visibility.**
