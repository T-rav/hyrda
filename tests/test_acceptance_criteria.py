"""Tests for acceptance criteria generation in review_phase.py."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

if TYPE_CHECKING:
    from config import HydraConfig

from events import EventBus
from models import GitHubIssue, PRInfo, VerificationCriteria
from review_phase import ReviewPhase
from state import StateTracker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_phase(
    config: HydraConfig,
    *,
    event_bus: EventBus | None = None,
) -> ReviewPhase:
    """Build a ReviewPhase with standard mock dependencies."""
    state = StateTracker(config.state_file)
    stop_event = asyncio.Event()
    active_issues: set[int] = set()

    mock_wt = AsyncMock()
    mock_wt.destroy = AsyncMock()

    mock_reviewers = AsyncMock()
    mock_prs = AsyncMock()

    phase = ReviewPhase(
        config=config,
        state=state,
        worktrees=mock_wt,
        reviewers=mock_reviewers,
        prs=mock_prs,
        stop_event=stop_event,
        active_issues=active_issues,
        event_bus=event_bus or EventBus(),
    )

    return phase


def _make_issue(
    number: int = 42,
    body: str = "Fix the login form validation",
    comments: list[str] | None = None,
) -> GitHubIssue:
    return GitHubIssue(
        number=number,
        title="Fix login validation",
        body=body,
        labels=["ready"],
        comments=comments or [],
        url=f"https://github.com/test-org/test-repo/issues/{number}",
    )


def _make_pr(number: int = 101, issue_number: int = 42) -> PRInfo:
    return PRInfo(
        number=number,
        issue_number=issue_number,
        branch=f"agent/issue-{issue_number}",
        url=f"https://github.com/test-org/test-repo/pull/{number}",
    )


SAMPLE_TRANSCRIPT = """\
Thinking about the changes...

AC_START
## Acceptance Criteria

AC-1: Login form displays validation errors for empty email field
AC-2: Login form displays validation errors for malformed email
AC-3: Submit button is disabled while validation errors exist

## Human Verification Instructions

1. Open the application in a browser
2. Navigate to the login page
3. Click "Submit" without entering an email
4. Verify a red error message appears below the email field
5. Enter "not-an-email" and click Submit
6. Verify the error message says "Invalid email format"
AC_END

Done.
"""

SAMPLE_TRANSCRIPT_NO_MARKERS = """\
Here is the analysis of the changes made.
The login form was updated to include validation.
"""

SAMPLE_DIFF = """\
diff --git a/login.py b/login.py
index abc1234..def5678 100644
--- a/login.py
+++ b/login.py
@@ -10,6 +10,12 @@ def validate_email(email):
+    if not email:
+        return "Email is required"
+    if "@" not in email:
+        return "Invalid email format"
     return None

diff --git a/tests/test_login.py b/tests/test_login.py
new file mode 100644
--- /dev/null
+++ b/tests/test_login.py
@@ -0,0 +1,20 @@
+def test_validate_email_empty():
+    assert validate_email("") == "Email is required"
"""


# ---------------------------------------------------------------------------
# _build_ac_prompt tests
# ---------------------------------------------------------------------------


class TestBuildAcPrompt:
    """Tests for ReviewPhase._build_ac_prompt."""

    def test_includes_issue_body(self) -> None:
        prompt = ReviewPhase._build_ac_prompt(
            issue_body="Fix the login form",
            plan_comment="",
            diff_summary="",
            test_files=[],
        )
        assert "Fix the login form" in prompt

    def test_includes_plan_comment(self) -> None:
        plan = "## Implementation Plan\n\n1. Update validation logic"
        prompt = ReviewPhase._build_ac_prompt(
            issue_body="issue body",
            plan_comment=plan,
            diff_summary="",
            test_files=[],
        )
        assert "Update validation logic" in prompt
        assert "## Implementation Plan" in prompt

    def test_includes_diff_summary(self) -> None:
        diff = "+    if not email:\n+        return 'required'"
        prompt = ReviewPhase._build_ac_prompt(
            issue_body="issue body",
            plan_comment="",
            diff_summary=diff,
            test_files=[],
        )
        assert "if not email" in prompt
        assert "```diff" in prompt

    def test_includes_test_files(self) -> None:
        prompt = ReviewPhase._build_ac_prompt(
            issue_body="issue body",
            plan_comment="",
            diff_summary="",
            test_files=["tests/test_login.py", "tests/test_auth.py"],
        )
        assert "tests/test_login.py" in prompt
        assert "tests/test_auth.py" in prompt

    def test_handles_missing_plan(self) -> None:
        prompt = ReviewPhase._build_ac_prompt(
            issue_body="issue body",
            plan_comment="",
            diff_summary="some diff",
            test_files=[],
        )
        assert "Implementation Plan" not in prompt
        assert "issue body" in prompt

    def test_handles_empty_issue_body(self) -> None:
        prompt = ReviewPhase._build_ac_prompt(
            issue_body="",
            plan_comment="",
            diff_summary="",
            test_files=[],
        )
        assert "(no issue body)" in prompt

    def test_truncates_long_issue_body(self) -> None:
        long_body = "x" * 10000
        prompt = ReviewPhase._build_ac_prompt(
            issue_body=long_body,
            plan_comment="",
            diff_summary="",
            test_files=[],
        )
        assert len(long_body) > 5000
        # The prompt should contain a truncated version
        assert "x" * 5000 in prompt
        assert "x" * 5001 not in prompt

    def test_truncates_long_diff(self) -> None:
        long_diff = "+" * 20000
        prompt = ReviewPhase._build_ac_prompt(
            issue_body="body",
            plan_comment="",
            diff_summary=long_diff,
            test_files=[],
        )
        assert "+" * 10000 in prompt
        assert "+" * 10001 not in prompt

    def test_includes_ac_marker_instructions(self) -> None:
        prompt = ReviewPhase._build_ac_prompt(
            issue_body="body",
            plan_comment="",
            diff_summary="",
            test_files=[],
        )
        assert "AC_START" in prompt
        assert "AC_END" in prompt
        assert "AC-1" in prompt

    def test_asks_for_functional_verification(self) -> None:
        prompt = ReviewPhase._build_ac_prompt(
            issue_body="body",
            plan_comment="",
            diff_summary="",
            test_files=[],
        )
        assert "functional" in prompt.lower() or "UAT" in prompt


# ---------------------------------------------------------------------------
# _extract_criteria tests
# ---------------------------------------------------------------------------


class TestExtractCriteria:
    """Tests for ReviewPhase._extract_criteria."""

    def test_parses_ac_markers(self) -> None:
        result = ReviewPhase._extract_criteria(SAMPLE_TRANSCRIPT, issue_number=42)
        assert result is not None
        assert result.issue_number == 42
        assert result.raw_text != ""

    def test_extracts_numbered_items(self) -> None:
        result = ReviewPhase._extract_criteria(SAMPLE_TRANSCRIPT, issue_number=42)
        assert result is not None
        assert len(result.criteria) == 3
        assert (
            "Login form displays validation errors for empty email field"
            in result.criteria[0]
        )

    def test_returns_none_on_missing_markers(self) -> None:
        result = ReviewPhase._extract_criteria(
            SAMPLE_TRANSCRIPT_NO_MARKERS, issue_number=42
        )
        assert result is None

    def test_sets_generated_at(self) -> None:
        result = ReviewPhase._extract_criteria(SAMPLE_TRANSCRIPT, issue_number=42)
        assert result is not None
        assert result.generated_at != ""
        # Should be an ISO timestamp
        assert "T" in result.generated_at

    def test_empty_transcript(self) -> None:
        result = ReviewPhase._extract_criteria("", issue_number=1)
        assert result is None


# ---------------------------------------------------------------------------
# _extract_test_files tests
# ---------------------------------------------------------------------------


class TestExtractTestFiles:
    """Tests for ReviewPhase._extract_test_files."""

    def test_extracts_test_files_from_diff(self) -> None:
        files = ReviewPhase._extract_test_files(SAMPLE_DIFF)
        assert "tests/test_login.py" in files

    def test_returns_empty_for_no_test_files(self) -> None:
        diff = "+++ b/login.py\n+++ b/utils.py"
        files = ReviewPhase._extract_test_files(diff)
        assert files == []

    def test_extracts_multiple_test_files(self) -> None:
        diff = "+++ b/tests/test_login.py\n+++ b/tests/test_auth.py\n+++ b/src/app.py\n"
        files = ReviewPhase._extract_test_files(diff)
        assert len(files) == 2
        assert "tests/test_login.py" in files
        assert "tests/test_auth.py" in files


# ---------------------------------------------------------------------------
# _extract_plan_comment tests
# ---------------------------------------------------------------------------


class TestExtractPlanComment:
    """Tests for ReviewPhase._extract_plan_comment."""

    def test_extracts_plan_from_comments(self) -> None:
        comments = [
            "Great issue!",
            "## Implementation Plan\n\n1. Do X\n2. Do Y",
            "LGTM",
        ]
        result = ReviewPhase._extract_plan_comment(comments)
        assert "## Implementation Plan" in result

    def test_returns_empty_when_no_plan(self) -> None:
        comments = ["Nice work!", "Thanks"]
        result = ReviewPhase._extract_plan_comment(comments)
        assert result == ""

    def test_returns_first_plan_comment(self) -> None:
        comments = [
            "## Implementation Plan\n\nFirst plan",
            "## Implementation Plan\n\nSecond plan",
        ]
        result = ReviewPhase._extract_plan_comment(comments)
        assert "First plan" in result


# ---------------------------------------------------------------------------
# _persist_criteria tests
# ---------------------------------------------------------------------------


class TestPersistCriteria:
    """Tests for ReviewPhase._persist_criteria."""

    def test_creates_verification_dir(self, config: HydraConfig) -> None:
        phase = _make_phase(config)
        criteria = VerificationCriteria(
            issue_number=42,
            criteria=["Login validates email"],
            raw_text="AC-1: Login validates email",
            generated_at="2026-01-01T00:00:00+00:00",
        )
        config.repo_root.mkdir(parents=True, exist_ok=True)

        phase._persist_criteria(criteria)

        verification_dir = config.repo_root / ".hydra" / "verification"
        assert verification_dir.exists()

    def test_writes_markdown_file(self, config: HydraConfig) -> None:
        phase = _make_phase(config)
        criteria = VerificationCriteria(
            issue_number=42,
            criteria=["Login validates email"],
            raw_text="AC-1: Login validates email\n\n1. Open login page",
            generated_at="2026-01-01T00:00:00+00:00",
        )
        config.repo_root.mkdir(parents=True, exist_ok=True)

        phase._persist_criteria(criteria)

        path = config.repo_root / ".hydra" / "verification" / "issue-42.md"
        assert path.exists()
        content = path.read_text()
        assert "AC-1: Login validates email" in content
        assert "Open login page" in content


# ---------------------------------------------------------------------------
# _generate_acceptance_criteria tests
# ---------------------------------------------------------------------------


class TestGenerateAcceptanceCriteria:
    """Tests for ReviewPhase._generate_acceptance_criteria."""

    @pytest.mark.asyncio
    async def test_returns_none_on_subprocess_failure(
        self, config: HydraConfig
    ) -> None:
        phase = _make_phase(config)
        issue = _make_issue()
        pr = _make_pr()

        with patch(
            "review_phase.stream_claude_process",
            new_callable=AsyncMock,
            side_effect=RuntimeError("subprocess failed"),
        ):
            result = await phase._generate_acceptance_criteria(pr, issue, "diff")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_criteria_on_success(self, config: HydraConfig) -> None:
        phase = _make_phase(config)
        issue = _make_issue()
        pr = _make_pr()

        with patch(
            "review_phase.stream_claude_process",
            new_callable=AsyncMock,
            return_value=SAMPLE_TRANSCRIPT,
        ):
            result = await phase._generate_acceptance_criteria(pr, issue, SAMPLE_DIFF)
            assert result is not None
            assert result.issue_number == 42
            assert len(result.criteria) == 3

    @pytest.mark.asyncio
    async def test_returns_none_when_no_markers_in_transcript(
        self, config: HydraConfig
    ) -> None:
        phase = _make_phase(config)
        issue = _make_issue()
        pr = _make_pr()

        with patch(
            "review_phase.stream_claude_process",
            new_callable=AsyncMock,
            return_value=SAMPLE_TRANSCRIPT_NO_MARKERS,
        ):
            result = await phase._generate_acceptance_criteria(pr, issue, "diff")
            assert result is None

    @pytest.mark.asyncio
    async def test_skipped_in_dry_run(self, dry_config: HydraConfig) -> None:
        phase = _make_phase(dry_config)
        issue = _make_issue()
        pr = _make_pr()

        result = await phase._generate_acceptance_criteria(pr, issue, "diff")
        assert result is None

    @pytest.mark.asyncio
    async def test_uses_configured_model(self, config: HydraConfig) -> None:
        phase = _make_phase(config)
        issue = _make_issue()
        pr = _make_pr()

        with patch(
            "review_phase.stream_claude_process",
            new_callable=AsyncMock,
            return_value=SAMPLE_TRANSCRIPT,
        ) as mock_stream:
            await phase._generate_acceptance_criteria(pr, issue, SAMPLE_DIFF)
            call_kwargs = mock_stream.call_args
            cmd = call_kwargs.kwargs["cmd"]
            model_idx = cmd.index("--model")
            assert cmd[model_idx + 1] == "haiku"

    @pytest.mark.asyncio
    async def test_includes_plan_from_comments(self, config: HydraConfig) -> None:
        phase = _make_phase(config)
        issue = _make_issue(comments=["## Implementation Plan\n\n1. Add validation"])
        pr = _make_pr()

        with patch(
            "review_phase.stream_claude_process",
            new_callable=AsyncMock,
            return_value=SAMPLE_TRANSCRIPT,
        ) as mock_stream:
            await phase._generate_acceptance_criteria(pr, issue, SAMPLE_DIFF)
            prompt = mock_stream.call_args.kwargs["prompt"]
            assert "Add validation" in prompt


# ---------------------------------------------------------------------------
# VerificationCriteria model tests
# ---------------------------------------------------------------------------


class TestVerificationCriteriaModel:
    """Tests for the VerificationCriteria Pydantic model."""

    def test_default_values(self) -> None:
        vc = VerificationCriteria(issue_number=1)
        assert vc.issue_number == 1
        assert vc.criteria == []
        assert vc.raw_text == ""
        assert vc.generated_at == ""

    def test_with_all_fields(self) -> None:
        vc = VerificationCriteria(
            issue_number=42,
            criteria=["Login validates", "Error shown"],
            raw_text="AC-1: Login validates\nAC-2: Error shown",
            generated_at="2026-01-01T00:00:00+00:00",
        )
        assert vc.issue_number == 42
        assert len(vc.criteria) == 2
        assert "Login validates" in vc.raw_text
