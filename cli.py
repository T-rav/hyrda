"""CLI entry point for Hydra."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from typing import Any

from config import HydraConfig
from log import setup_logging
from orchestrator import HydraOrchestrator


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="hydra",
        description="Hydra — Intent in. Software out.",
    )

    parser.add_argument(
        "--ready-label",
        default=None,
        help="GitHub issue labels to filter by, comma-separated (default: hydra-ready)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Number of issues per batch (default: 15)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Max concurrent implementation agents (default: 2)",
    )
    parser.add_argument(
        "--max-planners",
        type=int,
        default=None,
        help="Max concurrent planning agents (default: 1)",
    )
    parser.add_argument(
        "--max-reviewers",
        type=int,
        default=None,
        help="Max concurrent review agents (default: 1)",
    )
    parser.add_argument(
        "--max-budget-usd",
        type=float,
        default=None,
        help="USD budget cap per implementation agent (0 = unlimited, default: 0)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model for implementation agents (default: sonnet)",
    )
    parser.add_argument(
        "--review-model",
        default=None,
        help="Model for review agents (default: opus)",
    )
    parser.add_argument(
        "--review-budget-usd",
        type=float,
        default=None,
        help="USD budget cap per review agent (0 = unlimited, default: 0)",
    )
    parser.add_argument(
        "--ci-check-timeout",
        type=int,
        default=None,
        help="Seconds to wait for CI checks (default: 600)",
    )
    parser.add_argument(
        "--ci-poll-interval",
        type=int,
        default=None,
        help="Seconds between CI status polls (default: 30)",
    )
    parser.add_argument(
        "--max-ci-fix-attempts",
        type=int,
        default=None,
        help="Max CI fix-and-retry cycles; 0 disables CI wait (default: 2)",
    )
    parser.add_argument(
        "--review-label",
        default=None,
        help="Labels for issues/PRs under review, comma-separated (default: hydra-review)",
    )
    parser.add_argument(
        "--hitl-label",
        default=None,
        help="Labels for human-in-the-loop escalation, comma-separated (default: hydra-hitl)",
    )
    parser.add_argument(
        "--fixed-label",
        default=None,
        help="Labels applied after PR is merged, comma-separated (default: hydra-fixed)",
    )
    parser.add_argument(
        "--find-label",
        default=None,
        help="Labels for new issues to discover, comma-separated (default: hydra-find)",
    )
    parser.add_argument(
        "--planner-label",
        default=None,
        help="Labels for issues needing plans, comma-separated (default: hydra-plan)",
    )
    parser.add_argument(
        "--planner-model",
        default=None,
        help="Model for planning agents (default: opus)",
    )
    parser.add_argument(
        "--planner-budget-usd",
        type=float,
        default=None,
        help="USD budget cap per planning agent (0 = unlimited, default: 0)",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="GitHub repo owner/name (auto-detected from git remote if omitted)",
    )
    parser.add_argument(
        "--main-branch",
        default=None,
        help="Base branch name (default: main)",
    )
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=None,
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
        default=None,
        help="GitHub token for gh CLI auth (overrides HYDRA_GH_TOKEN and shell GH_TOKEN)",
    )
    parser.add_argument(
        "--git-user-name",
        default=None,
        help="Git user.name for worktree commits; uses global git config if unset",
    )
    parser.add_argument(
        "--git-user-email",
        default=None,
        help="Git user.email for worktree commits; uses global git config if unset",
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
    """Convert parsed CLI args into a :class:`HydraConfig`.

    Only explicitly-provided CLI values are passed through;
    HydraConfig supplies all defaults.
    """
    kwargs: dict[str, Any] = {}

    # 1) Simple 1:1 fields (CLI attr name == HydraConfig field name)
    for field in (
        "batch_size",
        "max_workers",
        "max_planners",
        "max_reviewers",
        "max_budget_usd",
        "model",
        "review_model",
        "review_budget_usd",
        "ci_check_timeout",
        "ci_poll_interval",
        "max_ci_fix_attempts",
        "planner_model",
        "planner_budget_usd",
        "repo",
        "main_branch",
        "dashboard_port",
        "gh_token",
        "git_user_name",
        "git_user_email",
    ):
        val = getattr(args, field)
        if val is not None:
            kwargs[field] = val

    # 2) Label fields: CLI string → list[str]
    for field in (
        "ready_label",
        "review_label",
        "hitl_label",
        "fixed_label",
        "find_label",
        "planner_label",
    ):
        val = getattr(args, field)
        if val is not None:
            kwargs[field] = _parse_label_arg(val)

    # 3) Boolean flags (only pass when explicitly set)
    if args.no_dashboard:
        kwargs["dashboard_enabled"] = False
    if args.dry_run:
        kwargs["dry_run"] = True

    return HydraConfig(**kwargs)


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

        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        try:
            await stop_event.wait()
        finally:
            if dashboard._orchestrator and dashboard._orchestrator.running:
                await dashboard._orchestrator.stop()
            await dashboard.stop()
    else:
        orchestrator = HydraOrchestrator(config)

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig, lambda: asyncio.create_task(orchestrator.stop())
            )

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
