"""Tests for dx/hydra/models.py."""

from __future__ import annotations

import pytest

# conftest.py already inserts the hydra package directory into sys.path
from models import (
    BatchResult,
    GitHubIssue,
    Phase,
    PRInfo,
    ReviewResult,
    ReviewVerdict,
    WorkerResult,
    WorkerStatus,
)

# ---------------------------------------------------------------------------
# GitHubIssue
# ---------------------------------------------------------------------------


class TestGitHubIssue:
    """Tests for the GitHubIssue model."""

    def test_minimal_instantiation(self) -> None:
        """Should create an issue with only required fields."""
        # Arrange / Act
        issue = GitHubIssue(number=1, title="Fix the bug")

        # Assert
        assert issue.number == 1
        assert issue.title == "Fix the bug"

    def test_body_defaults_to_empty_string(self) -> None:
        # Arrange / Act
        issue = GitHubIssue(number=1, title="t")

        # Assert
        assert issue.body == ""

    def test_labels_defaults_to_empty_list(self) -> None:
        # Arrange / Act
        issue = GitHubIssue(number=1, title="t")

        # Assert
        assert issue.labels == []

    def test_comments_defaults_to_empty_list(self) -> None:
        # Arrange / Act
        issue = GitHubIssue(number=1, title="t")

        # Assert
        assert issue.comments == []

    def test_url_defaults_to_empty_string(self) -> None:
        # Arrange / Act
        issue = GitHubIssue(number=1, title="t")

        # Assert
        assert issue.url == ""

    def test_all_fields_set(self) -> None:
        # Arrange / Act
        issue = GitHubIssue(
            number=42,
            title="Improve widget",
            body="The widget is slow.",
            labels=["ready", "perf"],
            comments=["LGTM", "Needs tests"],
            url="https://github.com/org/repo/issues/42",
        )

        # Assert
        assert issue.number == 42
        assert issue.title == "Improve widget"
        assert issue.body == "The widget is slow."
        assert issue.labels == ["ready", "perf"]
        assert issue.comments == ["LGTM", "Needs tests"]
        assert issue.url == "https://github.com/org/repo/issues/42"

    def test_labels_are_independent_between_instances(self) -> None:
        """Default mutable lists should not be shared between instances."""
        # Arrange
        issue_a = GitHubIssue(number=1, title="a")
        issue_b = GitHubIssue(number=2, title="b")

        # Act
        issue_a.labels.append("ready")

        # Assert
        assert issue_b.labels == []

    def test_serialization_with_model_dump(self) -> None:
        # Arrange
        issue = GitHubIssue(number=5, title="Serialise me", body="body text")

        # Act
        data = issue.model_dump()

        # Assert
        assert data["number"] == 5
        assert data["title"] == "Serialise me"
        assert data["body"] == "body text"
        assert data["labels"] == []
        assert data["comments"] == []
        assert data["url"] == ""


# ---------------------------------------------------------------------------
# WorkerStatus
# ---------------------------------------------------------------------------


class TestWorkerStatus:
    """Tests for the WorkerStatus enum."""

    @pytest.mark.parametrize(
        "member, expected_value",
        [
            (WorkerStatus.QUEUED, "queued"),
            (WorkerStatus.RUNNING, "running"),
            (WorkerStatus.TESTING, "testing"),
            (WorkerStatus.COMMITTING, "committing"),
            (WorkerStatus.DONE, "done"),
            (WorkerStatus.FAILED, "failed"),
        ],
    )
    def test_enum_values(self, member: WorkerStatus, expected_value: str) -> None:
        # Arrange / Act / Assert
        assert member.value == expected_value

    def test_enum_is_string_subclass(self) -> None:
        # Assert
        assert isinstance(WorkerStatus.DONE, str)

    def test_all_six_members_present(self) -> None:
        # Assert
        assert len(WorkerStatus) == 6

    def test_lookup_by_value(self) -> None:
        # Act
        status = WorkerStatus("running")

        # Assert
        assert status is WorkerStatus.RUNNING


# ---------------------------------------------------------------------------
# WorkerResult
# ---------------------------------------------------------------------------


class TestWorkerResult:
    """Tests for the WorkerResult model."""

    def test_minimal_instantiation(self) -> None:
        """Should create a result with only required fields."""
        # Arrange / Act
        result = WorkerResult(issue_number=10, branch="agent/issue-10")

        # Assert
        assert result.issue_number == 10
        assert result.branch == "agent/issue-10"

    def test_worktree_path_defaults_to_empty_string(self) -> None:
        result = WorkerResult(issue_number=1, branch="b")
        assert result.worktree_path == ""

    def test_success_defaults_to_false(self) -> None:
        result = WorkerResult(issue_number=1, branch="b")
        assert result.success is False

    def test_error_defaults_to_none(self) -> None:
        result = WorkerResult(issue_number=1, branch="b")
        assert result.error is None

    def test_transcript_defaults_to_empty_string(self) -> None:
        result = WorkerResult(issue_number=1, branch="b")
        assert result.transcript == ""

    def test_commits_defaults_to_zero(self) -> None:
        result = WorkerResult(issue_number=1, branch="b")
        assert result.commits == 0

    def test_duration_seconds_defaults_to_zero(self) -> None:
        result = WorkerResult(issue_number=1, branch="b")
        assert result.duration_seconds == pytest.approx(0.0)

    def test_all_fields_set(self) -> None:
        # Arrange / Act
        result = WorkerResult(
            issue_number=7,
            branch="agent/issue-7",
            worktree_path="/tmp/wt/issue-7",
            success=True,
            error=None,
            transcript="Done in 3 steps.",
            commits=2,
            duration_seconds=45.3,
        )

        # Assert
        assert result.issue_number == 7
        assert result.branch == "agent/issue-7"
        assert result.worktree_path == "/tmp/wt/issue-7"
        assert result.success is True
        assert result.error is None
        assert result.transcript == "Done in 3 steps."
        assert result.commits == 2
        assert result.duration_seconds == pytest.approx(45.3)

    def test_failed_result_stores_error_message(self) -> None:
        # Arrange / Act
        result = WorkerResult(
            issue_number=99,
            branch="agent/issue-99",
            success=False,
            error="TimeoutError: agent exceeded budget",
        )

        # Assert
        assert result.success is False
        assert result.error == "TimeoutError: agent exceeded budget"

    def test_serialization_with_model_dump(self) -> None:
        # Arrange
        result = WorkerResult(
            issue_number=3, branch="agent/issue-3", commits=1, success=True
        )

        # Act
        data = result.model_dump()

        # Assert
        assert data["issue_number"] == 3
        assert data["branch"] == "agent/issue-3"
        assert data["commits"] == 1
        assert data["success"] is True


# ---------------------------------------------------------------------------
# PRInfo
# ---------------------------------------------------------------------------


class TestPRInfo:
    """Tests for the PRInfo model."""

    def test_minimal_instantiation(self) -> None:
        # Arrange / Act
        pr = PRInfo(number=101, issue_number=42, branch="agent/issue-42")

        # Assert
        assert pr.number == 101
        assert pr.issue_number == 42
        assert pr.branch == "agent/issue-42"

    def test_url_defaults_to_empty_string(self) -> None:
        pr = PRInfo(number=1, issue_number=1, branch="b")
        assert pr.url == ""

    def test_draft_defaults_to_false(self) -> None:
        pr = PRInfo(number=1, issue_number=1, branch="b")
        assert pr.draft is False

    def test_all_fields_set(self) -> None:
        # Arrange / Act
        pr = PRInfo(
            number=200,
            issue_number=55,
            branch="agent/issue-55",
            url="https://github.com/org/repo/pull/200",
            draft=True,
        )

        # Assert
        assert pr.number == 200
        assert pr.issue_number == 55
        assert pr.branch == "agent/issue-55"
        assert pr.url == "https://github.com/org/repo/pull/200"
        assert pr.draft is True

    def test_serialization_with_model_dump(self) -> None:
        # Arrange
        pr = PRInfo(
            number=5,
            issue_number=3,
            branch="agent/issue-3",
            url="https://example.com/pr/5",
        )

        # Act
        data = pr.model_dump()

        # Assert
        assert data["number"] == 5
        assert data["issue_number"] == 3
        assert data["branch"] == "agent/issue-3"
        assert data["url"] == "https://example.com/pr/5"
        assert data["draft"] is False


# ---------------------------------------------------------------------------
# ReviewVerdict
# ---------------------------------------------------------------------------


class TestReviewVerdict:
    """Tests for the ReviewVerdict enum."""

    @pytest.mark.parametrize(
        "member, expected_value",
        [
            (ReviewVerdict.APPROVE, "approve"),
            (ReviewVerdict.REQUEST_CHANGES, "request-changes"),
            (ReviewVerdict.COMMENT, "comment"),
        ],
    )
    def test_enum_values(self, member: ReviewVerdict, expected_value: str) -> None:
        # Assert
        assert member.value == expected_value

    def test_enum_is_string_subclass(self) -> None:
        assert isinstance(ReviewVerdict.APPROVE, str)

    def test_all_three_members_present(self) -> None:
        assert len(ReviewVerdict) == 3

    def test_lookup_by_value(self) -> None:
        verdict = ReviewVerdict("approve")
        assert verdict is ReviewVerdict.APPROVE

    def test_request_changes_value_with_hyphen(self) -> None:
        """Value uses a hyphen to match the GitHub API string."""
        assert ReviewVerdict.REQUEST_CHANGES.value == "request-changes"


# ---------------------------------------------------------------------------
# ReviewResult
# ---------------------------------------------------------------------------


class TestReviewResult:
    """Tests for the ReviewResult model."""

    def test_minimal_instantiation(self) -> None:
        # Arrange / Act
        review = ReviewResult(pr_number=10, issue_number=5)

        # Assert
        assert review.pr_number == 10
        assert review.issue_number == 5

    def test_verdict_defaults_to_comment(self) -> None:
        review = ReviewResult(pr_number=1, issue_number=1)
        assert review.verdict is ReviewVerdict.COMMENT

    def test_summary_defaults_to_empty_string(self) -> None:
        review = ReviewResult(pr_number=1, issue_number=1)
        assert review.summary == ""

    def test_fixes_made_defaults_to_false(self) -> None:
        review = ReviewResult(pr_number=1, issue_number=1)
        assert review.fixes_made is False

    def test_transcript_defaults_to_empty_string(self) -> None:
        review = ReviewResult(pr_number=1, issue_number=1)
        assert review.transcript == ""

    def test_all_fields_set(self) -> None:
        # Arrange / Act
        review = ReviewResult(
            pr_number=77,
            issue_number=33,
            verdict=ReviewVerdict.APPROVE,
            summary="Looks great!",
            fixes_made=True,
            transcript="Reviewed 5 files.",
        )

        # Assert
        assert review.pr_number == 77
        assert review.issue_number == 33
        assert review.verdict is ReviewVerdict.APPROVE
        assert review.summary == "Looks great!"
        assert review.fixes_made is True
        assert review.transcript == "Reviewed 5 files."

    def test_request_changes_verdict(self) -> None:
        review = ReviewResult(
            pr_number=2, issue_number=2, verdict=ReviewVerdict.REQUEST_CHANGES
        )
        assert review.verdict is ReviewVerdict.REQUEST_CHANGES

    def test_serialization_with_model_dump(self) -> None:
        # Arrange
        review = ReviewResult(
            pr_number=8, issue_number=4, verdict=ReviewVerdict.APPROVE, summary="LGTM"
        )

        # Act
        data = review.model_dump()

        # Assert
        assert data["pr_number"] == 8
        assert data["issue_number"] == 4
        assert data["verdict"] == ReviewVerdict.APPROVE
        assert data["summary"] == "LGTM"
        assert data["fixes_made"] is False


# ---------------------------------------------------------------------------
# BatchResult
# ---------------------------------------------------------------------------


class TestBatchResult:
    """Tests for the BatchResult model."""

    def test_minimal_instantiation(self) -> None:
        # Arrange / Act
        batch = BatchResult(batch_number=1)

        # Assert
        assert batch.batch_number == 1

    def test_issues_defaults_to_empty_list(self) -> None:
        batch = BatchResult(batch_number=1)
        assert batch.issues == []

    def test_worker_results_defaults_to_empty_list(self) -> None:
        batch = BatchResult(batch_number=1)
        assert batch.worker_results == []

    def test_pr_infos_defaults_to_empty_list(self) -> None:
        batch = BatchResult(batch_number=1)
        assert batch.pr_infos == []

    def test_review_results_defaults_to_empty_list(self) -> None:
        batch = BatchResult(batch_number=1)
        assert batch.review_results == []

    def test_merged_prs_defaults_to_empty_list(self) -> None:
        batch = BatchResult(batch_number=1)
        assert batch.merged_prs == []

    def test_lists_are_independent_between_instances(self) -> None:
        """Default mutable lists must not be shared between BatchResult instances."""
        # Arrange
        batch_a = BatchResult(batch_number=1)
        batch_b = BatchResult(batch_number=2)

        # Act
        batch_a.merged_prs.append(99)

        # Assert
        assert batch_b.merged_prs == []

    def test_populated_batch_result(self) -> None:
        """Should hold multiple issues, worker results, PRs, reviews, and merged PR numbers."""
        # Arrange
        issues = [
            GitHubIssue(number=1, title="Issue 1"),
            GitHubIssue(number=2, title="Issue 2"),
        ]
        worker_results = [
            WorkerResult(
                issue_number=1, branch="agent/issue-1", success=True, commits=1
            ),
            WorkerResult(
                issue_number=2, branch="agent/issue-2", success=False, error="timeout"
            ),
        ]
        pr_infos = [
            PRInfo(number=100, issue_number=1, branch="agent/issue-1"),
        ]
        review_results = [
            ReviewResult(pr_number=100, issue_number=1, verdict=ReviewVerdict.APPROVE),
        ]
        merged_prs = [100]

        # Act
        batch = BatchResult(
            batch_number=3,
            issues=issues,
            worker_results=worker_results,
            pr_infos=pr_infos,
            review_results=review_results,
            merged_prs=merged_prs,
        )

        # Assert
        assert batch.batch_number == 3
        assert len(batch.issues) == 2
        assert batch.issues[0].number == 1
        assert batch.issues[1].number == 2
        assert len(batch.worker_results) == 2
        assert batch.worker_results[0].success is True
        assert batch.worker_results[1].success is False
        assert len(batch.pr_infos) == 1
        assert batch.pr_infos[0].number == 100
        assert len(batch.review_results) == 1
        assert batch.review_results[0].verdict is ReviewVerdict.APPROVE
        assert batch.merged_prs == [100]

    def test_serialization_with_model_dump(self) -> None:
        # Arrange
        batch = BatchResult(
            batch_number=2,
            issues=[GitHubIssue(number=10, title="T")],
            merged_prs=[200, 201],
        )

        # Act
        data = batch.model_dump()

        # Assert
        assert data["batch_number"] == 2
        assert len(data["issues"]) == 1
        assert data["issues"][0]["number"] == 10
        assert data["merged_prs"] == [200, 201]
        assert data["worker_results"] == []
        assert data["pr_infos"] == []
        assert data["review_results"] == []

    def test_successful_worker_count_via_list_comprehension(self) -> None:
        """BatchResult does not have a built-in aggregation method, but its data should support it."""
        # Arrange
        batch = BatchResult(
            batch_number=1,
            worker_results=[
                WorkerResult(issue_number=1, branch="b1", success=True),
                WorkerResult(issue_number=2, branch="b2", success=False),
                WorkerResult(issue_number=3, branch="b3", success=True),
            ],
        )

        # Act
        successful = [r for r in batch.worker_results if r.success]

        # Assert
        assert len(successful) == 2


# ---------------------------------------------------------------------------
# Phase
# ---------------------------------------------------------------------------


class TestPhase:
    """Tests for the Phase enum."""

    @pytest.mark.parametrize(
        "member, expected_value",
        [
            (Phase.FETCH, "fetch"),
            (Phase.IMPLEMENT, "implement"),
            (Phase.PUSH_PRS, "push_prs"),
            (Phase.REVIEW, "review"),
            (Phase.MERGE, "merge"),
            (Phase.CLEANUP, "cleanup"),
            (Phase.DONE, "done"),
        ],
    )
    def test_enum_values(self, member: Phase, expected_value: str) -> None:
        # Assert
        assert member.value == expected_value

    def test_enum_is_string_subclass(self) -> None:
        assert isinstance(Phase.FETCH, str)

    def test_all_seven_members_present(self) -> None:
        assert len(Phase) == 7

    def test_lookup_by_value(self) -> None:
        phase = Phase("implement")
        assert phase is Phase.IMPLEMENT

    def test_done_is_terminal_phase(self) -> None:
        """DONE should be the last declared phase."""
        members = list(Phase)
        assert members[-1] is Phase.DONE
