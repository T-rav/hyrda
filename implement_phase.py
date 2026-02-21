"""Implementation batch processing for the Hydra orchestrator."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from agent import AgentRunner
from config import HydraConfig
from issue_fetcher import IssueFetcher
from models import GitHubIssue, WorkerResult
from pr_manager import PRManager
from state import StateTracker
from worktree import WorktreeManager

logger = logging.getLogger("hydra.implement_phase")


class ImplementPhase:
    """Fetches ready issues and runs implementation agents concurrently."""

    def __init__(
        self,
        config: HydraConfig,
        state: StateTracker,
        worktrees: WorktreeManager,
        agents: AgentRunner,
        prs: PRManager,
        fetcher: IssueFetcher,
        stop_event: asyncio.Event,
        active_issues: set[int],
    ) -> None:
        self._config = config
        self._state = state
        self._worktrees = worktrees
        self._agents = agents
        self._prs = prs
        self._fetcher = fetcher
        self._stop_event = stop_event
        self._active_issues = active_issues

    async def run_batch(
        self,
    ) -> tuple[list[WorkerResult], list[GitHubIssue]]:
        """Fetch ready issues and run implementation agents concurrently.

        Returns ``(worker_results, issues)`` so the caller has access
        to the issue list for downstream phases.  The internal queue
        holds up to ``2 * max_workers`` issues.
        """
        issues = await self._fetcher.fetch_ready_issues(self._active_issues)
        if not issues:
            return [], []

        semaphore = asyncio.Semaphore(self._config.max_workers)
        results: list[WorkerResult] = []

        async def _worker(idx: int, issue: GitHubIssue) -> WorkerResult:
            if self._stop_event.is_set():
                return WorkerResult(
                    issue_number=issue.number,
                    branch=f"agent/issue-{issue.number}",
                    error="stopped",
                )

            async with semaphore:
                if self._stop_event.is_set():
                    return WorkerResult(
                        issue_number=issue.number,
                        branch=f"agent/issue-{issue.number}",
                        error="stopped",
                    )

                branch = f"agent/issue-{issue.number}"
                self._active_issues.add(issue.number)
                self._state.mark_issue(issue.number, "in_progress")
                self._state.set_branch(issue.number, branch)

                try:
                    # Resume: reuse existing worktree if present
                    wt_path = self._config.worktree_base / f"issue-{issue.number}"
                    if wt_path.is_dir():
                        logger.info(
                            "Resuming existing worktree for issue #%d", issue.number
                        )
                    else:
                        wt_path = await self._worktrees.create(issue.number, branch)
                    self._state.set_worktree(issue.number, str(wt_path))

                    # Push branch immediately so it appears on the GitHub issue
                    await self._prs.push_branch(wt_path, branch)
                    await self._prs.post_comment(
                        issue.number,
                        f"**Branch:** [`{branch}`](https://github.com/"
                        f"{self._config.repo}/tree/{branch})\n\n"
                        f"Implementation in progress.",
                    )

                    # Check for review feedback from a previous
                    # REQUEST_CHANGES cycle
                    review_feedback = (
                        self._state.get_review_feedback(issue.number) or ""
                    )

                    result = await self._agents.run(
                        issue,
                        wt_path,
                        branch,
                        worker_id=idx,
                        review_feedback=review_feedback,
                    )

                    # Clear review feedback after implementation run
                    if review_feedback:
                        self._state.clear_review_feedback(issue.number)

                    if result.duration_seconds > 0:
                        self._state.record_implementation_duration(
                            result.duration_seconds
                        )
                    if result.quality_fix_attempts > 0:
                        self._state.record_quality_fix_rounds(
                            result.quality_fix_attempts
                        )

                    # Persist worker metrics for retrospective analysis
                    self._state.set_worker_result_meta(
                        issue.number,
                        {
                            "quality_fix_attempts": result.quality_fix_attempts,
                            "duration_seconds": result.duration_seconds,
                            "error": result.error,
                        },
                    )

                    # Push final commits and create PR
                    if result.worktree_path:
                        pushed = await self._prs.push_branch(
                            Path(result.worktree_path), result.branch
                        )
                        if pushed:
                            # On retry cycles a PR already exists for this
                            # branch — skip creation to avoid gh CLI errors.
                            pr = None
                            is_retry = bool(review_feedback)
                            if not is_retry:
                                draft = not result.success
                                pr = await self._prs.create_pr(
                                    issue, result.branch, draft=draft
                                )
                                result.pr_info = pr

                            if result.success:
                                # Success: move to review pipeline
                                for lbl in self._config.ready_label:
                                    await self._prs.remove_label(issue.number, lbl)
                                await self._prs.add_labels(
                                    issue.number, [self._config.review_label[0]]
                                )
                                if pr and pr.number > 0:
                                    await self._prs.add_pr_labels(
                                        pr.number, [self._config.review_label[0]]
                                    )
                            # Failure: keep implementation label so issue can be retried

                    status = "success" if result.success else "failed"
                    self._state.mark_issue(issue.number, status)
                    return result
                except Exception:
                    logger.exception("Worker failed for issue #%d", issue.number)
                    self._state.mark_issue(issue.number, "failed")
                    return WorkerResult(
                        issue_number=issue.number,
                        branch=branch,
                        error=f"Worker exception for issue #{issue.number}",
                    )
                finally:
                    self._active_issues.discard(issue.number)

        all_tasks = [
            asyncio.create_task(_worker(i, issue)) for i, issue in enumerate(issues)
        ]
        for task in asyncio.as_completed(all_tasks):
            results.append(await task)
            # Cancel remaining tasks if stop requested
            if self._stop_event.is_set():
                for t in all_tasks:
                    t.cancel()
                break

        return results, issues
