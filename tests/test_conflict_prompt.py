"""Tests for the shared conflict prompt builder."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from conflict_prompt import _extract_plan_comment, build_conflict_prompt
from models import GitHubIssue


def _make_issue(**kwargs) -> GitHubIssue:
    defaults = {
        "number": 42,
        "title": "Fix the widget",
        "body": "The widget is broken. Please fix it.",
        "labels": [],
        "comments": [],
    }
    defaults.update(kwargs)
    return GitHubIssue(**defaults)


class TestExtractPlanComment:
    def test_extracts_plan_comment(self) -> None:
        comments = [
            "Some random comment",
            "## Implementation Plan\n\n1. Do thing\n2. Test thing",
            "Another comment",
        ]
        result = _extract_plan_comment(comments)
        assert "## Implementation Plan" in result
        assert "Do thing" in result

    def test_returns_empty_when_no_plan(self) -> None:
        comments = ["Just a comment", "Another one"]
        assert _extract_plan_comment(comments) == ""

    def test_returns_empty_for_empty_list(self) -> None:
        assert _extract_plan_comment([]) == ""


class TestBuildConflictPrompt:
    def test_includes_issue_header(self) -> None:
        issue = _make_issue()
        prompt = build_conflict_prompt(issue, [], "", None, 1)
        assert "issue #42" in prompt
        assert "Fix the widget" in prompt
        assert "merge conflicts with main" in prompt

    def test_includes_issue_body(self) -> None:
        issue = _make_issue(body="Detailed description of the bug.")
        prompt = build_conflict_prompt(issue, [], "", None, 1)
        assert "## Issue Description" in prompt
        assert "Detailed description of the bug." in prompt

    def test_omits_issue_body_when_empty(self) -> None:
        issue = _make_issue(body="")
        prompt = build_conflict_prompt(issue, [], "", None, 1)
        assert "## Issue Description" not in prompt

    def test_includes_plan_comment(self) -> None:
        issue = _make_issue(
            comments=["## Implementation Plan\n\n1. Fix module A\n2. Update tests"]
        )
        prompt = build_conflict_prompt(issue, [], "", None, 1)
        assert "## Implementation Plan" in prompt
        assert "Fix module A" in prompt

    def test_omits_plan_when_no_plan_comment(self) -> None:
        issue = _make_issue(comments=["Just a regular comment"])
        prompt = build_conflict_prompt(issue, [], "", None, 1)
        # Should only have the Instructions section, not Implementation Plan
        plan_count = prompt.count("## Implementation Plan")
        assert plan_count == 0

    def test_includes_main_commits(self) -> None:
        issue = _make_issue()
        commits = "abc1234 Refactor polling loop\ndef5678 Add new config option"
        prompt = build_conflict_prompt(issue, [], commits, None, 1)
        assert "## Recent Commits on Main" in prompt
        assert "abc1234 Refactor polling loop" in prompt
        assert "def5678 Add new config option" in prompt

    def test_omits_main_commits_when_empty(self) -> None:
        issue = _make_issue()
        prompt = build_conflict_prompt(issue, [], "", None, 1)
        assert "## Recent Commits on Main" not in prompt

    def test_includes_pr_changed_files(self) -> None:
        issue = _make_issue()
        files = ["orchestrator.py", "tests/test_orchestrator.py", "models.py"]
        prompt = build_conflict_prompt(issue, files, "", None, 1)
        assert "## Files Changed in This PR" in prompt
        assert "- orchestrator.py" in prompt
        assert "- tests/test_orchestrator.py" in prompt
        assert "- models.py" in prompt

    def test_omits_files_when_empty(self) -> None:
        issue = _make_issue()
        prompt = build_conflict_prompt(issue, [], "", None, 1)
        assert "## Files Changed in This PR" not in prompt

    def test_includes_enriched_instructions(self) -> None:
        issue = _make_issue()
        prompt = build_conflict_prompt(issue, [], "", None, 1)
        assert "## Instructions" in prompt
        assert "make quality" in prompt
        assert "non-conflicted files" in prompt.lower()
        assert "PR's intent" in prompt

    def test_includes_rules(self) -> None:
        issue = _make_issue()
        prompt = build_conflict_prompt(issue, [], "", None, 1)
        assert "## Rules" in prompt
        assert "Do NOT push to remote" in prompt

    def test_no_previous_error_on_first_attempt(self) -> None:
        issue = _make_issue()
        prompt = build_conflict_prompt(issue, [], "", None, 1)
        assert "Previous Attempt Failed" not in prompt

    def test_includes_previous_error_on_retry(self) -> None:
        issue = _make_issue()
        prompt = build_conflict_prompt(
            issue, [], "", "make quality failed: ruff error", 2
        )
        assert "## Previous Attempt Failed" in prompt
        assert "ruff error" in prompt
        assert "Attempt 1" in prompt

    def test_truncates_long_error(self) -> None:
        issue = _make_issue()
        long_error = "x" * 5000
        prompt = build_conflict_prompt(issue, [], "", long_error, 3)
        # Should only include last 3000 chars
        assert "## Previous Attempt Failed" in prompt
        error_section = prompt.split("## Previous Attempt Failed")[1].split("##")[0]
        # The x's in the error section should be <= 3000
        assert error_section.count("x") <= 3000

    def test_all_sections_present_with_full_context(self) -> None:
        issue = _make_issue(
            body="Fix the widget rendering",
            comments=["## Implementation Plan\n\n1. Update render.py\n2. Add tests"],
        )
        files = ["render.py", "tests/test_render.py"]
        commits = "abc123 Refactor rendering pipeline"

        prompt = build_conflict_prompt(issue, files, commits, "previous error text", 2)

        assert "## Issue Description" in prompt
        assert "## Implementation Plan" in prompt
        assert "## Recent Commits on Main" in prompt
        assert "## Files Changed in This PR" in prompt
        assert "## Instructions" in prompt
        assert "## Rules" in prompt
        assert "## Previous Attempt Failed" in prompt
        assert "## Optional: Memory Suggestion" in prompt

    def test_body_truncated_at_3000_chars(self) -> None:
        issue = _make_issue(body="a" * 5000)
        prompt = build_conflict_prompt(issue, [], "", None, 1)
        body_section = prompt.split("## Issue Description")[1].split("##")[0]
        assert body_section.count("a") == 3000

    def test_includes_memory_suggestion_instructions(self) -> None:
        issue = _make_issue()
        prompt = build_conflict_prompt(issue, [], "", None, 1)
        assert "MEMORY_SUGGESTION_START" in prompt
        assert "MEMORY_SUGGESTION_END" in prompt
        assert "## Optional: Memory Suggestion" in prompt

    def test_includes_conflicting_files_section(self) -> None:
        issue = _make_issue()
        prompt = build_conflict_prompt(
            issue,
            [],
            "",
            None,
            1,
            conflicting_files=["src/foo.py", "src/bar.py"],
        )
        assert "## Conflicting Files" in prompt
        assert "- src/foo.py" in prompt
        assert "- src/bar.py" in prompt

    def test_includes_main_diff_section(self) -> None:
        issue = _make_issue()
        diff = "diff --git a/foo.py b/foo.py\n+added line"
        prompt = build_conflict_prompt(
            issue,
            [],
            "",
            None,
            1,
            main_diff=diff,
        )
        assert "## What Changed on Main" in prompt
        assert "+added line" in prompt

    def test_omits_conflicting_files_when_none(self) -> None:
        issue = _make_issue()
        prompt = build_conflict_prompt(issue, [], "", None, 1)
        assert "## Conflicting Files" not in prompt

    def test_omits_conflicting_files_when_empty(self) -> None:
        issue = _make_issue()
        prompt = build_conflict_prompt(issue, [], "", None, 1, conflicting_files=[])
        assert "## Conflicting Files" not in prompt

    def test_omits_main_diff_when_empty(self) -> None:
        issue = _make_issue()
        prompt = build_conflict_prompt(issue, [], "", None, 1, main_diff="")
        assert "## What Changed on Main" not in prompt

    def test_backward_compatible_without_new_params(self) -> None:
        """Calling without the new kwargs should still work."""
        issue = _make_issue()
        prompt = build_conflict_prompt(issue, [], "", None, 1)
        assert "merge conflicts with main" in prompt
        assert "## Instructions" in prompt
        assert "## Conflicting Files" not in prompt
        assert "## What Changed on Main" not in prompt

    def test_simplified_instructions(self) -> None:
        """Instructions should be concise, not step-by-step."""
        issue = _make_issue()
        prompt = build_conflict_prompt(issue, [], "", None, 1)
        instructions = prompt.split("## Instructions")[1].split("##")[0]
        assert "make quality" in instructions
        # Should not have numbered step-by-step list
        assert "1. Run `git diff" not in instructions

    def test_instructions_include_gh_issue_reference(self) -> None:
        """Instructions should tell the agent how to look up full issue history."""
        issue = _make_issue(number=99)
        prompt = build_conflict_prompt(issue, [], "", None, 1)
        assert "gh issue view 99" in prompt
