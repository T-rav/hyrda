"""Review processing for the Hydra orchestrator."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from acceptance_criteria import AcceptanceCriteriaGenerator
from agent import AgentRunner
from config import HydraConfig
from epic import EpicCompletionChecker
from events import EventBus, EventType, HydraEvent
from issue_store import IssueStore
from models import (
    GitHubIssue,
    JudgeResult,
    PRInfo,
    ReviewResult,
    ReviewVerdict,
    WorkerStatus,
)
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
from transcript_summarizer import TranscriptSummarizer
from verification import format_verification_issue_body
from verification_judge import VerificationJudge
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
        store: IssueStore,
        agents: AgentRunner | None = None,
        event_bus: EventBus | None = None,
        retrospective: RetrospectiveCollector | None = None,
        ac_generator: AcceptanceCriteriaGenerator | None = None,
        verification_judge: VerificationJudge | None = None,
        transcript_summarizer: TranscriptSummarizer | None = None,
        epic_checker: EpicCompletionChecker | None = None,
    ) -> None:
        self._config = config
        self._state = state
        self._worktrees = worktrees
        self._reviewers = reviewers
        self._prs = prs
        self._stop_event = stop_event
        self._store = store
        self._agents = agents
        self._bus = event_bus or EventBus()
        self._retrospective = retrospective
        self._ac_generator = ac_generator
        self._verification_judge = verification_judge
        self._summarizer = transcript_summarizer
        self._epic_checker = epic_checker
        self._insights = ReviewInsightStore(config.repo_root / ".hydra" / "memory")
        self._active_issues: set[int] = set()

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
                self._state.set_active_issue_numbers(list(self._active_issues))
                self._store.mark_active(pr.issue_number, "review")
                try:
                    return await self._review_one_inner(idx, pr, issue_map)
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
                    self._state.set_active_issue_numbers(list(self._active_issues))
                    self._store.mark_complete(pr.issue_number)

        tasks = [asyncio.create_task(_review_one(i, pr)) for i, pr in enumerate(prs)]
        for task in asyncio.as_completed(tasks):
            results.append(await task)

        return results

    async def _review_one_inner(
        self,
        idx: int,
        pr: PRInfo,
        issue_map: dict[int, GitHubIssue],
    ) -> ReviewResult:
        """Core review logic for a single PR — called inside the semaphore."""
        await self._publish_review_status(pr, idx, "start")

        issue = issue_map.get(pr.issue_number)
        if issue is None:
            return ReviewResult(
                pr_number=pr.number,
                issue_number=pr.issue_number,
                summary="Issue not found",
            )

        wt_path = self._config.worktree_base / f"issue-{pr.issue_number}"
        if not wt_path.exists():
            wt_path = await self._worktrees.create(pr.issue_number, pr.branch)

        # Merge main and push — returns False on unresolvable conflicts
        merged = await self._merge_with_main(pr, issue, wt_path, idx)
        if not merged:
            return ReviewResult(
                pr_number=pr.number,
                issue_number=pr.issue_number,
                summary="Merge conflicts with main — escalated to HITL",
            )

        diff = await self._prs.get_pr_diff(pr.number)
        result = await self._run_and_post_review(pr, issue, wt_path, diff, idx)

        self._state.mark_pr(pr.number, result.verdict.value)
        self._state.mark_issue(pr.issue_number, "reviewed")
        self._state.record_review_verdict(result.verdict.value, result.fixes_made)
        if result.duration_seconds > 0:
            self._state.record_review_duration(result.duration_seconds)
        await self._record_review_insight(result)

        # Verdict-specific handling
        skip_worktree_cleanup = False
        if result.verdict == ReviewVerdict.APPROVE and pr.number > 0:
            await self._handle_approved_merge(pr, issue, result, diff, idx)
        elif result.verdict in (
            ReviewVerdict.REQUEST_CHANGES,
            ReviewVerdict.COMMENT,
        ):
            skip_worktree_cleanup = await self._handle_rejected_review(pr, result, idx)

        if not skip_worktree_cleanup:
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

    async def _merge_with_main(
        self,
        pr: PRInfo,
        issue: GitHubIssue,
        wt_path: Path,
        worker_id: int,
    ) -> bool:
        """Merge main into the PR branch, resolving conflicts if needed.

        Returns True on success, False on failure (escalates to HITL).
        """
        await self._publish_review_status(pr, worker_id, "merge_main")
        merged = await self._worktrees.merge_main(wt_path, pr.branch)
        if not merged:
            logger.info(
                "PR #%d has conflicts with %s — running agent to resolve",
                pr.number,
                self._config.main_branch,
            )
            await self._publish_review_status(
                pr, worker_id, WorkerStatus.MERGE_FIX.value
            )
            merged = await self._resolve_merge_conflicts(
                pr, issue, wt_path, worker_id=worker_id
            )
        if merged:
            await self._prs.push_branch(wt_path, pr.branch)
            return True

        logger.warning(
            "PR #%d merge conflict resolution failed — escalating to HITL",
            pr.number,
        )
        await self._publish_review_status(pr, worker_id, "escalating")
        await self._escalate_to_hitl(
            pr.issue_number,
            pr.number,
            cause="Merge conflict with main branch",
            origin_label=self._config.review_label[0],
            comment=(
                f"**Merge conflicts** with "
                f"`{self._config.main_branch}` could not be "
                "resolved automatically. "
                "Escalating to human review."
            ),
            event_cause="merge_conflict",
        )
        return False

    async def _run_and_post_review(
        self,
        pr: PRInfo,
        issue: GitHubIssue,
        wt_path: Path,
        diff: str,
        worker_id: int,
    ) -> ReviewResult:
        """Run the reviewer, push fixes, post summary, submit formal review."""
        result = await self._reviewers.review(
            pr, issue, wt_path, diff, worker_id=worker_id
        )

        if result.fixes_made:
            await self._prs.push_branch(wt_path, pr.branch)

        if result.summary and pr.number > 0:
            await self._prs.post_pr_comment(pr.number, result.summary)

        if pr.number > 0 and result.verdict != ReviewVerdict.APPROVE:
            try:
                await self._prs.submit_review(pr.number, result.verdict, result.summary)
            except SelfReviewError:
                logger.info(
                    "Skipping formal %s review on own PR #%d"
                    " — already posted as comment",
                    result.verdict.value,
                    pr.number,
                )

        if result.verdict == ReviewVerdict.APPROVE:
            result = await self._check_adversarial_threshold(
                pr, issue, wt_path, diff, result, worker_id
            )

        return result

    async def _handle_approved_merge(
        self,
        pr: PRInfo,
        issue: GitHubIssue,
        result: ReviewResult,
        diff: str,
        worker_id: int,
    ) -> None:
        """Attempt merge for an approved PR (with optional CI gate)."""
        should_merge = True
        if self._config.max_ci_fix_attempts > 0:
            should_merge = await self.wait_and_fix_ci(
                pr,
                issue,
                self._config.worktree_base / f"issue-{pr.issue_number}",
                result,
                worker_id,
            )
        if not should_merge:
            return

        await self._publish_review_status(pr, worker_id, "merging")
        success = await self._prs.merge_pr(pr.number)
        if success:
            result.merged = True
            self._state.mark_issue(pr.issue_number, "merged")
            self._state.record_pr_merged()
            self._state.record_issue_completed()
            if result.ci_fix_attempts > 0:
                self._state.record_ci_fix_rounds(result.ci_fix_attempts)
            self._state.reset_review_attempts(pr.issue_number)
            self._state.reset_issue_attempts(pr.issue_number)
            self._state.clear_review_feedback(pr.issue_number)
            for lbl in self._config.review_label:
                await self._prs.remove_label(pr.issue_number, lbl)
            await self._prs.add_labels(pr.issue_number, [self._config.fixed_label[0]])
            await self._run_post_merge_hooks(pr, issue, result, diff)
        else:
            logger.warning("PR #%d merge failed — escalating to HITL", pr.number)
            await self._publish_review_status(pr, worker_id, "escalating")
            await self._escalate_to_hitl(
                pr.issue_number,
                pr.number,
                cause="PR merge failed on GitHub",
                origin_label=self._config.review_label[0],
                comment=(
                    "**Merge failed** — PR could not be merged. "
                    "Escalating to human review."
                ),
                event_cause="merge_failed",
            )

    async def _run_post_merge_hooks(
        self,
        pr: PRInfo,
        issue: GitHubIssue,
        result: ReviewResult,
        diff: str,
    ) -> None:
        """Run non-blocking post-merge hooks (AC, retrospective, judge, epic)."""
        if self._ac_generator:
            try:
                await self._ac_generator.generate(
                    issue_number=pr.issue_number,
                    pr_number=pr.number,
                    issue=issue,
                    diff=diff,
                )
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Acceptance criteria generation failed for issue #%d",
                    pr.issue_number,
                    exc_info=True,
                )
        if self._retrospective:
            try:
                await self._retrospective.record(
                    issue_number=pr.issue_number,
                    pr_number=pr.number,
                    review_result=result,
                )
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Retrospective record failed for issue #%d",
                    pr.issue_number,
                    exc_info=True,
                )
        if self._verification_judge:
            try:
                await self._verification_judge.judge(
                    issue_number=pr.issue_number,
                    pr_number=pr.number,
                    diff=diff,
                )
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Verification judge failed for issue #%d",
                    pr.issue_number,
                    exc_info=True,
                )

        # Check if any parent epics can be closed
        if self._epic_checker:
            try:
                await self._epic_checker.check_and_close_epics(
                    pr.issue_number,
                )
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Epic completion check failed for issue #%d",
                    pr.issue_number,
                    exc_info=True,
                )

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
        self._state.record_ci_fix_rounds(result.ci_fix_attempts)
        await self._publish_review_status(pr, worker_id, "escalating")
        cause = f"CI failed after {result.ci_fix_attempts} fix attempt(s)"
        await self._escalate_to_hitl(
            issue.number,
            pr.number,
            cause=cause,
            origin_label=self._config.review_label[0],
            comment=(
                f"**CI failed** after {result.ci_fix_attempts} fix attempt(s).\n\n"
                f"Last failure: {summary}\n\n"
                f"PR not merged — escalating to human review."
            ),
            event_cause="ci_failed",
            extra_event_data={"ci_fix_attempts": result.ci_fix_attempts},
        )
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
                issue_num = await self._prs.create_issue(title, body, labels)
                if issue_num:
                    self._state.set_hitl_origin(
                        issue_num, self._config.improve_label[0]
                    )
                    self._state.set_hitl_cause(
                        issue_num, f"Recurring review pattern: {desc}"
                    )
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

    async def _escalate_to_hitl(
        self,
        issue_number: int,
        pr_number: int,
        cause: str,
        origin_label: str,
        *,
        comment: str,
        post_on_pr: bool = True,
        event_cause: str = "",
        extra_event_data: dict[str, object] | None = None,
    ) -> None:
        """Record HITL escalation state, swap labels, post comment, publish event."""
        self._state.set_hitl_origin(issue_number, origin_label)
        self._state.set_hitl_cause(issue_number, cause)
        self._state.record_hitl_escalation()

        for lbl in self._config.review_label:
            await self._prs.remove_label(issue_number, lbl)
            await self._prs.remove_pr_label(pr_number, lbl)
        await self._prs.add_labels(issue_number, [self._config.hitl_label[0]])
        await self._prs.add_pr_labels(pr_number, [self._config.hitl_label[0]])

        if post_on_pr:
            await self._prs.post_pr_comment(pr_number, comment)
        else:
            await self._prs.post_comment(issue_number, comment)

        event_data: dict[str, object] = {
            "issue": issue_number,
            "pr": pr_number,
            "status": "escalated",
            "role": "reviewer",
            "cause": event_cause or cause,
        }
        if extra_event_data:
            event_data.update(extra_event_data)
        await self._bus.publish(
            HydraEvent(type=EventType.HITL_ESCALATION, data=event_data)
        )

    @staticmethod
    def _count_review_findings(summary: str) -> int:
        """Count the number of findings in a review summary.

        Counts bullet points (``-`` or ``*``) and numbered items (``1.``)
        as individual findings.
        """
        lines = summary.strip().splitlines()
        count = 0
        for line in lines:
            stripped = line.strip()
            # Bullet points ("- text", "* text") or numbered items ("1. text")
            if re.match(r"^[-*]\s+\S", stripped) or re.match(r"^\d+\.\s+\S", stripped):
                count += 1
        return count

    async def _check_adversarial_threshold(
        self,
        pr: PRInfo,
        issue: GitHubIssue,
        wt_path: Path,
        diff: str,
        result: ReviewResult,
        worker_id: int,
    ) -> ReviewResult:
        """Re-review if APPROVE has too few findings and no justification.

        Returns the (possibly updated) review result.
        """
        min_findings = self._config.min_review_findings
        if min_findings <= 0:
            return result

        findings_count = self._count_review_findings(result.summary)
        has_justification = "THOROUGH_REVIEW_COMPLETE" in result.transcript

        if findings_count >= min_findings or has_justification:
            return result

        # Under threshold with no justification — re-review once
        logger.info(
            "PR #%d: APPROVE with only %d findings (min %d) and no "
            "THOROUGH_REVIEW_COMPLETE — re-reviewing",
            pr.number,
            findings_count,
            min_findings,
        )
        await self._publish_review_status(pr, worker_id, "re_reviewing")

        re_result = await self._reviewers.review(
            pr, issue, wt_path, diff, worker_id=worker_id
        )

        # If re-review still under threshold without justification, accept
        # but log a warning (don't loop forever)
        re_count = self._count_review_findings(re_result.summary)
        re_justified = "THOROUGH_REVIEW_COMPLETE" in re_result.transcript
        if re_count < min_findings and not re_justified:
            logger.warning(
                "PR #%d: re-review still under threshold (%d/%d) "
                "with no justification — accepting anyway",
                pr.number,
                re_count,
                min_findings,
            )

        # If reviewer made fixes during re-review, push them
        if re_result.fixes_made:
            await self._prs.push_branch(wt_path, pr.branch)

        return re_result

    async def _handle_rejected_review(
        self,
        pr: PRInfo,
        result: ReviewResult,
        worker_id: int,
    ) -> bool:
        """Handle REQUEST_CHANGES or COMMENT verdict with retry logic.

        Returns *True* if the worktree should be preserved (retry case),
        *False* if the worktree should be destroyed (HITL escalation).
        """
        max_attempts = self._config.max_review_fix_attempts
        attempts = self._state.get_review_attempts(pr.issue_number)

        if attempts < max_attempts:
            # Under cap: re-queue for implementation with feedback
            new_count = self._state.increment_review_attempts(pr.issue_number)
            self._state.set_review_feedback(pr.issue_number, result.summary)

            # Swap labels: review → ready (issue and PR)
            for lbl in self._config.review_label:
                await self._prs.remove_label(pr.issue_number, lbl)
                await self._prs.remove_pr_label(pr.number, lbl)
            await self._prs.add_labels(pr.issue_number, [self._config.ready_label[0]])
            await self._prs.add_pr_labels(pr.number, [self._config.ready_label[0]])

            await self._prs.post_comment(
                pr.issue_number,
                f"**Review requested changes** (attempt {new_count}/{max_attempts}). "
                f"Re-queuing for implementation with feedback.",
            )

            logger.info(
                "PR #%d: %s verdict — retry %d/%d, re-queuing issue #%d",
                pr.number,
                result.verdict.value,
                new_count,
                max_attempts,
                pr.issue_number,
            )
            return True  # Preserve worktree
        else:
            # Cap exceeded: escalate to HITL
            logger.warning(
                "PR #%d: review fix cap (%d) exceeded — escalating issue #%d to HITL",
                pr.number,
                max_attempts,
                pr.issue_number,
            )
            await self._publish_review_status(pr, worker_id, "escalating")
            await self._escalate_to_hitl(
                pr.issue_number,
                pr.number,
                cause=f"Review fix cap exceeded after {max_attempts} attempt(s)",
                origin_label=self._config.review_label[0],
                comment=(
                    f"**Review fix cap exceeded** — {max_attempts} review fix "
                    f"attempt(s) exhausted. Escalating to human review."
                ),
                post_on_pr=False,
                event_cause="review_fix_cap_exceeded",
            )
            return False  # Destroy worktree

    async def _create_verification_issue(
        self,
        issue: GitHubIssue,
        pr: PRInfo,
        judge_result: JudgeResult,
    ) -> int:
        """Create a linked verification issue for human review.

        Returns the created issue number (0 on failure).
        """
        title = f"Verify: {issue.title}"
        if len(title) > 256:
            title = title[:253] + "..."

        body = format_verification_issue_body(judge_result, issue, pr)
        label = self._config.hitl_label[0]
        issue_number = await self._prs.create_issue(title, body, [label])

        if issue_number > 0:
            self._state.set_verification_issue(issue.number, issue_number)
            logger.info(
                "Created verification issue #%d for issue #%d (PR #%d)",
                issue_number,
                issue.number,
                pr.number,
            )

        return issue_number

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
        from conflict_prompt import build_conflict_prompt

        if self._agents is None:
            logger.warning(
                "No agent runner available for conflict resolution on PR #%d",
                pr.number,
            )
            return False

        max_attempts = self._config.max_merge_conflict_fix_attempts
        last_error: str | None = None

        # Fetch context once before the attempt loop
        pr_changed_files = await self._prs.get_pr_diff_names(pr.number)
        main_commits = await self._worktrees.get_main_commits_since_diverge(wt_path)

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
            await self._publish_review_status(
                pr, worker_id, WorkerStatus.MERGE_FIX.value
            )

            try:
                prompt = build_conflict_prompt(
                    issue, pr_changed_files, main_commits, last_error, attempt
                )
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
                    await self._maybe_summarize_conflict(
                        transcript, issue.number, pr.number
                    )
                    return True

                last_error = error_msg
                logger.warning(
                    "Conflict resolution attempt %d/%d failed for PR #%d: %s",
                    attempt,
                    max_attempts,
                    pr.number,
                    error_msg[:200] if error_msg else "",
                )
                # Summarize final failed attempt
                if attempt == max_attempts:
                    await self._maybe_summarize_conflict(
                        transcript, issue.number, pr.number
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

    async def _maybe_summarize_conflict(
        self, transcript: str, issue_number: int, pr_number: int
    ) -> None:
        """Summarize a conflict resolution transcript if summarizer is available."""
        if self._summarizer is None:
            return
        try:
            await self._summarizer.summarize_and_publish(
                transcript=transcript,
                issue_number=issue_number,
                phase="conflict_resolution",
            )
        except Exception:
            logger.exception(
                "Failed to file transcript summary for conflict resolution on PR #%d",
                pr_number,
            )

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
