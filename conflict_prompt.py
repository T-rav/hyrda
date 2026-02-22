"""Shared conflict resolution prompt builder for Hydra.

Used by both :mod:`pr_unsticker` and :mod:`review_phase` to produce
enriched prompts that give the conflict-resolution agent full context
about the issue, the plan, what changed on main, and which files the
PR touches.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import GitHubIssue


def _extract_plan_comment(comments: list[str]) -> str:
    """Return the first comment containing ``## Implementation Plan``, or ``""``."""
    for c in comments:
        if "## Implementation Plan" in c:
            return c
    return ""


def build_conflict_prompt(
    issue: GitHubIssue,
    pr_changed_files: list[str],
    main_commits: str,
    last_error: str | None,
    attempt: int,
) -> str:
    """Build an enriched conflict resolution prompt.

    Parameters
    ----------
    issue:
        The full GitHub issue (number, title, body, comments).
    pr_changed_files:
        File paths changed in the PR (from ``gh pr diff --name-only``).
    main_commits:
        One-line commit summaries of what landed on main since the
        branch diverged (from ``git log --oneline HEAD..origin/main``).
    last_error:
        Error output from the previous failed attempt, or *None*.
    attempt:
        Current attempt number (1-based).
    """
    sections: list[str] = []

    # --- Header ---
    sections.append(
        f"The branch for issue #{issue.number} ({issue.title}) has "
        f"merge conflicts with main.\n\n"
        "There is a `git merge` in progress with conflict markers "
        "in the working tree."
    )

    # --- Issue Context ---
    if issue.body:
        body_preview = issue.body[:3000]
        sections.append(f"## Issue Description\n\n{body_preview}")

    # --- Plan ---
    plan = _extract_plan_comment(issue.comments)
    if plan:
        sections.append(f"## Implementation Plan\n\n{plan}")

    # --- What landed on main ---
    if main_commits:
        sections.append(
            f"## Recent Commits on Main (since branch diverged)\n\n"
            f"These commits landed on main after this branch was created. "
            f"Understand what they changed so you can resolve conflicts "
            f"correctly and catch stale references.\n\n"
            f"```\n{main_commits}\n```"
        )

    # --- PR changed files ---
    if pr_changed_files:
        file_list = "\n".join(f"- {f}" for f in pr_changed_files)
        sections.append(f"## Files Changed in This PR\n\n{file_list}")

    # --- Instructions ---
    sections.append(
        "## Instructions\n\n"
        "1. Run `git diff --name-only --diff-filter=U` to list "
        "conflicted files.\n"
        "2. Open each conflicted file and understand BOTH sides of the "
        "conflict:\n"
        "   - **Ours** (HEAD) = the PR's changes for the issue above.\n"
        "   - **Theirs** (origin/main) = what landed on main (see "
        "commits above).\n"
        "3. Resolve each conflict by keeping the PR's intent while "
        "adopting main's patterns. If main refactored code (renamed "
        "functions, changed APIs, moved files), use main's new patterns.\n"
        "4. **Check non-conflicted files too.** If main renamed "
        "functions, changed APIs, or moved code, non-conflicted files "
        "may have stale references (imports, function calls, test "
        "assertions). Fix these proactively.\n"
        "5. Stage all resolved files with `git add`.\n"
        "6. Complete the merge with `git commit --no-edit`.\n"
        "7. Run `make quality` to ensure everything passes.\n"
        "8. If quality fails, fix the issues and commit again."
    )

    # --- Rules ---
    sections.append(
        "## Rules\n\n"
        "- Keep the intent of the original PR changes.\n"
        "- Incorporate upstream (main) changes correctly.\n"
        "- Do NOT push to remote. Do NOT create pull requests.\n"
        "- Ensure `make quality` passes before finishing."
    )

    # --- Previous attempt error ---
    if last_error and attempt > 1:
        sections.append(
            f"## Previous Attempt Failed\n\n"
            f"Attempt {attempt - 1} resolved the conflicts but "
            f"failed verification:\n"
            f"```\n{last_error[-3000:]}\n```\n"
            f"Please resolve the conflicts again, paying attention "
            f"to the above errors."
        )

    # --- Optional memory suggestion ---
    sections.append(
        "## Optional: Memory Suggestion\n\n"
        "If you discover a reusable pattern or insight during this "
        "conflict resolution that would help future agent runs, "
        "you may output ONE suggestion:\n\n"
        "MEMORY_SUGGESTION_START\n"
        "title: Short descriptive title\n"
        "learning: What was learned and why it matters\n"
        "context: How it was discovered (reference issue/PR numbers)\n"
        "MEMORY_SUGGESTION_END\n\n"
        "Only suggest genuinely valuable learnings — not trivial observations."
    )

    return "\n\n".join(sections)
