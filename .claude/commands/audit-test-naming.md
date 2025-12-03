# Audit Test File Naming

Perform a comprehensive audit of test file naming conventions across all services and fix any misalignments with source files.

## Objective

Ensure all test files follow consistent naming conventions that clearly map to the source files they test.

## Process

### 1. Discovery Phase

Scan all test directories:
```bash
find bot/tests tasks/tests control_plane/tests agent-service/tests -name "test_*.py" -type f | sort
```

For each service, list source files:
```bash
ls -1 bot/services/*.py bot/handlers/*.py
ls -1 tasks/api/*.py tasks/services/*.py
ls -1 control_plane/api/*.py
ls -1 agent-service/services/*.py agent-service/agents/*.py
```

### 2. Naming Convention Rules

**Primary Rule:** Test files should match their source file names:
- Source: `api/jobs.py` → Test: `test_api_jobs.py` ✅
- Source: `services/llm_service.py` → Test: `test_llm_service.py` ✅

**Suffix Rules (Only When Needed):**
- `_unit.py` - Unit tests in isolation
- `_integration.py` - Integration tests with dependencies
- `_[feature].py` - Tests for specific feature/aspect (e.g., `_caching.py`)

**Anti-Patterns to Fix:**
- ❌ `_comprehensive` suffix - meaningless quality descriptor
- ❌ `test_message_handlers.py` testing `file_processors` - wrong module name
- ❌ Multiple test files with no clear distinction (rename to unit/integration)

### 3. Identification Phase

Create a mapping table:

| Service | Test File | Source File | Issue | Proposed Fix |
|---------|-----------|-------------|-------|--------------|
| tasks | test_api_jobs_comprehensive.py | api/jobs.py | Unnecessary suffix | → test_api_jobs.py |
| bot | test_message_handlers.py | handlers/message_handlers.py + file_processors | Ambiguous | → test_message_handlers_integration.py |

**Look for:**
1. Tests with `_comprehensive` suffix
2. Test files that don't match any source file
3. Source files with no corresponding test
4. Multiple test files testing the same source (need unit/integration distinction)
5. Test files with misleading names

### 4. Analysis Phase

For each potential rename, verify what the test actually tests:
```bash
# Check imports to see what modules are tested
grep "from " bot/tests/test_suspicious_name.py | grep -E "(handlers|services|agents)"

# Check test class names
grep "class Test" bot/tests/test_suspicious_name.py
```

### 5. Proposal Phase

Present findings in a clear table format:

```markdown
## Proposed Test File Renames

### Priority 1: Clear Misalignments (MUST FIX)
1. test_api_gdrive_comprehensive.py → test_api_gdrive.py
   - Source: tasks/api/gdrive.py
   - Reason: Unnecessary "_comprehensive" suffix

2. test_message_handlers.py → test_message_handlers_integration.py
   - Source: Multiple (message_handlers + file_processors)
   - Reason: Clarify it's integration testing vs unit tests

### Priority 2: Keep As-Is (CORRECT)
- test_message_handlers_unit.py ✅ (clear distinction)
- test_user_service_caching.py ✅ (specific feature)
```

### 6. Execution Phase

**IMPORTANT:** Use `git mv` to preserve history:

```bash
# DO THIS (preserves history):
git mv tasks/tests/test_api_jobs_comprehensive.py tasks/tests/test_api_jobs.py

# DON'T DO THIS (loses history):
mv tasks/tests/test_api_jobs_comprehensive.py tasks/tests/test_api_jobs.py
git add .
```

Check status:
```bash
git status --short
# Should show: R  old_name.py -> new_name.py
```

### 7. Verification Phase

Since these are pure renames with no code changes, verification is straightforward:

1. **Linting** (should pass immediately):
```bash
make lint
```

2. **Check CI status** - Existing CI run should show tests passing

3. **If you want to verify locally** (optional):
```bash
# Run specific renamed test files
cd tasks && make test
cd bot && make test
```

### 8. Commit Phase

Create a detailed commit message:

```bash
git commit -m "$(cat <<'EOF'
refactor: Improve test file naming to match source files

Renamed X test files for better clarity and alignment with source files:

**[Service Name] (N renames):**
1. old_name.py → new_name.py
   - Matches source: path/to/source.py
   - Reason: [Brief reason]

**Rationale:**
- Test files should clearly map to source files they test
- Suffixes should describe test type (integration/unit), not quality (comprehensive)
- Makes it easier to find tests for a given source file

**No Code Changes:**
- Only file renames (git mv preserves history)
- All test logic remains identical
- No functional changes

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### 9. Push and Document

```bash
git push
```

Create summary for user:
- List all renames with rationale
- List files kept as-is with explanation
- Confirm tests still pass
- Explain improved navigation

## Expected Outcomes

- **Clear mapping** between test files and source files
- **Consistent naming** across all services
- **Easier navigation** - developers can find tests instantly
- **Better organization** - unit vs integration tests clearly distinguished
- **Git history preserved** - renames tracked properly

## Edge Cases

**Multiple test files for one source:**
- OK if they test different aspects (unit vs integration, specific features)
- Name should clarify: `test_module_unit.py`, `test_module_integration.py`

**Test files testing multiple modules:**
- Usually indicates integration tests
- Name should reflect primary module + `_integration` suffix

**Source files with no tests:**
- Document but don't create placeholder tests
- May be legitimate (utility modules, types, etc.)

**Test files with no matching source:**
- Investigate - may be testing deleted code
- May be testing behavior across modules (integration tests)
- Rename to clarify what's being tested

## Success Criteria

✅ All test files clearly map to source files
✅ No arbitrary suffixes (comprehensive, full, etc.)
✅ Unit vs integration tests clearly distinguished
✅ Git history preserved with `git mv`
✅ All tests still pass
✅ Commit pushed with detailed message
