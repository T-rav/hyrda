"""CLI entry point for Hydra."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from config import HydraConfig
from log import setup_logging
from orchestrator import HydraOrchestrator


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="hydra",
        description="Hydra — Parallel Claude Code Issue Processor",
    )

    parser.add_argument(
        "--ready-label",
        default="hydra-ready",
        help="GitHub issue labels to filter by, comma-separated (default: hydra-ready)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=15,
        help="Number of issues per batch (default: 15)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=2,
        help="Max concurrent implementation agents (default: 2)",
    )
    parser.add_argument(
        "--max-planners",
        type=int,
        default=1,
        help="Max concurrent planning agents (default: 1)",
    )
    parser.add_argument(
        "--max-reviewers",
        type=int,
        default=1,
        help="Max concurrent review agents (default: 1)",
    )
    parser.add_argument(
        "--max-budget-usd",
        type=float,
        default=0,
        help="USD budget cap per implementation agent (0 = unlimited, default: 0)",
    )
    parser.add_argument(
        "--model",
        default="sonnet",
        help="Model for implementation agents (default: sonnet)",
    )
    parser.add_argument(
        "--review-model",
        default="opus",
        help="Model for review agents (default: opus)",
    )
    parser.add_argument(
        "--review-budget-usd",
        type=float,
        default=0,
        help="USD budget cap per review agent (0 = unlimited, default: 0)",
    )
    parser.add_argument(
        "--ci-check-timeout",
        type=int,
        default=600,
        help="Seconds to wait for CI checks (default: 600)",
    )
    parser.add_argument(
        "--ci-poll-interval",
        type=int,
        default=30,
        help="Seconds between CI status polls (default: 30)",
    )
    parser.add_argument(
        "--max-ci-fix-attempts",
        type=int,
        default=2,
        help="Max CI fix-and-retry cycles; 0 disables CI wait (default: 2)",
    )
    parser.add_argument(
        "--review-label",
        default="hydra-review",
        help="Labels for issues/PRs under review, comma-separated (default: hydra-review)",
    )
    parser.add_argument(
        "--hitl-label",
        default="hydra-hitl",
        help="Labels for human-in-the-loop escalation, comma-separated (default: hydra-hitl)",
    )
    parser.add_argument(
        "--fixed-label",
        default="hydra-fixed",
        help="Labels applied after PR is merged, comma-separated (default: hydra-fixed)",
    )
    parser.add_argument(
        "--find-label",
        default="hydra-find",
        help="Labels for new issues to discover, comma-separated (default: hydra-find)",
    )
    parser.add_argument(
        "--planner-label",
        default="hydra-plan",
        help="Labels for issues needing plans, comma-separated (default: hydra-plan)",
    )
    parser.add_argument(
        "--planner-model",
        default="opus",
        help="Model for planning agents (default: opus)",
    )
    parser.add_argument(
        "--planner-budget-usd",
        type=float,
        default=0,
        help="USD budget cap per planning agent (0 = unlimited, default: 0)",
    )
    parser.add_argument(
        "--repo",
        default="",
        help="GitHub repo owner/name (auto-detected from git remote if omitted)",
    )
    parser.add_argument(
        "--main-branch",
        default="main",
        help="Base branch name (default: main)",
    )
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=5555,
        help="Dashboard web UI port (default: 5555)",
    )
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Disable the live web dashboard",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without executing (no agents, no git, no PRs)",
    )
    parser.add_argument(
        "--gh-token",
        default="",
        help="GitHub token for gh CLI auth (overrides HYDRA_GH_TOKEN and shell GH_TOKEN)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove all worktrees and state, then exit",
    )

    return parser.parse_args(argv)


def _parse_label_arg(value: str) -> list[str]:
    """Split a comma-separated label string into a list."""
    return [part.strip() for part in value.split(",") if part.strip()]


def build_config(args: argparse.Namespace) -> HydraConfig:
    """Convert parsed CLI args into a :class:`HydraConfig`."""
    return HydraConfig(
        ready_label=_parse_label_arg(args.ready_label),
        batch_size=args.batch_size,
        max_workers=args.max_workers,
        max_planners=args.max_planners,
        max_reviewers=args.max_reviewers,
        max_budget_usd=args.max_budget_usd,
        model=args.model,
        review_model=args.review_model,
        review_budget_usd=args.review_budget_usd,
        ci_check_timeout=args.ci_check_timeout,
        ci_poll_interval=args.ci_poll_interval,
        max_ci_fix_attempts=args.max_ci_fix_attempts,
        review_label=_parse_label_arg(args.review_label),
        hitl_label=_parse_label_arg(args.hitl_label),
        fixed_label=_parse_label_arg(args.fixed_label),
        find_label=_parse_label_arg(args.find_label),
        planner_label=_parse_label_arg(args.planner_label),
        planner_model=args.planner_model,
        planner_budget_usd=args.planner_budget_usd,
        repo=args.repo,
        main_branch=args.main_branch,
        dashboard_port=args.dashboard_port,
        dashboard_enabled=not args.no_dashboard,
        dry_run=args.dry_run,
        gh_token=args.gh_token,
    )


async def _run_clean(config: HydraConfig) -> None:
    """Remove all worktrees and reset state."""
    from state import StateTracker
    from worktree import WorktreeManager

    logger = logging.getLogger("hydra")
    logger.info("Cleaning up all Hydra worktrees and state...")

    wt_mgr = WorktreeManager(config)
    await wt_mgr.destroy_all()

    state = StateTracker(config.state_file)
    state.reset()

    logger.info("Cleanup complete")


async def _run_main(config: HydraConfig) -> None:
    """Launch the orchestrator, optionally with the dashboard."""
    if config.dashboard_enabled:
        from dashboard import HydraDashboard
        from events import EventBus, EventType, HydraEvent
        from models import Phase
        from state import StateTracker

        bus = EventBus()
        state = StateTracker(config.state_file)

        dashboard = HydraDashboard(
            config=config,
            event_bus=bus,
            state=state,
        )
        await dashboard.start()

        # Publish idle phase so the UI shows the Start button
        await bus.publish(
            HydraEvent(
                type=EventType.PHASE_CHANGE,
                data={"phase": Phase.IDLE.value},
            )
        )

        # Block until Ctrl+C — the dashboard handles start/stop via API
        try:
            await asyncio.Event().wait()
        finally:
            await dashboard.stop()
    else:
        orchestrator = HydraOrchestrator(config)
        await orchestrator.run()


def main(argv: list[str] | None = None) -> None:
    """Entry point."""
    args = parse_args(argv)

    level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level=level, json_output=not args.verbose)

    config = build_config(args)

    if args.clean:
        asyncio.run(_run_clean(config))
        sys.exit(0)

    asyncio.run(_run_main(config))


if __name__ == "__main__":
    main()
