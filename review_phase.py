"""Review processing for the Hydra orchestrator."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from agent import AgentRunner
from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from models import GitHubIssue, PRInfo, ReviewResult, ReviewVerdict
from pr_manager import PRManager, SelfReviewError
from retrospective import RetrospectiveCollector
from review_insights import (
    CATEGORY_DESCRIPTIONS,
    ReviewInsightStore,
    ReviewRecord,
    analyze_patterns,
    build_insight_issue_body,
    extract_categories,
)
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
        agents: AgentRunner | None = None,
        event_bus: EventBus | None = None,
        retrospective: RetrospectiveCollector | None = None,
    ) -> None:
        self._config = config
        self._state = state
        self._worktrees = worktrees
        self._reviewers = reviewers
        self._prs = prs
        self._stop_event = stop_event
        self._active_issues = active_issues
        self._agents = agents
        self._bus = event_bus or EventBus()
        self._retrospective = retrospective
        self._insights = ReviewInsightStore(config.repo_root / ".hydra" / "memory")

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

                try:
                    # Publish a start event immediately so the dashboard
                    # shows this worker as active during pre-review work
                    # (worktree creation, merge, conflict resolution).
                    await self._bus.publish(
                        HydraEvent(
                            type=EventType.REVIEW_UPDATE,
                            data={
                                "pr": pr.number,
                                "issue": pr.issue_number,
                                "worker": idx,
                                "status": "start",
                                "role": "reviewer",
                            },
                        )
                    )
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
                        wt_path = await self._worktrees.create(
                            pr.issue_number, pr.branch
                        )

                    # Merge main into the branch before reviewing so we review
                    # up-to-date code.  Merge keeps the push fast-forward
                    # so no force-push is needed.
                    await self._publish_review_status(pr, idx, "merge_main")
                    merged_main = await self._worktrees.merge_main(wt_path, pr.branch)
                    if not merged_main:
                        # Conflicts — let the agent try to resolve them
                        logger.info(
                            "PR #%d has conflicts with %s — running agent to resolve",
                            pr.number,
                            self._config.main_branch,
                        )
                        await self._publish_review_status(
                            pr, idx, "conflict_resolution"
                        )
                        merged_main = await self._resolve_merge_conflicts(
                            pr, issue, wt_path, worker_id=idx
                        )
                    if merged_main:
                        await self._prs.push_branch(wt_path, pr.branch)
                    else:
                        logger.warning(
                            "PR #%d merge conflict resolution failed — escalating to HITL",
                            pr.number,
                        )
                        await self._publish_review_status(pr, idx, "escalating")
                        await self._prs.post_pr_comment(
                            pr.number,
                            f"**Merge conflicts** with "
                            f"`{self._config.main_branch}` could not be "
                            "resolved automatically. "
                            "Escalating to human review.",
                        )
                        self._state.set_hitl_origin(
                            pr.issue_number, self._config.review_label[0]
                        )
                        self._state.set_hitl_cause(
                            pr.issue_number,
                            "Merge conflict with main branch",
                        )
                        for lbl in self._config.review_label:
                            await self._prs.remove_label(pr.issue_number, lbl)
                            await self._prs.remove_pr_label(pr.number, lbl)
                        await self._prs.add_labels(
                            pr.issue_number, [self._config.hitl_label[0]]
                        )
                        await self._prs.add_pr_labels(
                            pr.number, [self._config.hitl_label[0]]
                        )
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
                        try:
                            await self._prs.submit_review(
                                pr.number, result.verdict, result.summary
                            )
                        except SelfReviewError:
                            logger.info(
                                "Skipping formal %s review on own PR #%d"
                                " — already posted as comment",
                                result.verdict.value,
                                pr.number,
                            )

                    self._state.mark_pr(pr.number, result.verdict.value)
                    self._state.mark_issue(pr.issue_number, "reviewed")

                    # Record review insight (non-blocking)
                    await self._record_review_insight(result)

                    # Merge immediately if approved (with optional CI gate)
                    if result.verdict == ReviewVerdict.APPROVE and pr.number > 0:
                        should_merge = True
                        if self._config.max_ci_fix_attempts > 0:
                            should_merge = await self.wait_and_fix_ci(
                                pr, issue, wt_path, result, idx
                            )
                        if should_merge:
                            await self._publish_review_status(pr, idx, "merging")
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
                                # Run post-merge retrospective (non-blocking;
                                # record() catches all exceptions internally)
                                if self._retrospective:
                                    await self._retrospective.record(
                                        issue_number=pr.issue_number,
                                        pr_number=pr.number,
                                        review_result=result,
                                    )
                            else:
                                logger.warning(
                                    "PR #%d merge failed — escalating to HITL",
                                    pr.number,
                                )
                                await self._publish_review_status(pr, idx, "escalating")
                                await self._prs.post_pr_comment(
                                    pr.number,
                                    "**Merge failed** — PR could not be merged. "
                                    "Escalating to human review.",
                                )
                                self._state.set_hitl_origin(
                                    pr.issue_number, self._config.review_label[0]
                                )
                                self._state.set_hitl_cause(
                                    pr.issue_number,
                                    "PR merge failed on GitHub",
                                )
                                for lbl in self._config.review_label:
                                    await self._prs.remove_label(pr.issue_number, lbl)
                                    await self._prs.remove_pr_label(pr.number, lbl)
                                await self._prs.add_labels(
                                    pr.issue_number,
                                    [self._config.hitl_label[0]],
                                )
                                await self._prs.add_pr_labels(
                                    pr.number,
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

                    return result
                except Exception:
                    logger.exception(
                        "Review failed for PR #%d (issue #%d)",
                        pr.number,
                        pr.issue_number,
                    )
                    return ReviewResult(
                        pr_number=pr.number,
                        issue_number=pr.issue_number,
                        summary="Review failed due to unexpected error",
                    )
                finally:
                    await self._publish_review_status(pr, idx, "done")
                    self._active_issues.discard(pr.issue_number)

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
            await self._publish_review_status(pr, worker_id, "ci_wait")
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
            await self._publish_review_status(pr, worker_id, "ci_fix")
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
        await self._publish_review_status(pr, worker_id, "escalating")
        await self._prs.post_pr_comment(
            pr.number,
            f"**CI failed** after {result.ci_fix_attempts} fix attempt(s).\n\n"
            f"Last failure: {summary}\n\n"
            f"PR not merged — escalating to human review.",
        )
        # Swap to HITL label so the dashboard HITL tab picks it up
        self._state.set_hitl_origin(issue.number, self._config.review_label[0])
        self._state.set_hitl_cause(
            issue.number,
            f"CI failed after {result.ci_fix_attempts} fix attempt(s)",
        )
        for lbl in self._config.review_label:
            await self._prs.remove_label(issue.number, lbl)
            await self._prs.remove_pr_label(pr.number, lbl)
        await self._prs.add_labels(issue.number, [self._config.hitl_label[0]])
        await self._prs.add_pr_labels(pr.number, [self._config.hitl_label[0]])
        return False

    async def _record_review_insight(self, result: ReviewResult) -> None:
        """Record a review result and file improvement proposals if patterns emerge.

        Wrapped in try/except so insight failures never interrupt the review flow.
        """
        try:
            record = ReviewRecord(
                pr_number=result.pr_number,
                issue_number=result.issue_number,
                timestamp=datetime.now(UTC).isoformat(),
                verdict=result.verdict.value,
                summary=result.summary,
                fixes_made=result.fixes_made,
                categories=extract_categories(result.summary),
            )
            self._insights.append_review(record)

            recent = self._insights.load_recent(self._config.review_insight_window)
            patterns = analyze_patterns(recent, self._config.review_pattern_threshold)
            proposed = self._insights.get_proposed_categories()

            for category, count, evidence in patterns:
                if category in proposed:
                    continue
                body = build_insight_issue_body(category, count, len(recent), evidence)
                desc = CATEGORY_DESCRIPTIONS.get(category, category)
                title = f"[Review Insight] Recurring feedback: {desc}"
                labels = self._config.improve_label[:1] + self._config.hitl_label[:1]
                await self._prs.create_issue(title, body, labels)
                self._insights.mark_category_proposed(category)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Review insight recording failed for PR #%d",
                result.pr_number,
                exc_info=True,
            )

    async def _publish_review_status(
        self, pr: PRInfo, worker_id: int, status: str
    ) -> None:
        """Emit a REVIEW_UPDATE event with the given status."""
        await self._bus.publish(
            HydraEvent(
                type=EventType.REVIEW_UPDATE,
                data={
                    "pr": pr.number,
                    "issue": pr.issue_number,
                    "worker": worker_id,
                    "status": status,
                    "role": "reviewer",
                },
            )
        )

    async def _resolve_merge_conflicts(
        self,
        pr: PRInfo,
        issue: GitHubIssue,
        wt_path: Path,
        worker_id: int,
    ) -> bool:
        """Use the implementation agent to resolve merge conflicts.

        Retries up to ``config.max_merge_conflict_fix_attempts`` times.
        Each attempt starts a merge (leaving conflict markers), runs the
        agent to resolve them, and verifies with ``make quality``.

        Returns *True* if the conflicts were resolved successfully.
        """
        if self._agents is None:
            logger.warning(
                "No agent runner available for conflict resolution on PR #%d",
                pr.number,
            )
            return False

        max_attempts = self._config.max_merge_conflict_fix_attempts
        last_error: str | None = None

        for attempt in range(1, max_attempts + 1):
            # Abort any prior failed merge before retrying
            if attempt > 1:
                await self._worktrees.abort_merge(wt_path)

            # Start merge leaving conflict markers in place
            clean = await self._worktrees.start_merge_main(wt_path, pr.branch)
            if clean:
                return True

            logger.info(
                "Conflict resolution attempt %d/%d for PR #%d",
                attempt,
                max_attempts,
                pr.number,
            )
            await self._publish_review_status(pr, worker_id, "conflict_resolution")

            try:
                prompt = self._build_conflict_prompt(issue, last_error, attempt)
                cmd = self._agents._build_command(wt_path)
                transcript = await self._agents._execute(
                    cmd, prompt, wt_path, issue.number
                )

                self._save_conflict_transcript(
                    pr.number, issue.number, attempt, transcript
                )

                success, error_msg = await self._agents._verify_result(
                    wt_path, pr.branch
                )
                if success:
                    return True

                last_error = error_msg
                logger.warning(
                    "Conflict resolution attempt %d/%d failed for PR #%d: %s",
                    attempt,
                    max_attempts,
                    pr.number,
                    error_msg[:200] if error_msg else "",
                )
            except Exception as exc:
                logger.error(
                    "Conflict resolution agent failed for PR #%d (attempt %d/%d): %s",
                    pr.number,
                    attempt,
                    max_attempts,
                    exc,
                )
                last_error = str(exc)

        # All attempts exhausted — abort and let caller escalate
        await self._worktrees.abort_merge(wt_path)
        return False

    def _build_conflict_prompt(
        self,
        issue: GitHubIssue,
        last_error: str | None,
        attempt: int,
    ) -> str:
        """Build the conflict resolution prompt, adding error context on retries."""
        prompt = (
            f"The branch for issue #{issue.number} ({issue.title}) has "
            f"merge conflicts with main.\n\n"
            "There is a `git merge` in progress with conflict markers "
            "in the working tree.\n\n"
            "## Instructions\n\n"
            "1. Run `git diff --name-only --diff-filter=U` to list "
            "conflicted files.\n"
            "2. Open each conflicted file, understand both sides of the "
            "conflict, and resolve the markers.\n"
            "3. Stage all resolved files with `git add`.\n"
            "4. Complete the merge with "
            "`git commit --no-edit`.\n"
            "5. Run `make quality` to ensure everything passes.\n"
            "6. If quality fails, fix the issues and commit again.\n\n"
            "## Rules\n\n"
            "- Keep the intent of the original PR changes.\n"
            "- Incorporate upstream (main) changes correctly.\n"
            "- Do NOT push to remote. Do NOT create pull requests.\n"
            "- Ensure `make quality` passes before finishing.\n"
        )
        if last_error and attempt > 1:
            prompt += (
                f"\n## Previous Attempt Failed\n\n"
                f"Attempt {attempt - 1} resolved the conflicts but "
                f"failed verification:\n"
                f"```\n{last_error[-3000:]}\n```\n"
                f"Please resolve the conflicts again, paying attention "
                f"to the above errors.\n"
            )
        return prompt

    def _save_conflict_transcript(
        self,
        pr_number: int,
        issue_number: int,
        attempt: int,
        transcript: str,
    ) -> None:
        """Save a conflict resolution transcript to ``.hydra/logs/``."""
        log_dir = self._config.repo_root / ".hydra" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"conflict-pr-{pr_number}-attempt-{attempt}.txt"
        path.write_text(transcript)
        logger.info(
            "Conflict resolution transcript saved to %s",
            path,
            extra={"issue": issue_number},
        )
