"""Main orchestrator loop — fetch, implement, push, review, merge, repeat."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from agent import AgentRunner
from config import HydraConfig
from events import EventBus, EventType, HydraEvent
from models import (
    BatchResult,
    GitHubIssue,
    Phase,
    PRInfo,
    ReviewResult,
    ReviewVerdict,
    WorkerResult,
)
from pr_manager import PRManager
from reviewer import ReviewRunner
from state import StateTracker
from worktree import WorktreeManager

logger = logging.getLogger("hydra.orchestrator")


class HydraOrchestrator:
    """Coordinates the full Hydra pipeline.

    Flow per batch:
      1. Fetch issues with the target label
      2. Spin up workers in isolated worktrees to implement
      3. Push branches and create PRs
      4. Review PRs with reviewer agents
      5. Auto-merge approved PRs
      6. Cleanup and loop
    """

    # Default: 2 reviewer agents (per user request)
    DEFAULT_MAX_REVIEWERS = 2

    def __init__(self, config: HydraConfig) -> None:
        self._config = config
        self._bus = EventBus()
        self._state = StateTracker(config.state_file)
        self._worktrees = WorktreeManager(config)
        self._agents = AgentRunner(config, self._bus)
        self._prs = PRManager(config, self._bus)
        self._reviewers = ReviewRunner(config, self._bus)
        self._dashboard: object | None = None
        # Pending human-input requests: {issue_number: question}
        self._human_input_requests: dict[int, str] = {}
        # Fulfilled human-input responses: {issue_number: answer}
        self._human_input_responses: dict[int, str] = {}

    @property
    def event_bus(self) -> EventBus:
        """Expose event bus for dashboard integration."""
        return self._bus

    @property
    def state(self) -> StateTracker:
        """Expose state for dashboard integration."""
        return self._state

    @property
    def human_input_requests(self) -> dict[int, str]:
        """Pending questions for the human operator."""
        return self._human_input_requests

    def provide_human_input(self, issue_number: int, answer: str) -> None:
        """Provide an answer to a paused agent's question."""
        self._human_input_responses[issue_number] = answer
        self._human_input_requests.pop(issue_number, None)

    async def run(self) -> None:
        """Execute the orchestrator loop until no issues remain."""
        logger.info(
            "Hydra starting — repo=%s label=%s", self._config.repo, self._config.label
        )

        while True:
            batch_num = self._state.increment_batch()
            await self._bus.publish(
                HydraEvent(
                    type=EventType.BATCH_START,
                    data={"batch": batch_num},
                )
            )

            # Phase 1: Fetch
            await self._set_phase(Phase.FETCH)
            issues = await self._fetch_issues()
            if not issues:
                logger.info("No more issues to process — stopping")
                break

            batch = BatchResult(batch_number=batch_num, issues=issues)

            # Phase 2: Implement
            await self._set_phase(Phase.IMPLEMENT)
            batch.worker_results = await self._implement_batch(issues)

            # Phase 3: Push & create PRs
            await self._set_phase(Phase.PUSH_PRS)
            batch.pr_infos = await self._push_and_create_prs(
                batch.worker_results, issues
            )

            # Phase 4: Review
            await self._set_phase(Phase.REVIEW)
            non_draft_prs = [
                pr for pr in batch.pr_infos if not pr.draft and pr.number > 0
            ]
            batch.review_results = await self._review_prs(non_draft_prs, issues)

            # Phase 5: Merge approved PRs
            await self._set_phase(Phase.MERGE)
            batch.merged_prs = await self._merge_approved(batch.review_results)

            # Phase 6: Cleanup
            await self._set_phase(Phase.CLEANUP)
            await self._cleanup_batch(issues)

            await self._bus.publish(
                HydraEvent(
                    type=EventType.BATCH_COMPLETE,
                    data={
                        "batch": batch_num,
                        "implemented": len(
                            [r for r in batch.worker_results if r.success]
                        ),
                        "prs_created": len([p for p in batch.pr_infos if p.number > 0]),
                        "approved": len(
                            [
                                r
                                for r in batch.review_results
                                if r.verdict == ReviewVerdict.APPROVE
                            ]
                        ),
                        "merged": len(batch.merged_prs),
                    },
                )
            )

        await self._set_phase(Phase.DONE)
        logger.info("Hydra complete")

    # --- Phase implementations ---

    async def _fetch_issues(self) -> list[GitHubIssue]:
        """Fetch a batch of issues matching the configured label."""
        if self._config.dry_run:
            logger.info(
                "[dry-run] Would fetch up to %d issues with label %r",
                self._config.batch_size,
                self._config.label,
            )
            return []

        try:
            env = {**os.environ}
            env.pop("CLAUDECODE", None)
            proc = await asyncio.create_subprocess_exec(
                "gh",
                "issue",
                "list",
                "--repo",
                self._config.repo,
                "--label",
                self._config.label,
                "--limit",
                str(self._config.batch_size),
                "--json",
                "number,title,body,labels,comments,url",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error("gh issue list failed: %s", stderr.decode())
                return []

            raw_issues = json.loads(stdout.decode())
        except (json.JSONDecodeError, FileNotFoundError) as exc:
            logger.error("Failed to fetch issues: %s", exc)
            return []

        issues: list[GitHubIssue] = []
        for raw in raw_issues:
            issue_num = raw["number"]
            if self._state.is_processed(issue_num):
                logger.info("Skipping already-processed issue #%d", issue_num)
                continue
            labels = [
                lbl["name"] if isinstance(lbl, dict) else str(lbl)
                for lbl in raw.get("labels", [])
            ]
            comments = []
            for c in raw.get("comments", []):
                if isinstance(c, dict):
                    comments.append(c.get("body", ""))
                else:
                    comments.append(str(c))
            issues.append(
                GitHubIssue(
                    number=issue_num,
                    title=raw.get("title", ""),
                    body=raw.get("body", ""),
                    labels=labels,
                    comments=comments,
                    url=raw.get("url", ""),
                )
            )

        logger.info("Fetched %d issues to process", len(issues))
        return issues[: self._config.batch_size]

    async def _implement_batch(self, issues: list[GitHubIssue]) -> list[WorkerResult]:
        """Run implementation agents concurrently (capped by max_workers)."""
        semaphore = asyncio.Semaphore(self._config.max_workers)
        results: list[WorkerResult] = []

        async def _worker(idx: int, issue: GitHubIssue) -> WorkerResult:
            async with semaphore:
                branch = f"agent/issue-{issue.number}"
                self._state.mark_issue(issue.number, "in_progress")
                self._state.set_branch(issue.number, branch)

                wt_path = await self._worktrees.create(issue.number, branch)
                self._state.set_worktree(issue.number, str(wt_path))

                result = await self._agents.run(issue, wt_path, branch, worker_id=idx)

                status = "success" if result.success else "failed"
                self._state.mark_issue(issue.number, status)
                return result

        tasks = [
            asyncio.create_task(_worker(i, issue)) for i, issue in enumerate(issues)
        ]
        for task in asyncio.as_completed(tasks):
            results.append(await task)

        return results

    async def _push_and_create_prs(
        self,
        results: list[WorkerResult],
        issues: list[GitHubIssue],
    ) -> list[PRInfo]:
        """Push branches and create PRs for all worker results."""
        issue_map = {i.number: i for i in issues}
        pr_infos: list[PRInfo] = []

        for result in results:
            issue = issue_map.get(result.issue_number)
            if issue is None:
                continue

            wt_path = Path(result.worktree_path) if result.worktree_path else None
            if wt_path is None:
                continue

            # Push the branch
            pushed = await self._prs.push_branch(wt_path, result.branch)
            if not pushed:
                logger.warning(
                    "Could not push branch for issue #%d", result.issue_number
                )
                continue

            # Create PR (draft if implementation failed)
            draft = not result.success
            pr = await self._prs.create_pr(issue, result.branch, draft=draft)
            pr_infos.append(pr)

            # Update labels
            if draft:
                await self._prs.add_labels(issue.number, ["needs-review"])
            await self._prs.remove_label(issue.number, self._config.label)
            await self._prs.add_labels(issue.number, ["agent-processed"])

        return pr_infos

    async def _review_prs(
        self,
        prs: list[PRInfo],
        issues: list[GitHubIssue],
    ) -> list[ReviewResult]:
        """Run reviewer agents on non-draft PRs (2 concurrent reviewers)."""
        if not prs:
            return []

        issue_map = {i.number: i for i in issues}
        semaphore = asyncio.Semaphore(self.DEFAULT_MAX_REVIEWERS)
        results: list[ReviewResult] = []

        async def _review_one(idx: int, pr: PRInfo) -> ReviewResult:
            async with semaphore:
                issue = issue_map.get(pr.issue_number)
                if issue is None:
                    return ReviewResult(
                        pr_number=pr.number,
                        issue_number=pr.issue_number,
                        summary="Issue not found",
                    )

                # Get the diff
                diff = await self._prs.get_pr_diff(pr.number)

                # The reviewer works in the same worktree as the implementation
                wt_path = self._config.worktree_base / f"issue-{pr.issue_number}"
                if not wt_path.exists():
                    # Create a fresh worktree for review
                    wt_path = await self._worktrees.create(pr.issue_number, pr.branch)

                result = await self._reviewers.review(
                    pr, issue, wt_path, diff, worker_id=idx
                )

                # If reviewer made fixes, push them
                if result.fixes_made:
                    await self._prs.push_branch(wt_path, pr.branch)

                self._state.mark_pr(pr.number, result.verdict.value)
                return result

        tasks = [asyncio.create_task(_review_one(i, pr)) for i, pr in enumerate(prs)]
        for task in asyncio.as_completed(tasks):
            results.append(await task)

        return results

    async def _merge_approved(self, reviews: list[ReviewResult]) -> list[int]:
        """Auto-merge PRs that reviewers approved."""
        merged: list[int] = []
        for review in reviews:
            if review.verdict == ReviewVerdict.APPROVE and review.pr_number > 0:
                success = await self._prs.merge_pr(review.pr_number)
                if success:
                    merged.append(review.pr_number)

        if merged:
            # Wait briefly for merges to process, then pull
            await asyncio.sleep(5)
            await self._prs.pull_main()

        return merged

    async def _cleanup_batch(self, issues: list[GitHubIssue]) -> None:
        """Destroy all worktrees from this batch."""
        for issue in issues:
            try:
                await self._worktrees.destroy(issue.number)
                self._state.remove_worktree(issue.number)
            except RuntimeError as exc:
                logger.warning(
                    "Could not destroy worktree for issue #%d: %s",
                    issue.number,
                    exc,
                )

    async def _set_phase(self, phase: Phase) -> None:
        """Update the current phase and broadcast."""
        logger.info("Phase: %s", phase.value)
        await self._bus.publish(
            HydraEvent(
                type=EventType.PHASE_CHANGE,
                data={"phase": phase.value},
            )
        )
