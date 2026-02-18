# Create a GitHub Issue

Take a rough description from the user, research the relevant codebase, and create a well-structured GitHub issue with full context, file references, and acceptance criteria.

## Usage

```
/gh-issue add a Stop hook that checks for Langfuse tracing in new LLM code
/gh-issue the tasks service Google Drive auth flow doesn't handle token refresh
```

`$ARGUMENTS` contains the rough issue description from the user.

If `$ARGUMENTS` is empty, ask the user to describe the issue.

## Instructions

### Phase 1: Understand the Request

Parse `$ARGUMENTS` to understand what the user wants filed as an issue. Identify:
- What area of the codebase is involved
- What the problem or feature request is
- Any specific services, files, or patterns mentioned

### Phase 2: Research the Codebase

Before writing the issue, explore the codebase to gather concrete context:
- Use Grep/Glob/Read to find the relevant files, services, and patterns
- Understand the current state of the code related to the issue
- Identify specific file paths, function names, and line numbers
- Check for existing related patterns or prior art in the codebase
- Look at how similar things are already done elsewhere

This research makes the issue actionable rather than vague.

### Phase 3: Check for Duplicates

Before creating, search for existing issues:
```bash
gh issue list --repo 8thlight/insightmesh --label claude-explore --state open --search "<key terms>"
```

If a matching open issue already exists, tell the user and show the link instead of creating a duplicate.

### Phase 4: Create the Issue

Create the issue using `gh issue create` with:
- **Label**: `claude-explore`
- **Assignee**: `T-rav`
- **Title**: Concise, descriptive (under 70 chars)
- **Body**: Well-structured with the sections below

#### Issue Body Structure

```markdown
## Problem

Clear description of what's missing, broken, or needed. Include WHY this matters.

## Current State

What exists today — reference specific files, services, and patterns found during research.
Use full file paths so the implementer can navigate directly.

## Proposed Solution

Concrete description of what should be built or changed.
Reference existing patterns in the codebase that should be followed.

## Scope

### Files/Services involved:
- List specific files and directories

### Key integration points:
- List functions, classes, or patterns to hook into

## Acceptance Criteria

- [ ] Checklist of concrete, verifiable outcomes
- [ ] Each item should be testable
- [ ] Include test requirements
```

#### gh issue create command

```bash
gh issue create --repo 8thlight/insightmesh \
  --assignee T-rav \
  --label claude-explore \
  --title "<title>" \
  --body "$(cat <<'EOF'
<body content>
EOF
)"
```

### Phase 5: Report Back

Show the user:
- The issue URL
- A brief summary of what was filed
