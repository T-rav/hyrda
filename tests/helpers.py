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
        ready_label: str = "test-label",
        batch_size: int = 3,
        max_workers: int = 2,
        max_budget_usd: float = 1.0,
        model: str = "sonnet",
        review_model: str = "opus",
        review_budget_usd: float = 1.0,
        ci_check_timeout: int = 600,
        ci_poll_interval: int = 30,
        max_ci_fix_attempts: int = 0,
        review_label: str = "hydra-review",
        hitl_label: str = "hydra-hitl",
        fixed_label: str = "hydra-fixed",
        planner_label: str = "hydra-plan",
        planner_model: str = "opus",
        planner_budget_usd: float = 1.0,
        repo: str = "test-org/test-repo",
        dry_run: bool = False,
        dashboard_enabled: bool = False,
        dashboard_port: int = 15555,
        repo_root: Path | None = None,
        worktree_base: Path | None = None,
        state_file: Path | None = None,
    ):
        """Create a HydraConfig with test-friendly defaults."""
        from config import HydraConfig

        root = repo_root or Path("/tmp/hydra-test-repo")
        return HydraConfig(
            ready_label=ready_label,
            batch_size=batch_size,
            max_workers=max_workers,
            max_budget_usd=max_budget_usd,
            model=model,
            review_model=review_model,
            review_budget_usd=review_budget_usd,
            ci_check_timeout=ci_check_timeout,
            ci_poll_interval=ci_poll_interval,
            max_ci_fix_attempts=max_ci_fix_attempts,
            review_label=review_label,
            hitl_label=hitl_label,
            fixed_label=fixed_label,
            planner_label=planner_label,
            planner_model=planner_model,
            planner_budget_usd=planner_budget_usd,
            repo=repo,
            dry_run=dry_run,
            dashboard_enabled=dashboard_enabled,
            dashboard_port=dashboard_port,
            repo_root=root,
            worktree_base=worktree_base or root.parent / "test-worktrees",
            state_file=state_file or root / ".hydra-state.json",
        )
