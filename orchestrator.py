"""Main orchestrator loop — plan, implement, review, cleanup, repeat."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from pathlib import Path

from agent import AgentRunner
from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from models import (
    GitHubIssue,
    Phase,
    PlanResult,
    PRInfo,
    ReviewResult,
    ReviewVerdict,
    WorkerResult,
    WorkerStatus,
)
from planner import PlannerRunner
from pr_manager import PRManager
from reviewer import ReviewRunner
from state import StateTracker
from subprocess_util import run_subprocess
from triage import TriageRunner
from worktree import WorktreeManager

logger = logging.getLogger("hydra.orchestrator")


class HydraOrchestrator:
    """Coordinates the full Hydra pipeline.

    Each phase runs as an independent polling loop so new work is picked
    up continuously — planner, implementer, and reviewer all run
    concurrently without waiting on each other.
    """

    def __init__(
        self,
        config: HydraConfig,
        event_bus: EventBus | None = None,
        state: StateTracker | None = None,
    ) -> None:
        self._config = config
        self._bus = event_bus or EventBus()
        self._state = state or StateTracker(config.state_file)
        self._worktrees = WorktreeManager(config)
        self._agents = AgentRunner(config, self._bus)
        self._planners = PlannerRunner(config, self._bus)
        self._prs = PRManager(config, self._bus)
        self._reviewers = ReviewRunner(config, self._bus)
        self._triage = TriageRunner(config, self._bus)
        self._dashboard: object | None = None
        # Pending human-input requests: {issue_number: question}
        self._human_input_requests: dict[int, str] = {}
        # Fulfilled human-input responses: {issue_number: answer}
        self._human_input_responses: dict[int, str] = {}
        # In-memory tracking of issues active in this run (avoids double-processing)
        self._active_issues: set[int] = set()
        # Stop mechanism for dashboard control
        self._stop_event = asyncio.Event()
        self._running = False

    @property
    def event_bus(self) -> EventBus:
        """Expose event bus for dashboard integration."""
        return self._bus

    @property
    def state(self) -> StateTracker:
        """Expose state for dashboard integration."""
        return self._state

    @property
    def running(self) -> bool:
        """Whether the orchestrator is currently executing."""
        return self._running

    @property
    def run_status(self) -> str:
        """Return the current lifecycle status: idle, running, stopping, or done."""
        if self._stop_event.is_set() and self._running:
            return "stopping"
        if self._running:
            return "running"
        # Check if we finished naturally (DONE phase in history)
        for event in reversed(self._bus.get_history()):
            if (
                event.type == EventType.PHASE_CHANGE
                and event.data.get("phase") == Phase.DONE.value
            ):
                return "done"
        return "idle"

    @property
    def human_input_requests(self) -> dict[int, str]:
        """Pending questions for the human operator."""
        return self._human_input_requests

    def provide_human_input(self, issue_number: int, answer: str) -> None:
        """Provide an answer to a paused agent's question."""
        self._human_input_responses[issue_number] = answer
        self._human_input_requests.pop(issue_number, None)

    async def stop(self) -> None:
        """Signal the orchestrator to stop and kill active subprocesses."""
        self._stop_event.set()
        logger.info("Stop requested — terminating active processes")
        self._planners.terminate()
        self._agents.terminate()
        self._reviewers.terminate()
        await self._publish_status()

    # Alias for backward compatibility
    request_stop = stop

    def reset(self) -> None:
        """Reset the stop event so the orchestrator can be started again."""
        self._stop_event.clear()
        self._running = False
        self._active_issues.clear()

    async def _publish_status(self) -> None:
        """Broadcast the current orchestrator status to all subscribers."""
        await self._bus.publish(
            HydraEvent(
                type=EventType.ORCHESTRATOR_STATUS,
                data={"status": self.run_status},
            )
        )

    async def run(self) -> None:
        """Run three independent, continuous loops — plan, implement, review.

        Each loop polls for its own work on ``poll_interval`` and processes
        whatever it finds.  No phase blocks another; new issues are picked
        up as soon as they arrive.  Loops run until explicitly stopped.
        """
        self._stop_event.clear()
        self._running = True
        await self._publish_status()
        logger.info(
            "Hydra starting — repo=%s label=%s workers=%d poll=%ds",
            self._config.repo,
            ",".join(self._config.ready_label),
            self._config.max_workers,
            self._config.poll_interval,
        )

        await self._prs.ensure_labels_exist()

        try:
            await asyncio.gather(
                self._triage_loop(),
                self._plan_loop(),
                self._implement_loop(),
                self._review_loop(),
            )
        finally:
            self._running = False
            self._planners.terminate()
            self._agents.terminate()
            self._reviewers.terminate()
            await self._publish_status()
            logger.info("Hydra stopped")

    async def _triage_loop(self) -> None:
        """Continuously poll for find-labeled issues and triage them."""
        while not self._stop_event.is_set():
            await self._triage_find_issues()
            await self._sleep_or_stop(self._config.poll_interval)

    async def _plan_loop(self) -> None:
        """Continuously poll for planner-labeled issues."""
        while not self._stop_event.is_set():
            await self._triage_find_issues()
            await self._plan_issues()
            await self._sleep_or_stop(self._config.poll_interval)

    async def _implement_loop(self) -> None:
        """Continuously poll for ``hydra-ready`` issues and implement them."""
        while not self._stop_event.is_set():
            await self._implement_batch()
            await self._sleep_or_stop(self._config.poll_interval)

    async def _review_loop(self) -> None:
        """Continuously poll for ``hydra-review`` issues and review their PRs."""
        while not self._stop_event.is_set():
            prs, issues = await self._fetch_reviewable_prs()
            if prs:
                review_results = await self._review_prs(prs, issues)
                any_merged = any(r.merged for r in review_results)
                if any_merged:
                    await asyncio.sleep(5)
                    await self._prs.pull_main()
            await self._sleep_or_stop(self._config.poll_interval)

    async def _sleep_or_stop(self, seconds: int) -> None:
        """Sleep for *seconds*, waking early if stop is requested."""
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)

    # --- Phase implementations ---

    async def _fetch_issues_by_labels(
        self,
        labels: list[str],
        limit: int,
        exclude_labels: list[str] | None = None,
    ) -> list[GitHubIssue]:
        """Fetch open issues matching *any* of *labels*, deduplicated.

        If *labels* is empty but *exclude_labels* is provided, fetch all
        open issues and filter out those carrying any of the exclude labels.
        """
        if self._config.dry_run:
            logger.info(
                "[dry-run] Would fetch issues with labels=%r exclude=%r",
                labels,
                exclude_labels,
            )
            return []

        seen: dict[int, dict] = {}

        async def _query_label(label: str | None) -> None:
            cmd = [
                "gh",
                "issue",
                "list",
                "--repo",
                self._config.repo,
                "--limit",
                str(limit),
                "--json",
                "number,title,body,labels,comments,url",
            ]
            if label is not None:
                cmd += ["--label", label]
            try:
                raw = await run_subprocess(*cmd, gh_token=self._config.gh_token)
                for item in json.loads(raw):
                    seen.setdefault(item["number"], item)
            except (RuntimeError, json.JSONDecodeError, FileNotFoundError) as exc:
                logger.error("gh issue list failed for label=%r: %s", label, exc)

        if labels:
            await asyncio.gather(*[_query_label(lbl) for lbl in labels])
        elif exclude_labels:
            await _query_label(None)
            # Remove issues that carry any of the exclude labels
            exclude_set = set(exclude_labels)
            to_remove = []
            for num, raw in seen.items():
                raw_labels = {
                    (rl["name"] if isinstance(rl, dict) else str(rl))
                    for rl in raw.get("labels", [])
                }
                if raw_labels & exclude_set:
                    to_remove.append(num)
            for num in to_remove:
                del seen[num]
        else:
            return []

        issues = [GitHubIssue.model_validate(raw) for raw in seen.values()]
        return issues[:limit]

    async def _fetch_plan_issues(self) -> list[GitHubIssue]:
        """Fetch issues labeled with the planner label (e.g. ``hydra-plan``)."""
        if not self._config.planner_label:
            # No planner labels configured — fetch all open issues that are
            # not already in a downstream pipeline stage.
            exclude = list(
                {
                    *self._config.ready_label,
                    *self._config.review_label,
                    *self._config.hitl_label,
                    *self._config.fixed_label,
                }
            )
            issues = await self._fetch_issues_by_labels(
                [],
                self._config.batch_size,
                exclude_labels=exclude,
            )
        else:
            issues = await self._fetch_issues_by_labels(
                self._config.planner_label,
                self._config.batch_size,
            )
        logger.info("Fetched %d issues for planning", len(issues))
        return issues[: self._config.batch_size]

    async def _triage_find_issues(self) -> None:
        """Evaluate ``find_label`` issues and route them.

        Issues with enough context go to ``planner_label`` (planning).
        Issues lacking detail are escalated to ``hitl_label`` with a
        comment explaining what is missing so the dashboard surfaces
        them as "needs attention".
        """
        if not self._config.find_label:
            return

        issues = await self._fetch_issues_by_labels(
            self._config.find_label, self._config.batch_size
        )
        if not issues:
            return

        logger.info("Triaging %d found issues", len(issues))
        for issue in issues:
            if self._stop_event.is_set():
                logger.info("Stop requested — aborting triage loop")
                return

            result = await self._triage.evaluate(issue)

            if self._config.dry_run:
                continue

            # Remove find label regardless of outcome
            for lbl in self._config.find_label:
                await self._prs.remove_label(issue.number, lbl)

            if result.ready:
                await self._prs.add_labels(
                    issue.number, [self._config.planner_label[0]]
                )
                logger.info(
                    "Issue #%d triaged → %s (ready for planning)",
                    issue.number,
                    self._config.planner_label[0],
                )
            else:
                await self._prs.add_labels(issue.number, [self._config.hitl_label[0]])
                note = (
                    "## Needs More Information\n\n"
                    "This issue was picked up by Hydra but doesn't have "
                    "enough detail to begin planning.\n\n"
                    "**Missing:**\n"
                    + "\n".join(f"- {r}" for r in result.reasons)
                    + "\n\n"
                    "Please update the issue with more context and re-apply "
                    f"the `{self._config.find_label[0]}` label when ready.\n\n"
                    "---\n*Generated by Hydra Triage*"
                )
                await self._prs.post_comment(issue.number, note)
                logger.info(
                    "Issue #%d triaged → %s (needs attention: %s)",
                    issue.number,
                    self._config.hitl_label[0],
                    "; ".join(result.reasons),
                )

    async def _plan_issues(self) -> list[PlanResult]:
        """Run planning agents on issues labeled with the planner label."""
        issues = await self._fetch_plan_issues()
        if not issues:
            return []

        semaphore = asyncio.Semaphore(self._config.max_planners)
        results: list[PlanResult] = []

        async def _plan_one(idx: int, issue: GitHubIssue) -> PlanResult:
            if self._stop_event.is_set():
                return PlanResult(issue_number=issue.number, error="stopped")

            async with semaphore:
                if self._stop_event.is_set():
                    return PlanResult(issue_number=issue.number, error="stopped")

                result = await self._planners.plan(issue, worker_id=idx)

                if result.success and result.plan:
                    # Post plan + branch as comment on the issue
                    branch = self._config.branch_for_issue(issue.number)
                    comment_body = (
                        f"## Implementation Plan\n\n"
                        f"{result.plan}\n\n"
                        f"**Branch:** `{branch}`\n\n"
                        f"---\n"
                        f"*Generated by Hydra Planner*"
                    )
                    await self._prs.post_comment(issue.number, comment_body)

                    # Swap labels: remove planner label(s), add implementation label
                    for lbl in self._config.planner_label:
                        await self._prs.remove_label(issue.number, lbl)
                    await self._prs.add_labels(
                        issue.number, [self._config.ready_label[0]]
                    )

                    # File new issues discovered during planning
                    for new_issue in result.new_issues:
                        labels = new_issue.labels or (
                            [self._config.planner_label[0]]
                            if self._config.planner_label
                            else []
                        )
                        await self._prs.create_issue(
                            new_issue.title, new_issue.body, labels
                        )
                        self._state.record_issue_created()

                    logger.info(
                        "Plan posted and labels swapped for issue #%d",
                        issue.number,
                    )
                else:
                    logger.warning(
                        "Planning failed for issue #%d — skipping label swap",
                        issue.number,
                    )

                return result

        all_tasks = [
            asyncio.create_task(_plan_one(i, issue)) for i, issue in enumerate(issues)
        ]
        for task in asyncio.as_completed(all_tasks):
            results.append(await task)
            # Cancel remaining tasks if stop requested
            if self._stop_event.is_set():
                for t in all_tasks:
                    t.cancel()
                break

        return results

    async def _fetch_ready_issues(self) -> list[GitHubIssue]:
        """Fetch issues labeled ``hydra-ready`` for the implement phase.

        Returns up to ``2 * max_workers`` issues so the worker pool
        stays saturated.
        """
        queue_size = 2 * self._config.max_workers

        all_issues = await self._fetch_issues_by_labels(
            self._config.ready_label,
            queue_size,
        )
        # Only skip issues already active in this run (GitHub labels are
        # the source of truth — if it still has hydra-ready, it needs work)
        issues = [i for i in all_issues if i.number not in self._active_issues]
        for skipped in all_issues:
            if skipped.number in self._active_issues:
                logger.info("Skipping in-progress issue #%d", skipped.number)

        logger.info("Fetched %d issues to implement", len(issues))
        return issues[:queue_size]

    async def _fetch_reviewable_prs(
        self,
    ) -> tuple[list[PRInfo], list[GitHubIssue]]:
        """Fetch issues labeled ``hydra-review`` and resolve their open PRs.

        Returns ``(pr_infos, issues)`` so the reviewer has both.
        """
        all_issues = await self._fetch_issues_by_labels(
            self._config.review_label,
            self._config.batch_size,
        )
        # Only skip issues already active in this run
        issues = [i for i in all_issues if i.number not in self._active_issues]
        if not issues:
            return [], []

        # For each issue, look up the open PR on its branch
        pr_infos: list[PRInfo] = []
        for issue in issues:
            branch = self._config.branch_for_issue(issue.number)
            try:
                raw = await run_subprocess(
                    "gh",
                    "pr",
                    "list",
                    "--repo",
                    self._config.repo,
                    "--head",
                    branch,
                    "--state",
                    "open",
                    "--json",
                    "number,url,isDraft",
                    "--limit",
                    "1",
                    gh_token=self._config.gh_token,
                )
                prs_json = json.loads(raw)
                if prs_json:
                    pr_data = prs_json[0]
                    pr_infos.append(
                        PRInfo(
                            number=pr_data["number"],
                            issue_number=issue.number,
                            branch=branch,
                            url=pr_data.get("url", ""),
                            draft=pr_data.get("isDraft", False),
                        )
                    )
            except (RuntimeError, json.JSONDecodeError, KeyError) as exc:
                logger.warning("Could not find PR for issue #%d: %s", issue.number, exc)

        non_draft = [p for p in pr_infos if not p.draft and p.number > 0]
        logger.info("Fetched %d reviewable PRs", len(non_draft))
        return non_draft, issues

    async def _implement_batch(
        self,
    ) -> tuple[list[WorkerResult], list[GitHubIssue]]:
        """Fetch ready issues and run implementation agents concurrently.

        Returns ``(worker_results, issues)`` so the caller has access
        to the issue list for downstream phases.  The internal queue
        holds up to ``2 * max_workers`` issues.
        """
        issues = await self._fetch_ready_issues()
        if not issues:
            return [], []

        semaphore = asyncio.Semaphore(self._config.max_workers)
        results: list[WorkerResult] = []

        all_tasks = [
            asyncio.create_task(self._implement_one(i, issue, semaphore))
            for i, issue in enumerate(issues)
        ]
        for task in asyncio.as_completed(all_tasks):
            results.append(await task)
            # Cancel remaining tasks if stop requested
            if self._stop_event.is_set():
                for t in all_tasks:
                    t.cancel()
                break

        return results, issues

    async def _implement_one(
        self, idx: int, issue: GitHubIssue, semaphore: asyncio.Semaphore
    ) -> WorkerResult:
        """Run an implementation agent for a single issue.

        Handles worktree creation/reuse, agent execution, branch push,
        PR creation, and label management.
        """
        if self._stop_event.is_set():
            return WorkerResult(
                issue_number=issue.number,
                branch=self._config.branch_for_issue(issue.number),
                error="stopped",
            )

        async with semaphore:
            if self._stop_event.is_set():
                return WorkerResult(
                    issue_number=issue.number,
                    branch=self._config.branch_for_issue(issue.number),
                    error="stopped",
                )

            branch = self._config.branch_for_issue(issue.number)
            self._active_issues.add(issue.number)
            self._state.mark_issue(issue.number, "in_progress")
            self._state.set_branch(issue.number, branch)

            # Resume: reuse existing worktree if present
            wt_path = self._config.worktree_path_for_issue(issue.number)
            if wt_path.is_dir():
                logger.info("Resuming existing worktree for issue #%d", issue.number)
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

            result = await self._agents.run(issue, wt_path, branch, worker_id=idx)

            # Push final commits and create PR
            if result.worktree_path:
                pushed = await self._prs.push_branch(
                    Path(result.worktree_path), result.branch
                )
                if pushed:
                    draft = not result.success
                    pr = await self._prs.create_pr(issue, result.branch, draft=draft)
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
            # Release so the review loop can pick it up
            self._active_issues.discard(issue.number)
            return result

    async def _review_prs(
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

        tasks = [
            asyncio.create_task(self._review_one_pr(i, pr, issue_map, semaphore))
            for i, pr in enumerate(prs)
        ]
        for task in asyncio.as_completed(tasks):
            results.append(await task)

        return results

    async def _review_one_pr(
        self,
        idx: int,
        pr: PRInfo,
        issue_map: dict[int, GitHubIssue],
        semaphore: asyncio.Semaphore,
    ) -> ReviewResult:
        """Run a review agent for a single PR.

        Handles worktree setup, merge-main, conflict resolution, diff
        fetching, review execution, fix pushing, review submission,
        merge logic, and worktree cleanup.
        """
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
            wt_path = self._config.worktree_path_for_issue(pr.issue_number)
            if not wt_path.exists():
                # Create a fresh worktree for review
                wt_path = await self._worktrees.create(pr.issue_number, pr.branch)

            # Merge main into the branch before reviewing so we review
            # up-to-date code.  Merge keeps the push fast-forward
            # so no force-push is needed.
            merged_main = await self._worktrees.merge_main(wt_path, pr.branch)
            if not merged_main:
                # Conflicts — let the agent try to resolve them
                logger.info(
                    "PR #%d has conflicts with %s — running agent to resolve",
                    pr.number,
                    self._config.main_branch,
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
                await self._prs.post_pr_comment(
                    pr.number,
                    f"**Merge conflicts** with "
                    f"`{self._config.main_branch}` could not be "
                    "resolved automatically. "
                    "Escalating to human review.",
                )
                for lbl in self._config.review_label:
                    await self._prs.remove_label(pr.issue_number, lbl)
                    await self._prs.remove_pr_label(pr.number, lbl)
                await self._prs.add_labels(
                    pr.issue_number, [self._config.hitl_label[0]]
                )
                await self._prs.add_pr_labels(pr.number, [self._config.hitl_label[0]])
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
                await self._prs.submit_review(pr.number, result.verdict, result.summary)

            self._state.mark_pr(pr.number, result.verdict.value)
            self._state.mark_issue(pr.issue_number, "reviewed")

            # Merge immediately if approved (with optional CI gate)
            if result.verdict == ReviewVerdict.APPROVE and pr.number > 0:
                should_merge = True
                if self._config.max_ci_fix_attempts > 0:
                    should_merge = await self._wait_and_fix_ci(
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
                            pr.issue_number, [self._config.fixed_label[0]]
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

            # Release so issue can be re-reviewed if needed
            self._active_issues.discard(pr.issue_number)
            return result

    async def _resolve_merge_conflicts(
        self,
        pr: PRInfo,
        issue: GitHubIssue,
        wt_path: Path,
        worker_id: int,
    ) -> bool:
        """Use the implementation agent to resolve merge conflicts.

        Starts a merge (leaving conflict markers), runs the agent to
        resolve them, and verifies the result with ``make quality``.
        Returns *True* if the conflicts were resolved successfully.
        """
        # Start merge leaving conflict markers in place
        clean = await self._worktrees.start_merge_main(wt_path, pr.branch)
        if clean:
            # No conflicts after all (race / already resolved)
            return True

        try:
            await self._bus.publish(
                HydraEvent(
                    type=EventType.WORKER_UPDATE,
                    data={
                        "issue": issue.number,
                        "worker": worker_id,
                        "status": WorkerStatus.RUNNING.value,
                        "role": "conflict-resolver",
                    },
                )
            )

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

            cmd = self._agents._build_command(wt_path)
            await self._agents._execute(cmd, prompt, wt_path, issue.number)

            # Verify quality passes
            await self._bus.publish(
                HydraEvent(
                    type=EventType.WORKER_UPDATE,
                    data={
                        "issue": issue.number,
                        "worker": worker_id,
                        "status": WorkerStatus.TESTING.value,
                        "role": "conflict-resolver",
                    },
                )
            )
            success, _ = await self._agents._verify_result(wt_path, pr.branch)

            status = WorkerStatus.DONE if success else WorkerStatus.FAILED
            await self._bus.publish(
                HydraEvent(
                    type=EventType.WORKER_UPDATE,
                    data={
                        "issue": issue.number,
                        "worker": worker_id,
                        "status": status.value,
                        "role": "conflict-resolver",
                    },
                )
            )
            return success
        except Exception as exc:
            logger.error(
                "Conflict resolution agent failed for PR #%d: %s",
                pr.number,
                exc,
            )
            await self._bus.publish(
                HydraEvent(
                    type=EventType.WORKER_UPDATE,
                    data={
                        "issue": issue.number,
                        "worker": worker_id,
                        "status": WorkerStatus.FAILED.value,
                        "role": "conflict-resolver",
                    },
                )
            )
            # Abort the merge to leave a clean state
            await self._worktrees.abort_merge(wt_path)
            return False

    async def _wait_and_fix_ci(
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
            await self._prs.remove_pr_label(pr.number, lbl)
        await self._prs.add_labels(issue.number, [self._config.hitl_label[0]])
        await self._prs.add_pr_labels(pr.number, [self._config.hitl_label[0]])
        return False

    async def _set_phase(self, phase: Phase) -> None:
        """Update the current phase and broadcast."""
        logger.info("Phase: %s", phase.value)
        await self._bus.publish(
            HydraEvent(
                type=EventType.PHASE_CHANGE,
                data={"phase": phase.value},
            )
        )
