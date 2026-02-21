"""Shared test helpers for Hydra tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


class AsyncLineIter:
    """Async iterator yielding raw bytes lines for mock proc.stdout."""

    def __init__(self, lines: list[bytes]) -> None:
        self._it = iter(lines)

    def __aiter__(self):  # noqa: ANN204
        return self

    async def __anext__(self) -> bytes:
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration from None


def make_streaming_proc(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> AsyncMock:
    """Build a mock for asyncio.create_subprocess_exec with streaming stdout."""
    mock_proc = AsyncMock()
    mock_proc.returncode = returncode
    # stdin.write and stdin.close are sync on StreamWriter; drain is async
    mock_proc.stdin = MagicMock()
    mock_proc.stdin.drain = AsyncMock()
    raw_lines = [(ln + "\n").encode() for ln in stdout.split("\n")] if stdout else []
    mock_proc.stdout = AsyncLineIter(raw_lines)
    mock_proc.stderr = AsyncMock()
    mock_proc.stderr.read = AsyncMock(return_value=stderr.encode())
    mock_proc.wait = AsyncMock(return_value=returncode)
    return AsyncMock(return_value=mock_proc)


class ConfigFactory:
    """Factory for HydraConfig instances."""

    @staticmethod
    def create(
        *,
        ready_label: list[str] | None = None,
        batch_size: int = 3,
        max_workers: int = 2,
        max_planners: int = 1,
        max_reviewers: int = 1,
        max_budget_usd: float = 1.0,
        model: str = "sonnet",
        review_model: str = "opus",
        review_budget_usd: float = 1.0,
        ci_check_timeout: int = 600,
        ci_poll_interval: int = 30,
        max_ci_fix_attempts: int = 0,
        max_quality_fix_attempts: int = 2,
        max_review_fix_attempts: int = 2,
        min_review_findings: int = 3,
        max_merge_conflict_fix_attempts: int = 3,
        review_label: list[str] | None = None,
        hitl_label: list[str] | None = None,
        fixed_label: list[str] | None = None,
        improve_label: list[str] | None = None,
        dup_label: list[str] | None = None,
        find_label: list[str] | None = None,
        planner_label: list[str] | None = None,
        memory_label: list[str] | None = None,
        planner_model: str = "opus",
        planner_budget_usd: float = 1.0,
        min_plan_words: int = 200,
        max_new_files_warning: int = 5,
        lite_plan_labels: list[str] | None = None,
        repo: str = "test-org/test-repo",
        dry_run: bool = False,
        gh_token: str = "",
        git_user_name: str = "",
        git_user_email: str = "",
        dashboard_enabled: bool = False,
        dashboard_port: int = 15555,
        review_insight_window: int = 10,
        review_pattern_threshold: int = 3,
        poll_interval: int = 5,
        gh_max_retries: int = 3,
        test_command: str = "make test",
        max_issue_body_chars: int = 10_000,
        max_review_diff_chars: int = 15_000,
        repo_root: Path | None = None,
        worktree_base: Path | None = None,
        state_file: Path | None = None,
        event_log_path: Path | None = None,
        config_file: Path | None = None,
    ):
        """Create a HydraConfig with test-friendly defaults."""
        from config import HydraConfig

        root = repo_root or Path("/tmp/hydra-test-repo")
        return HydraConfig(
            config_file=config_file,
            ready_label=ready_label if ready_label is not None else ["test-label"],
            batch_size=batch_size,
            max_workers=max_workers,
            max_planners=max_planners,
            max_reviewers=max_reviewers,
            max_budget_usd=max_budget_usd,
            model=model,
            review_model=review_model,
            review_budget_usd=review_budget_usd,
            ci_check_timeout=ci_check_timeout,
            ci_poll_interval=ci_poll_interval,
            max_ci_fix_attempts=max_ci_fix_attempts,
            max_quality_fix_attempts=max_quality_fix_attempts,
            max_review_fix_attempts=max_review_fix_attempts,
            min_review_findings=min_review_findings,
            max_merge_conflict_fix_attempts=max_merge_conflict_fix_attempts,
            review_label=review_label if review_label is not None else ["hydra-review"],
            hitl_label=hitl_label if hitl_label is not None else ["hydra-hitl"],
            fixed_label=fixed_label if fixed_label is not None else ["hydra-fixed"],
            improve_label=improve_label
            if improve_label is not None
            else ["hydra-improve"],
            dup_label=dup_label if dup_label is not None else ["hydra-dup"],
            find_label=find_label if find_label is not None else ["hydra-find"],
            planner_label=planner_label
            if planner_label is not None
            else ["hydra-plan"],
            memory_label=memory_label if memory_label is not None else ["hydra-memory"],
            planner_model=planner_model,
            planner_budget_usd=planner_budget_usd,
            min_plan_words=min_plan_words,
            max_new_files_warning=max_new_files_warning,
            lite_plan_labels=lite_plan_labels
            if lite_plan_labels is not None
            else ["bug", "typo", "docs"],
            repo=repo,
            dry_run=dry_run,
            gh_token=gh_token,
            git_user_name=git_user_name,
            git_user_email=git_user_email,
            dashboard_enabled=dashboard_enabled,
            dashboard_port=dashboard_port,
            review_insight_window=review_insight_window,
            review_pattern_threshold=review_pattern_threshold,
            poll_interval=poll_interval,
            gh_max_retries=gh_max_retries,
            test_command=test_command,
            max_issue_body_chars=max_issue_body_chars,
            max_review_diff_chars=max_review_diff_chars,
            repo_root=root,
            worktree_base=worktree_base or root.parent / "test-worktrees",
            state_file=state_file or root / ".hydra-state.json",
            event_log_path=event_log_path or root / ".hydra-events.jsonl",
        )
