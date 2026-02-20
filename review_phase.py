"""Review processing for the Hydra orchestrator."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from config import HydraConfig
from models import GitHubIssue, PRInfo, ReviewResult, ReviewVerdict
from pr_manager import PRManager
from reviewer import ReviewRunner
from state import StateTracker
from worktree import WorktreeManager

logger = logging.getLogger("hydra.review_phase")


class ReviewPhase:
    """Runs reviewer agents on PRs, merging approved ones inline."""

    def __init__(
        self,
        config: HydraConfig,
        state: StateTracker,
        worktrees: WorktreeManager,
        reviewers: ReviewRunner,
        prs: PRManager,
        stop_event: asyncio.Event,
        active_issues: set[int],
    ) -> None:
        self._config = config
        self._state = state
        self._worktrees = worktrees
        self._reviewers = reviewers
        self._prs = prs
        self._stop_event = stop_event
        self._active_issues = active_issues

    async def review_prs(
        self,
        prs: list[PRInfo],
        issues: list[GitHubIssue],
    ) -> list[ReviewResult]:
        """Run reviewer agents on non-draft PRs, merging approved ones inline."""
        if not prs:
            return []

        issue_map = {i.number: i for i in issues}
        semaphore = asyncio.Semaphore(self._config.max_reviewers)
        results: list[ReviewResult] = []

        async def _review_one(idx: int, pr: PRInfo) -> ReviewResult:
            async with semaphore:
                self._active_issues.add(pr.issue_number)
                issue = issue_map.get(pr.issue_number)
                if issue is None:
                    return ReviewResult(
                        pr_number=pr.number,
                        issue_number=pr.issue_number,
                        summary="Issue not found",
                    )

                # The reviewer works in the same worktree as the implementation
                wt_path = self._config.worktree_base / f"issue-{pr.issue_number}"
                if not wt_path.exists():
                    # Create a fresh worktree for review
                    wt_path = await self._worktrees.create(pr.issue_number, pr.branch)

                # Merge main before reviewing so we review up-to-date code
                merged_main = await self._worktrees.merge_main(wt_path, pr.branch)
                if merged_main:
                    await self._prs.push_branch(wt_path, pr.branch)
                else:
                    logger.warning(
                        "PR #%d has conflicts with %s — escalating to HITL",
                        pr.number,
                        self._config.main_branch,
                    )
                    await self._prs.post_pr_comment(
                        pr.number,
                        f"**Merge conflicts** with `{self._config.main_branch}` "
                        "that could not be resolved automatically. "
                        "Escalating to human review.",
                    )
                    for lbl in self._config.review_label:
                        await self._prs.remove_label(pr.issue_number, lbl)
                    await self._prs.add_labels(
                        pr.issue_number, [self._config.hitl_label[0]]
                    )
                    self._active_issues.discard(pr.issue_number)
                    return ReviewResult(
                        pr_number=pr.number,
                        issue_number=pr.issue_number,
                        summary="Merge conflicts with main — escalated to HITL",
                    )

                # Get the diff (after merge so it reflects current main)
                diff = await self._prs.get_pr_diff(pr.number)

                result = await self._reviewers.review(
                    pr, issue, wt_path, diff, worker_id=idx
                )

                # If reviewer made fixes, push them
                if result.fixes_made:
                    await self._prs.push_branch(wt_path, pr.branch)

                # Post review summary as PR comment
                if result.summary and pr.number > 0:
                    await self._prs.post_pr_comment(pr.number, result.summary)

                # Submit formal GitHub PR review for non-approve verdicts.
                # Approve is skipped to avoid "cannot approve your own PR"
                # errors — Hydra merges directly once CI passes.
                if pr.number > 0 and result.verdict != ReviewVerdict.APPROVE:
                    await self._prs.submit_review(
                        pr.number, result.verdict, result.summary
                    )

                self._state.mark_pr(pr.number, result.verdict.value)
                self._state.mark_issue(pr.issue_number, "reviewed")

                # Merge immediately if approved (with optional CI gate)
                if result.verdict == ReviewVerdict.APPROVE and pr.number > 0:
                    should_merge = True
                    if self._config.max_ci_fix_attempts > 0:
                        should_merge = await self.wait_and_fix_ci(
                            pr, issue, wt_path, result, idx
                        )
                    if should_merge:
                        success = await self._prs.merge_pr(pr.number)
                        if success:
                            result.merged = True
                            self._state.mark_issue(pr.issue_number, "merged")
                            self._state.record_pr_merged()
                            self._state.record_issue_completed()
                            for lbl in self._config.review_label:
                                await self._prs.remove_label(pr.issue_number, lbl)
                            await self._prs.add_labels(
                                pr.issue_number,
                                [self._config.fixed_label[0]],
                            )
                        else:
                            logger.warning(
                                "PR #%d merge failed — escalating to HITL",
                                pr.number,
                            )
                            await self._prs.post_pr_comment(
                                pr.number,
                                "**Merge failed** — PR could not be merged. "
                                "Escalating to human review.",
                            )
                            for lbl in self._config.review_label:
                                await self._prs.remove_label(pr.issue_number, lbl)
                            await self._prs.add_labels(
                                pr.issue_number,
                                [self._config.hitl_label[0]],
                            )

                # Cleanup worktree after review
                try:
                    await self._worktrees.destroy(pr.issue_number)
                    self._state.remove_worktree(pr.issue_number)
                except RuntimeError as exc:
                    logger.warning(
                        "Could not destroy worktree for issue #%d: %s",
                        pr.issue_number,
                        exc,
                    )

                # Release so issue can be re-reviewed if needed
                self._active_issues.discard(pr.issue_number)
                return result

        tasks = [asyncio.create_task(_review_one(i, pr)) for i, pr in enumerate(prs)]
        for task in asyncio.as_completed(tasks):
            results.append(await task)

        return results

    async def wait_and_fix_ci(
        self,
        pr: PRInfo,
        issue: GitHubIssue,
        wt_path: Path,
        result: ReviewResult,
        worker_id: int,
    ) -> bool:
        """Wait for CI and attempt fixes if it fails.

        Returns *True* if CI passed and the PR should be merged.
        Mutates *result* to set ``ci_passed`` and ``ci_fix_attempts``.
        """
        max_attempts = self._config.max_ci_fix_attempts
        summary = ""

        for attempt in range(max_attempts + 1):
            passed, summary = await self._prs.wait_for_ci(
                pr.number,
                self._config.ci_check_timeout,
                self._config.ci_poll_interval,
                self._stop_event,
            )
            if passed:
                result.ci_passed = True
                return True

            # Last attempt — no more retries
            if attempt >= max_attempts:
                break

            # Run the CI fix agent
            fix_result = await self._reviewers.fix_ci(
                pr,
                issue,
                wt_path,
                summary,
                attempt=attempt + 1,
                worker_id=worker_id,
            )
            result.ci_fix_attempts += 1

            if not fix_result.fixes_made:
                logger.info(
                    "CI fix agent made no changes for PR #%d — stopping retries",
                    pr.number,
                )
                break

            # Push fixes and loop back to wait_for_ci
            await self._prs.push_branch(wt_path, pr.branch)

        # CI failed after all attempts — escalate to human
        result.ci_passed = False
        await self._prs.post_pr_comment(
            pr.number,
            f"**CI failed** after {result.ci_fix_attempts} fix attempt(s).\n\n"
            f"Last failure: {summary}\n\n"
            f"PR not merged — escalating to human review.",
        )
        # Swap to HITL label so the dashboard HITL tab picks it up
        for lbl in self._config.review_label:
            await self._prs.remove_label(issue.number, lbl)
        await self._prs.add_labels(issue.number, [self._config.hitl_label[0]])
        return False
