"""Tests for dx/hydra/pr_manager.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import AsyncMock, patch

import pytest

from events import EventType
from pr_manager import PRManager

# ---------------------------------------------------------------------------
# _chunk_body (static method)
# ---------------------------------------------------------------------------


class TestChunkBody:
    """Tests for PRManager._chunk_body."""

    def test_short_body_returns_single_chunk(self):
        result = PRManager._chunk_body("hello world", limit=100)
        assert result == ["hello world"]

    def test_body_at_limit_returns_single_chunk(self):
        body = "x" * 100
        result = PRManager._chunk_body(body, limit=100)
        assert result == [body]

    def test_body_splits_at_newline(self):
        body = "line1\nline2\nline3"
        result = PRManager._chunk_body(body, limit=12)
        assert len(result) == 2
        assert result[0] == "line1\nline2"
        assert result[1] == "line3"

    def test_body_splits_without_newline(self):
        body = "a" * 200
        result = PRManager._chunk_body(body, limit=100)
        assert len(result) == 2
        assert result[0] == "a" * 100
        assert result[1] == "a" * 100

    def test_empty_body_returns_single_chunk(self):
        result = PRManager._chunk_body("", limit=100)
        assert result == [""]


# ---------------------------------------------------------------------------
# _cap_body (class method)
# ---------------------------------------------------------------------------


class TestCapBody:
    """Tests for PRManager._cap_body."""

    def test_short_body_unchanged(self):
        result = PRManager._cap_body("hello", limit=100)
        assert result == "hello"

    def test_body_at_limit_unchanged(self):
        body = "x" * 100
        result = PRManager._cap_body(body, limit=100)
        assert result == body

    def test_body_over_limit_truncated_with_marker(self):
        body = "x" * 200
        result = PRManager._cap_body(body, limit=100)
        assert len(result) == 100
        assert result.endswith(PRManager._TRUNCATION_MARKER)

    def test_truncated_body_contains_original_prefix(self):
        body = "ABCDEF" * 20_000
        result = PRManager._cap_body(body, limit=1000)
        marker_len = len(PRManager._TRUNCATION_MARKER)
        assert result[: 1000 - marker_len] == body[: 1000 - marker_len]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manager(config, event_bus):
    return PRManager(config=config, event_bus=event_bus)


def _make_subprocess_mock(returncode: int = 0, stdout: str = "", stderr: str = ""):
    """Build a mock for asyncio.create_subprocess_exec."""
    mock_proc = AsyncMock()
    mock_proc.returncode = returncode
    mock_proc.communicate = AsyncMock(return_value=(stdout.encode(), stderr.encode()))
    mock_proc.wait = AsyncMock(return_value=returncode)
    return AsyncMock(return_value=mock_proc)


# ---------------------------------------------------------------------------
# post_comment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_comment_calls_gh_issue_comment(config, event_bus, tmp_path):
    """post_comment should call gh issue comment with --body-file."""
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        await mgr.post_comment(42, "This is a plan comment")

    mock_create.assert_awaited_once()
    call_args = mock_create.call_args
    cmd = call_args.args if call_args.args else call_args[0]
    assert "gh" in cmd
    assert "issue" in cmd
    assert "comment" in cmd
    assert "42" in cmd
    assert "--body-file" in cmd
    # Body should NOT be passed inline
    assert "This is a plan comment" not in cmd


@pytest.mark.asyncio
async def test_post_comment_dry_run(dry_config, event_bus):
    """In dry-run mode, post_comment should not call subprocess."""
    mgr = _make_manager(dry_config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        await mgr.post_comment(42, "This is a plan comment")

    mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_post_comment_handles_error(config, event_bus, tmp_path):
    """post_comment should log warning on failure without raising."""
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=1, stderr="permission denied")

    with patch("asyncio.create_subprocess_exec", mock_create):
        # Should not raise
        await mgr.post_comment(42, "comment body")


# ---------------------------------------------------------------------------
# post_pr_comment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_pr_comment_calls_gh_pr_comment(config, event_bus, tmp_path):
    """post_pr_comment should call gh pr comment with --body-file."""
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        await mgr.post_pr_comment(101, "Review summary here")

    mock_create.assert_awaited_once()
    call_args = mock_create.call_args
    cmd = call_args.args if call_args.args else call_args[0]
    assert "gh" in cmd
    assert "pr" in cmd
    assert "comment" in cmd
    assert "101" in cmd
    assert "--body-file" in cmd
    assert "Review summary here" not in cmd


@pytest.mark.asyncio
async def test_post_pr_comment_dry_run(dry_config, event_bus):
    """In dry-run mode, post_pr_comment should not call subprocess."""
    mgr = _make_manager(dry_config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        await mgr.post_pr_comment(101, "Review summary here")

    mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_post_pr_comment_handles_error(config, event_bus, tmp_path):
    """post_pr_comment should log warning on failure without raising."""
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=1, stderr="permission denied")

    with patch("asyncio.create_subprocess_exec", mock_create):
        # Should not raise
        await mgr.post_pr_comment(101, "comment body")


# ---------------------------------------------------------------------------
# submit_review
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_review_approve_calls_correct_flag(config, event_bus, tmp_path):
    """submit_review with 'approve' should pass --approve flag and --body-file."""
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await mgr.submit_review(101, "approve", "Looks good")

    assert result is True
    cmd = (
        mock_create.call_args.args
        if mock_create.call_args.args
        else mock_create.call_args[0]
    )
    assert "gh" in cmd
    assert "pr" in cmd
    assert "review" in cmd
    assert "101" in cmd
    assert "--approve" in cmd
    assert "--body-file" in cmd
    assert "Looks good" not in cmd


@pytest.mark.asyncio
async def test_submit_review_request_changes_calls_correct_flag(
    config, event_bus, tmp_path
):
    """submit_review with 'request-changes' should pass --request-changes."""
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await mgr.submit_review(101, "request-changes", "Needs work")

    assert result is True
    cmd = (
        mock_create.call_args.args
        if mock_create.call_args.args
        else mock_create.call_args[0]
    )
    assert "--request-changes" in cmd


@pytest.mark.asyncio
async def test_submit_review_comment_calls_correct_flag(config, event_bus, tmp_path):
    """submit_review with 'comment' should pass --comment."""
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await mgr.submit_review(101, "comment", "FYI note")

    assert result is True
    cmd = (
        mock_create.call_args.args
        if mock_create.call_args.args
        else mock_create.call_args[0]
    )
    assert "--comment" in cmd


@pytest.mark.asyncio
async def test_submit_review_dry_run(dry_config, event_bus):
    """In dry-run mode, submit_review should not call subprocess."""
    mgr = _make_manager(dry_config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await mgr.submit_review(101, "approve", "LGTM")

    mock_create.assert_not_called()
    assert result is True


@pytest.mark.asyncio
async def test_submit_review_failure_returns_false(config, event_bus, tmp_path):
    """submit_review should return False on subprocess failure."""
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=1, stderr="review failed")

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await mgr.submit_review(101, "approve", "LGTM")

    assert result is False


@pytest.mark.asyncio
async def test_submit_review_unknown_verdict_returns_false(config, event_bus):
    """submit_review with invalid verdict should return False without calling subprocess."""
    mgr = _make_manager(config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await mgr.submit_review(101, "invalid-verdict", "body")

    assert result is False
    mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# create_issue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_issue_calls_gh_issue_create(config, event_bus, tmp_path):
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    issue_url = "https://github.com/test-org/test-repo/issues/99"
    mock_create = _make_subprocess_mock(returncode=0, stdout=issue_url)

    with patch("asyncio.create_subprocess_exec", mock_create):
        number = await mgr.create_issue("Bug found", "Details here", ["bug"])

    assert number == 99
    args = mock_create.call_args[0]
    assert "gh" in args
    assert "issue" in args
    assert "create" in args
    assert "--title" in args
    assert "Bug found" in args
    assert "--label" in args
    assert "bug" in args


@pytest.mark.asyncio
async def test_create_issue_publishes_event(config, event_bus, tmp_path):
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    issue_url = "https://github.com/test-org/test-repo/issues/55"
    mock_create = _make_subprocess_mock(returncode=0, stdout=issue_url)

    with patch("asyncio.create_subprocess_exec", mock_create):
        await mgr.create_issue("Tech debt", "Needs refactor", ["tech-debt"])

    events = event_bus.get_history()
    from events import EventType

    issue_events = [e for e in events if e.type == EventType.ISSUE_CREATED]
    assert len(issue_events) == 1
    assert issue_events[0].data["number"] == 55
    assert issue_events[0].data["title"] == "Tech debt"


@pytest.mark.asyncio
async def test_create_issue_dry_run(dry_config, event_bus):
    mgr = _make_manager(dry_config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0)

    with patch("asyncio.create_subprocess_exec", mock_create):
        number = await mgr.create_issue("Bug", "Details")

    mock_create.assert_not_called()
    assert number == 0


@pytest.mark.asyncio
async def test_create_issue_failure_returns_zero(config, event_bus, tmp_path):
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=1, stderr="permission denied")

    with patch("asyncio.create_subprocess_exec", mock_create):
        number = await mgr.create_issue("Bug", "Details")

    assert number == 0


@pytest.mark.asyncio
async def test_create_issue_no_labels(config, event_bus, tmp_path):
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    issue_url = "https://github.com/test-org/test-repo/issues/10"
    mock_create = _make_subprocess_mock(returncode=0, stdout=issue_url)

    with patch("asyncio.create_subprocess_exec", mock_create):
        number = await mgr.create_issue("Bug", "Details")

    assert number == 10
    args = mock_create.call_args[0]
    assert "--label" not in args


# ---------------------------------------------------------------------------
# push_branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_push_branch_calls_git_push(config, event_bus, tmp_path):
    manager = _make_manager(config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await manager.push_branch(tmp_path, "agent/issue-42")

    assert result is True
    args = mock_create.call_args[0]
    assert args[0] == "git"
    assert args[1] == "push"
    assert "--no-verify" in args
    assert "-u" in args
    assert "origin" in args
    assert "agent/issue-42" in args


# ---------------------------------------------------------------------------
# remote_branch_exists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remote_branch_exists_returns_true_when_found(
    config, event_bus, tmp_path
):
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    manager = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(
        returncode=0, stdout="abc123\trefs/heads/agent/issue-42"
    )

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await manager.remote_branch_exists("agent/issue-42")

    assert result is True
    args = mock_create.call_args[0]
    assert "ls-remote" in args
    assert "--heads" in args
    assert "agent/issue-42" in args


@pytest.mark.asyncio
async def test_remote_branch_exists_returns_false_when_not_found(
    config, event_bus, tmp_path
):
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    manager = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await manager.remote_branch_exists("agent/issue-99")

    assert result is False


@pytest.mark.asyncio
async def test_remote_branch_exists_returns_false_on_error(config, event_bus, tmp_path):
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    manager = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=1, stderr="fatal: network error")

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await manager.remote_branch_exists("agent/issue-42")

    assert result is False


@pytest.mark.asyncio
async def test_remote_branch_exists_dry_run_returns_false(dry_config, event_bus):
    manager = _make_manager(dry_config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0)

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await manager.remote_branch_exists("agent/issue-42")

    mock_create.assert_not_called()
    assert result is False


@pytest.mark.asyncio
async def test_push_branch_failure_returns_false(config, event_bus, tmp_path):
    manager = _make_manager(config, event_bus)
    mock_create = _make_subprocess_mock(returncode=1, stderr="error: failed to push")

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await manager.push_branch(tmp_path, "agent/issue-99")

    assert result is False


# ---------------------------------------------------------------------------
# create_pr
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_pr_constructs_correct_gh_command(config, event_bus, issue):
    manager = _make_manager(config, event_bus)
    pr_url = "https://github.com/test-org/test-repo/pull/55"
    mock_create = _make_subprocess_mock(returncode=0, stdout=pr_url)

    with patch("asyncio.create_subprocess_exec", mock_create):
        await manager.create_pr(issue, "agent/issue-42")

    args = mock_create.call_args[0]
    assert args[0] == "gh"
    assert "pr" in args
    assert "create" in args
    assert "--repo" in args
    assert config.repo in args
    assert "--head" in args
    assert "agent/issue-42" in args
    assert "--title" in args
    assert "--body-file" in args


@pytest.mark.asyncio
async def test_create_pr_parses_pr_number_from_url(config, event_bus, issue):
    manager = _make_manager(config, event_bus)
    pr_url = "https://github.com/test-org/test-repo/pull/123"
    mock_create = _make_subprocess_mock(returncode=0, stdout=pr_url)

    with patch("asyncio.create_subprocess_exec", mock_create):
        pr_info = await manager.create_pr(issue, "agent/issue-42")

    assert pr_info.number == 123
    assert pr_info.url == pr_url
    assert pr_info.issue_number == issue.number
    assert pr_info.branch == "agent/issue-42"


@pytest.mark.asyncio
async def test_create_pr_with_draft_flag(config, event_bus, issue):
    manager = _make_manager(config, event_bus)
    pr_url = "https://github.com/test-org/test-repo/pull/77"
    mock_create = _make_subprocess_mock(returncode=0, stdout=pr_url)

    with patch("asyncio.create_subprocess_exec", mock_create):
        pr_info = await manager.create_pr(issue, "agent/issue-42", draft=True)

    args = mock_create.call_args[0]
    assert "--draft" in args
    assert pr_info.draft is True


@pytest.mark.asyncio
async def test_create_pr_title_not_truncated_when_short(config, event_bus):
    from models import GitHubIssue

    short_issue = GitHubIssue(
        number=1,
        title="Fix it",
        body="Short issue",
        labels=["ready"],
        url="https://github.com/test-org/test-repo/issues/1",
    )
    manager = _make_manager(config, event_bus)
    pr_url = "https://github.com/test-org/test-repo/pull/10"
    mock_create = _make_subprocess_mock(returncode=0, stdout=pr_url)

    with patch("asyncio.create_subprocess_exec", mock_create):
        await manager.create_pr(short_issue, "agent/issue-1")

    args = mock_create.call_args[0]
    title_idx = list(args).index("--title") + 1
    title = args[title_idx]
    # "Fixes #1: Fix it" is well under 70 chars
    assert len(title) <= 70
    assert "Fix it" in title
    assert not title.endswith("...")


@pytest.mark.asyncio
async def test_create_pr_title_truncated_at_70_chars(config, event_bus):
    from models import GitHubIssue

    long_title = "A" * 80
    long_issue = GitHubIssue(
        number=99,
        title=long_title,
        body="Some body text",
        labels=["ready"],
        url="https://github.com/test-org/test-repo/issues/99",
    )
    manager = _make_manager(config, event_bus)
    pr_url = "https://github.com/test-org/test-repo/pull/200"
    mock_create = _make_subprocess_mock(returncode=0, stdout=pr_url)

    with patch("asyncio.create_subprocess_exec", mock_create):
        await manager.create_pr(long_issue, "agent/issue-99")

    args = mock_create.call_args[0]
    title_idx = list(args).index("--title") + 1
    title = args[title_idx]
    assert len(title) <= 70
    assert title.endswith("...")


@pytest.mark.asyncio
async def test_create_pr_failure_returns_pr_info_with_number_zero(
    config, event_bus, issue
):
    manager = _make_manager(config, event_bus)
    mock_create = _make_subprocess_mock(returncode=1, stderr="gh: error")

    with patch("asyncio.create_subprocess_exec", mock_create):
        pr_info = await manager.create_pr(issue, "agent/issue-42")

    assert pr_info.number == 0
    assert pr_info.issue_number == issue.number
    assert pr_info.branch == "agent/issue-42"


@pytest.mark.asyncio
async def test_create_pr_publishes_pr_created_event(config, event_bus, issue):
    manager = _make_manager(config, event_bus)
    pr_url = "https://github.com/test-org/test-repo/pull/55"
    mock_create = _make_subprocess_mock(returncode=0, stdout=pr_url)

    with patch("asyncio.create_subprocess_exec", mock_create):
        await manager.create_pr(issue, "agent/issue-42")

    events = event_bus.get_history()
    pr_created_events = [e for e in events if e.type == EventType.PR_CREATED]
    assert len(pr_created_events) == 1
    event_data = pr_created_events[0].data
    assert event_data["pr"] == 55
    assert event_data["issue"] == issue.number
    assert event_data["branch"] == "agent/issue-42"
    assert event_data["url"] == pr_url


@pytest.mark.asyncio
async def test_create_pr_dry_run_skips_command(dry_config, event_bus, issue):
    manager = _make_manager(dry_config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        pr_info = await manager.create_pr(issue, "agent/issue-42")

    mock_create.assert_not_called()
    assert pr_info.number == 0
    assert pr_info.issue_number == issue.number


# ---------------------------------------------------------------------------
# merge_pr
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_merge_pr_calls_gh_pr_merge_with_correct_flags(config, event_bus):
    manager = _make_manager(config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await manager.merge_pr(101)

    assert result is True
    args = mock_create.call_args[0]
    assert args[0] == "gh"
    assert "pr" in args
    assert "merge" in args
    assert "101" in args
    assert "--squash" in args
    assert "--auto" not in args
    assert "--delete-branch" in args


@pytest.mark.asyncio
async def test_merge_pr_failure_returns_false(config, event_bus):
    manager = _make_manager(config, event_bus)
    mock_create = _make_subprocess_mock(returncode=1, stderr="merge failed")

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await manager.merge_pr(101)

    assert result is False


@pytest.mark.asyncio
async def test_merge_pr_dry_run_skips_command(dry_config, event_bus):
    manager = _make_manager(dry_config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0)

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await manager.merge_pr(101)

    mock_create.assert_not_called()
    assert result is True


# ---------------------------------------------------------------------------
# add_labels
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_labels_calls_gh_issue_edit_for_each_label(config, event_bus):
    manager = _make_manager(config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        await manager.add_labels(42, ["bug", "enhancement"])

    assert mock_create.call_count == 2

    first_args = mock_create.call_args_list[0][0]
    assert first_args[0] == "gh"
    assert "issue" in first_args
    assert "edit" in first_args
    assert "--add-label" in first_args

    second_args = mock_create.call_args_list[1][0]
    assert "--add-label" in second_args


@pytest.mark.asyncio
async def test_add_labels_dry_run_skips_command(dry_config, event_bus):
    manager = _make_manager(dry_config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0)

    with patch("asyncio.create_subprocess_exec", mock_create):
        await manager.add_labels(42, ["bug"])

    mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_add_labels_empty_list_skips_command(config, event_bus):
    manager = _make_manager(config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0)

    with patch("asyncio.create_subprocess_exec", mock_create):
        await manager.add_labels(42, [])

    mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# remove_label
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_label_calls_gh_issue_edit(config, event_bus):
    manager = _make_manager(config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        await manager.remove_label(42, "ready")

    assert mock_create.call_count == 1
    args = mock_create.call_args[0]
    assert args[0] == "gh"
    assert "issue" in args
    assert "edit" in args
    assert "42" in args
    assert "--remove-label" in args
    assert "ready" in args


@pytest.mark.asyncio
async def test_remove_label_dry_run_skips_command(dry_config, event_bus):
    manager = _make_manager(dry_config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0)

    with patch("asyncio.create_subprocess_exec", mock_create):
        await manager.remove_label(42, "ready")

    mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# get_pr_diff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pr_diff_returns_diff_content(config, event_bus):
    manager = _make_manager(config, event_bus)
    expected_diff = "diff --git a/foo.py b/foo.py\n+added line"
    mock_create = _make_subprocess_mock(returncode=0, stdout=expected_diff)

    with patch("asyncio.create_subprocess_exec", mock_create):
        diff = await manager.get_pr_diff(101)

    assert diff == expected_diff

    args = mock_create.call_args[0]
    assert args[0] == "gh"
    assert "pr" in args
    assert "diff" in args
    assert "101" in args


@pytest.mark.asyncio
async def test_get_pr_diff_failure_returns_empty_string(config, event_bus):
    manager = _make_manager(config, event_bus)
    mock_create = _make_subprocess_mock(returncode=1, stderr="not found")

    with patch("asyncio.create_subprocess_exec", mock_create):
        diff = await manager.get_pr_diff(999)

    assert diff == ""


# ---------------------------------------------------------------------------
# get_pr_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pr_status_returns_parsed_json(config, event_bus):
    manager = _make_manager(config, event_bus)
    status_json = '{"number": 101, "state": "OPEN", "mergeable": "MERGEABLE", "title": "Fix bug", "isDraft": false}'
    mock_create = _make_subprocess_mock(returncode=0, stdout=status_json)

    with patch("asyncio.create_subprocess_exec", mock_create):
        status = await manager.get_pr_status(101)

    assert status["number"] == 101
    assert status["state"] == "OPEN"
    assert status["isDraft"] is False


@pytest.mark.asyncio
async def test_get_pr_status_failure_returns_empty_dict(config, event_bus):
    manager = _make_manager(config, event_bus)
    mock_create = _make_subprocess_mock(returncode=1, stderr="not found")

    with patch("asyncio.create_subprocess_exec", mock_create):
        status = await manager.get_pr_status(999)

    assert status == {}


# ---------------------------------------------------------------------------
# pull_main
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pull_main_calls_git_pull(config, event_bus):
    manager = _make_manager(config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="Already up to date.")

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await manager.pull_main()

    assert result is True
    args = mock_create.call_args[0]
    assert args[0] == "git"
    assert args[1] == "pull"
    assert "origin" in args
    assert config.main_branch in args


@pytest.mark.asyncio
async def test_pull_main_failure_returns_false(config, event_bus):
    manager = _make_manager(config, event_bus)
    mock_create = _make_subprocess_mock(returncode=1, stderr="fatal: pull failed")

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await manager.pull_main()

    assert result is False


@pytest.mark.asyncio
async def test_pull_main_dry_run_skips_command(dry_config, event_bus):
    manager = _make_manager(dry_config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0)

    with patch("asyncio.create_subprocess_exec", mock_create):
        result = await manager.pull_main()

    mock_create.assert_not_called()
    assert result is True


# NOTE: Tests for the subprocess helper (stdout parsing, error handling,
# GH_TOKEN injection, CLAUDECODE stripping) are now in test_subprocess_util.py
# since the logic was extracted into subprocess_util.run_subprocess.


# ---------------------------------------------------------------------------
# get_pr_checks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pr_checks_returns_parsed_json(config, event_bus, tmp_path):
    """get_pr_checks should return parsed check results."""
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    checks_json = '[{"name":"ci","state":"COMPLETED","conclusion":"SUCCESS"}]'
    mock_create = _make_subprocess_mock(returncode=0, stdout=checks_json)

    with patch("asyncio.create_subprocess_exec", mock_create):
        checks = await mgr.get_pr_checks(101)

    assert len(checks) == 1
    assert checks[0]["name"] == "ci"
    assert checks[0]["conclusion"] == "SUCCESS"


@pytest.mark.asyncio
async def test_get_pr_checks_returns_empty_on_failure(config, event_bus, tmp_path):
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=1, stderr="not found")

    with patch("asyncio.create_subprocess_exec", mock_create):
        checks = await mgr.get_pr_checks(999)

    assert checks == []


@pytest.mark.asyncio
async def test_get_pr_checks_dry_run_returns_empty(dry_config, event_bus):
    mgr = _make_manager(dry_config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0)

    with patch("asyncio.create_subprocess_exec", mock_create):
        checks = await mgr.get_pr_checks(101)

    mock_create.assert_not_called()
    assert checks == []


# ---------------------------------------------------------------------------
# wait_for_ci
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wait_for_ci_passes_when_all_succeed(config, event_bus, tmp_path):
    """wait_for_ci should return (True, ...) when all checks pass."""
    import asyncio

    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    stop = asyncio.Event()

    checks = [
        {"name": "ci", "state": "COMPLETED", "conclusion": "SUCCESS"},
        {"name": "lint", "state": "COMPLETED", "conclusion": "SUCCESS"},
    ]
    mgr.get_pr_checks = AsyncMock(return_value=checks)

    passed, summary = await mgr.wait_for_ci(
        101, timeout=60, poll_interval=5, stop_event=stop
    )

    assert passed is True
    assert "2 checks passed" in summary


@pytest.mark.asyncio
async def test_wait_for_ci_fails_on_failure(config, event_bus, tmp_path):
    """wait_for_ci should return (False, ...) when checks fail."""
    import asyncio

    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    stop = asyncio.Event()

    checks = [
        {"name": "ci", "state": "COMPLETED", "conclusion": "FAILURE"},
        {"name": "lint", "state": "COMPLETED", "conclusion": "SUCCESS"},
    ]
    mgr.get_pr_checks = AsyncMock(return_value=checks)

    passed, summary = await mgr.wait_for_ci(
        101, timeout=60, poll_interval=5, stop_event=stop
    )

    assert passed is False
    assert "ci" in summary


@pytest.mark.asyncio
async def test_wait_for_ci_passes_when_no_checks(config, event_bus, tmp_path):
    """wait_for_ci should return (True, ...) when no CI checks exist."""
    import asyncio

    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    stop = asyncio.Event()

    mgr.get_pr_checks = AsyncMock(return_value=[])

    passed, summary = await mgr.wait_for_ci(
        101, timeout=60, poll_interval=5, stop_event=stop
    )

    assert passed is True
    assert "No CI checks found" in summary


@pytest.mark.asyncio
async def test_wait_for_ci_respects_stop_event(config, event_bus, tmp_path):
    """wait_for_ci should return (False, 'Stopped') when stop_event is set."""
    import asyncio

    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    stop = asyncio.Event()
    stop.set()  # Already stopped

    passed, summary = await mgr.wait_for_ci(
        101, timeout=60, poll_interval=5, stop_event=stop
    )

    assert passed is False
    assert summary == "Stopped"


@pytest.mark.asyncio
async def test_wait_for_ci_dry_run_returns_success(dry_config, event_bus):
    """In dry-run mode, wait_for_ci should return (True, ...)."""
    import asyncio

    mgr = _make_manager(dry_config, event_bus)
    stop = asyncio.Event()

    passed, summary = await mgr.wait_for_ci(
        101, timeout=60, poll_interval=5, stop_event=stop
    )

    assert passed is True
    assert "Dry-run" in summary


@pytest.mark.asyncio
async def test_wait_for_ci_already_complete_returns_immediately(
    config, event_bus, tmp_path
):
    """When checks are already complete, should return without sleeping."""
    import asyncio

    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    stop = asyncio.Event()

    checks = [{"name": "ci", "state": "COMPLETED", "conclusion": "SUCCESS"}]
    mgr.get_pr_checks = AsyncMock(return_value=checks)

    passed, _ = await mgr.wait_for_ci(101, timeout=60, poll_interval=5, stop_event=stop)

    assert passed is True
    mgr.get_pr_checks.assert_awaited_once()


@pytest.mark.asyncio
async def test_wait_for_ci_publishes_ci_check_events(config, event_bus, tmp_path):
    """wait_for_ci should publish CI_CHECK events."""
    import asyncio

    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    stop = asyncio.Event()

    checks = [{"name": "ci", "state": "COMPLETED", "conclusion": "SUCCESS"}]
    mgr.get_pr_checks = AsyncMock(return_value=checks)

    await mgr.wait_for_ci(101, timeout=60, poll_interval=5, stop_event=stop)

    events = event_bus.get_history()
    ci_events = [e for e in events if e.type == EventType.CI_CHECK]
    assert len(ci_events) >= 1
    assert ci_events[0].data["pr"] == 101
    assert ci_events[0].data["status"] == "passed"


# ---------------------------------------------------------------------------
# ensure_labels_exist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_labels_exist_creates_all_hydra_labels(
    config, event_bus, tmp_path
):
    """ensure_labels_exist should call gh label create --force for each label."""
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        await mgr.ensure_labels_exist()

    # Should be called once per label (5 lifecycle labels)
    assert mock_create.call_count == len(PRManager._HYDRA_LABELS)

    # Verify each call uses gh label create --force
    for call in mock_create.call_args_list:
        args = call[0]
        assert args[0] == "gh"
        assert "label" in args
        assert "create" in args
        assert "--force" in args
        assert "--color" in args
        assert "--description" in args


@pytest.mark.asyncio
async def test_ensure_labels_exist_uses_config_label_names(config, event_bus, tmp_path):
    """ensure_labels_exist should use label names from config (not hardcoded defaults)."""
    from config import HydraConfig

    cfg = HydraConfig(
        find_label=["custom-find"],
        ready_label=["custom-ready"],
        planner_label=["custom-plan"],
        review_label=["custom-review"],
        hitl_label=["custom-hitl"],
        fixed_label=["custom-fixed"],
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    with patch("asyncio.create_subprocess_exec", mock_create):
        await mgr.ensure_labels_exist()

    # Collect all label names passed to gh label create
    created_labels = set()
    for call in mock_create.call_args_list:
        args = call[0]
        # Label name is the arg after "create"
        create_idx = list(args).index("create")
        created_labels.add(args[create_idx + 1])

    assert created_labels == {
        "custom-find",
        "custom-plan",
        "custom-ready",
        "custom-review",
        "custom-hitl",
        "custom-fixed",
    }


@pytest.mark.asyncio
async def test_ensure_labels_exist_dry_run_skips(dry_config, event_bus):
    """In dry-run mode, ensure_labels_exist should not call subprocess."""
    mgr = _make_manager(dry_config, event_bus)
    mock_create = _make_subprocess_mock(returncode=0)

    with patch("asyncio.create_subprocess_exec", mock_create):
        await mgr.ensure_labels_exist()

    mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_labels_exist_handles_individual_failures(
    config, event_bus, tmp_path
):
    """If one label creation fails, others should still be attempted."""
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)

    # First call fails, rest succeed
    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_proc = AsyncMock()
        if call_count == 1:
            mock_proc.returncode = 1
            mock_proc.communicate = AsyncMock(return_value=(b"", b"permission denied"))
        else:
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.wait = AsyncMock(return_value=mock_proc.returncode)
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=side_effect):
        # Should not raise
        await mgr.ensure_labels_exist()

    # All labels should be attempted even though first one failed
    assert call_count == len(PRManager._HYDRA_LABELS)


# ---------------------------------------------------------------------------
# _run_with_body_file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_with_body_file_writes_temp_file(config, event_bus, tmp_path):
    """_run_with_body_file should write body to a temp .md file and pass --body-file."""
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="ok")
    body_content = None

    original_mock = mock_create

    async def capture_body_file(*args, **kwargs):
        nonlocal body_content
        cmd = args
        for i, arg in enumerate(cmd):
            if arg == "--body-file" and i + 1 < len(cmd):
                body_content = Path(cmd[i + 1]).read_text()
                break
        return await original_mock(*args, **kwargs)

    with patch("asyncio.create_subprocess_exec", side_effect=capture_body_file):
        await mgr._run_with_body_file(
            "gh", "issue", "comment", "1", body="Large plan content", cwd=tmp_path
        )

    assert body_content == "Large plan content"


@pytest.mark.asyncio
async def test_run_with_body_file_cleans_up_temp_file(config, event_bus, tmp_path):
    """_run_with_body_file should delete the temp file after completion."""
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="ok")
    temp_file_path = None

    original_mock = mock_create

    async def capture_path(*args, **kwargs):
        nonlocal temp_file_path
        cmd = args
        for i, arg in enumerate(cmd):
            if arg == "--body-file" and i + 1 < len(cmd):
                temp_file_path = cmd[i + 1]
                break
        return await original_mock(*args, **kwargs)

    with patch("asyncio.create_subprocess_exec", side_effect=capture_path):
        await mgr._run_with_body_file(
            "gh", "issue", "comment", "1", body="content", cwd=tmp_path
        )

    assert temp_file_path is not None
    assert not Path(temp_file_path).exists(), "Temp file should be cleaned up"


@pytest.mark.asyncio
async def test_run_with_body_file_cleans_up_on_error(config, event_bus, tmp_path):
    """_run_with_body_file should delete the temp file even on failure."""
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=1, stderr="fail")
    temp_file_path = None

    original_mock = mock_create

    async def capture_path(*args, **kwargs):
        nonlocal temp_file_path
        cmd = args
        for i, arg in enumerate(cmd):
            if arg == "--body-file" and i + 1 < len(cmd):
                temp_file_path = cmd[i + 1]
                break
        return await original_mock(*args, **kwargs)

    with (
        patch("asyncio.create_subprocess_exec", side_effect=capture_path),
        pytest.raises(RuntimeError),
    ):
        await mgr._run_with_body_file(
            "gh", "issue", "comment", "1", body="content", cwd=tmp_path
        )

    assert temp_file_path is not None
    assert not Path(temp_file_path).exists(), "Temp file should be cleaned up on error"


# ---------------------------------------------------------------------------
# post_comment chunking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_comment_chunks_large_body(config, event_bus, tmp_path):
    """post_comment should split oversized bodies into multiple comments."""
    from config import HydraConfig

    cfg = HydraConfig(
        ready_label=config.ready_label,
        repo=config.repo,
        repo_root=tmp_path,
        worktree_base=tmp_path / "worktrees",
        state_file=tmp_path / "state.json",
    )
    mgr = _make_manager(cfg, event_bus)
    mock_create = _make_subprocess_mock(returncode=0, stdout="")

    # Body larger than the GitHub comment limit
    large_body = "x" * (PRManager._GITHUB_COMMENT_LIMIT + 1000)

    with patch("asyncio.create_subprocess_exec", mock_create):
        await mgr.post_comment(42, large_body)

    # Should have been split into 2 comments
    assert mock_create.call_count == 2
