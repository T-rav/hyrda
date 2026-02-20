"""Tests for cli.py — parse_args, build_config, and signal handling."""

from __future__ import annotations

import asyncio
import signal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cli import _parse_label_arg, _run_main, build_config, parse_args

# ---------------------------------------------------------------------------
# _parse_label_arg
# ---------------------------------------------------------------------------


class TestParseLabelArg:
    """Tests for the _parse_label_arg helper."""

    def test_single_label(self) -> None:
        assert _parse_label_arg("hydra-ready") == ["hydra-ready"]

    def test_comma_separated_labels(self) -> None:
        assert _parse_label_arg("foo,bar") == ["foo", "bar"]

    def test_strips_whitespace(self) -> None:
        assert _parse_label_arg(" foo , bar ") == ["foo", "bar"]

    def test_empty_string_returns_empty_list(self) -> None:
        assert _parse_label_arg("") == []


# ---------------------------------------------------------------------------
# parse_args — defaults
# ---------------------------------------------------------------------------


class TestParseArgs:
    """Tests for parse_args() default values."""

    def test_no_args_returns_none_for_optional_fields(self) -> None:
        """All non-boolean CLI args should default to None when no args given."""
        args = parse_args([])

        none_fields = [
            "ready_label",
            "batch_size",
            "max_workers",
            "max_planners",
            "max_reviewers",
            "max_hitl_workers",
            "max_budget_usd",
            "model",
            "review_model",
            "review_budget_usd",
            "ci_check_timeout",
            "ci_poll_interval",
            "max_ci_fix_attempts",
            "review_label",
            "hitl_label",
            "hitl_active_label",
            "fixed_label",
            "find_label",
            "planner_label",
            "planner_model",
            "planner_budget_usd",
            "repo",
            "main_branch",
            "dashboard_port",
            "gh_token",
        ]
        for field in none_fields:
            assert getattr(args, field) is None, f"{field} should be None"

    def test_store_true_flags_default_to_false(self) -> None:
        """Boolean store_true flags should default to False."""
        args = parse_args([])
        assert args.dry_run is False
        assert args.no_dashboard is False
        assert args.verbose is False
        assert args.clean is False

    def test_log_file_default(self) -> None:
        """--log-file should default to .hydra/logs/hydra.log."""
        args = parse_args([])
        assert args.log_file == ".hydra/logs/hydra.log"

    def test_log_file_explicit_value(self) -> None:
        """An explicit --log-file value should be preserved."""
        args = parse_args(["--log-file", "/tmp/custom.log"])
        assert args.log_file == "/tmp/custom.log"

    def test_explicit_int_arg_preserved(self) -> None:
        args = parse_args(["--batch-size", "10"])
        assert args.batch_size == 10

    def test_explicit_float_arg_preserved(self) -> None:
        args = parse_args(["--max-budget-usd", "5.5"])
        assert args.max_budget_usd == pytest.approx(5.5)

    def test_explicit_string_arg_preserved(self) -> None:
        args = parse_args(["--model", "haiku"])
        assert args.model == "haiku"

    def test_explicit_label_arg_preserved(self) -> None:
        args = parse_args(["--ready-label", "foo,bar"])
        assert args.ready_label == "foo,bar"


# ---------------------------------------------------------------------------
# build_config — integration with HydraConfig
# ---------------------------------------------------------------------------


class TestBuildConfig:
    """Tests for build_config() converting CLI args → HydraConfig."""

    def test_no_cli_args_uses_hydra_config_defaults(self) -> None:
        """With no CLI args, build_config should produce HydraConfig defaults."""
        args = parse_args([])
        cfg = build_config(args)

        # Check key defaults match HydraConfig
        assert cfg.ready_label == ["hydra-ready"]
        assert cfg.batch_size == 15
        assert cfg.max_workers == 2
        assert cfg.max_planners == 1
        assert cfg.max_reviewers == 3
        assert cfg.max_hitl_workers == 1
        assert cfg.hitl_active_label == ["hydra-hitl-active"]
        assert cfg.max_budget_usd == pytest.approx(0)
        assert cfg.model == "sonnet"
        assert cfg.review_model == "opus"
        assert cfg.review_budget_usd == pytest.approx(0)
        assert cfg.ci_check_timeout == 600
        assert cfg.ci_poll_interval == 30
        assert cfg.max_ci_fix_attempts == 2
        assert cfg.review_label == ["hydra-review"]
        assert cfg.hitl_label == ["hydra-hitl"]
        assert cfg.fixed_label == ["hydra-fixed"]
        assert cfg.find_label == ["hydra-find"]
        assert cfg.planner_label == ["hydra-plan"]
        assert cfg.planner_model == "opus"
        assert cfg.planner_budget_usd == pytest.approx(0)
        assert cfg.main_branch == "main"
        assert cfg.dashboard_port == 5555
        assert cfg.dashboard_enabled is True
        assert cfg.dry_run is False

    def test_explicit_cli_arg_overrides_default(self) -> None:
        """An explicit CLI arg should override the HydraConfig default."""
        args = parse_args(["--batch-size", "10"])
        cfg = build_config(args)

        assert cfg.batch_size == 10
        # Other fields remain at defaults
        assert cfg.max_workers == 2
        assert cfg.model == "sonnet"

    def test_label_arg_parsed_to_list(self) -> None:
        """A comma-separated label CLI arg should become a list."""
        args = parse_args(["--ready-label", "foo,bar"])
        cfg = build_config(args)

        assert cfg.ready_label == ["foo", "bar"]

    def test_no_dashboard_flag_sets_dashboard_disabled(self) -> None:
        """--no-dashboard should set dashboard_enabled=False."""
        args = parse_args(["--no-dashboard"])
        cfg = build_config(args)

        assert cfg.dashboard_enabled is False

    def test_dry_run_flag(self) -> None:
        """--dry-run should set dry_run=True."""
        args = parse_args(["--dry-run"])
        cfg = build_config(args)

        assert cfg.dry_run is True

    def test_multiple_args_combined(self) -> None:
        """Multiple CLI args should all land in the config correctly."""
        args = parse_args(
            [
                "--batch-size",
                "5",
                "--model",
                "haiku",
                "--max-workers",
                "4",
                "--dry-run",
                "--review-label",
                "review-me,check-me",
            ]
        )
        cfg = build_config(args)

        assert cfg.batch_size == 5
        assert cfg.model == "haiku"
        assert cfg.max_workers == 4
        assert cfg.dry_run is True
        assert cfg.review_label == ["review-me", "check-me"]
        # Non-specified fields remain at defaults
        assert cfg.max_planners == 1
        assert cfg.main_branch == "main"

    def test_gh_token_passed_through(self) -> None:
        """--gh-token value should land in config."""
        args = parse_args(["--gh-token", "ghp_abc123"])
        cfg = build_config(args)

        assert cfg.gh_token == "ghp_abc123"

    def test_repo_passed_through(self) -> None:
        """--repo value should land in config."""
        args = parse_args(["--repo", "org/repo"])
        cfg = build_config(args)

        assert cfg.repo == "org/repo"

    def test_all_label_fields_parsed(self) -> None:
        """All label CLI args should be split into lists."""
        args = parse_args(
            [
                "--ready-label",
                "a,b",
                "--review-label",
                "c",
                "--hitl-label",
                "d,e",
                "--hitl-active-label",
                "d2,e2",
                "--fixed-label",
                "f",
                "--find-label",
                "g,h",
                "--planner-label",
                "i",
            ]
        )
        cfg = build_config(args)

        assert cfg.ready_label == ["a", "b"]
        assert cfg.review_label == ["c"]
        assert cfg.hitl_label == ["d", "e"]
        assert cfg.hitl_active_label == ["d2", "e2"]
        assert cfg.fixed_label == ["f"]
        assert cfg.find_label == ["g", "h"]
        assert cfg.planner_label == ["i"]

    def test_planner_model_passed_through(self) -> None:
        args = parse_args(["--planner-model", "sonnet"])
        cfg = build_config(args)
        assert cfg.planner_model == "sonnet"

    def test_ci_fields_passed_through(self) -> None:
        args = parse_args(
            [
                "--ci-check-timeout",
                "300",
                "--ci-poll-interval",
                "10",
                "--max-ci-fix-attempts",
                "3",
            ]
        )
        cfg = build_config(args)
        assert cfg.ci_check_timeout == 300
        assert cfg.ci_poll_interval == 10
        assert cfg.max_ci_fix_attempts == 3

    def test_dashboard_port_passed_through(self) -> None:
        args = parse_args(["--dashboard-port", "8080"])
        cfg = build_config(args)
        assert cfg.dashboard_port == 8080

    def test_budget_fields_passed_through(self) -> None:
        args = parse_args(
            [
                "--max-budget-usd",
                "10.5",
                "--review-budget-usd",
                "5.0",
                "--planner-budget-usd",
                "3.0",
            ]
        )
        cfg = build_config(args)
        assert cfg.max_budget_usd == pytest.approx(10.5)
        assert cfg.review_budget_usd == pytest.approx(5.0)
        assert cfg.planner_budget_usd == pytest.approx(3.0)

    def test_min_plan_words_passed_through(self) -> None:
        args = parse_args(["--min-plan-words", "300"])
        cfg = build_config(args)
        assert cfg.min_plan_words == 300

    def test_lite_plan_labels_passed_through(self) -> None:
        args = parse_args(["--lite-plan-labels", "hotfix,patch,minor"])
        cfg = build_config(args)
        assert cfg.lite_plan_labels == ["hotfix", "patch", "minor"]

    def test_git_user_name_passed_through(self) -> None:
        args = parse_args(["--git-user-name", "T-rav-Hydra-Ops"])
        cfg = build_config(args)
        assert cfg.git_user_name == "T-rav-Hydra-Ops"

    def test_git_user_email_passed_through(self) -> None:
        args = parse_args(["--git-user-email", "bot@example.com"])
        cfg = build_config(args)
        assert cfg.git_user_email == "bot@example.com"

    def test_max_hitl_workers_passed_through(self) -> None:
        args = parse_args(["--max-hitl-workers", "3"])
        cfg = build_config(args)
        assert cfg.max_hitl_workers == 3

    def test_hitl_active_label_passed_through(self) -> None:
        args = parse_args(["--hitl-active-label", "my-active"])
        cfg = build_config(args)
        assert cfg.hitl_active_label == ["my-active"]

    def test_git_identity_defaults_to_none_in_parse_args(self) -> None:
        args = parse_args([])
        assert args.git_user_name is None
        assert args.git_user_email is None

    def test_max_issue_attempts_cli_arg(self) -> None:
        args = parse_args(["--max-issue-attempts", "5"])
        cfg = build_config(args)
        assert cfg.max_issue_attempts == 5

    def test_max_issue_attempts_defaults_to_none_in_parse_args(self) -> None:
        args = parse_args([])
        assert args.max_issue_attempts is None


# ---------------------------------------------------------------------------
# _run_main — signal handler registration
# ---------------------------------------------------------------------------


class TestRunMainSignalHandlers:
    """Tests for signal handler registration in _run_main()."""

    @pytest.mark.asyncio
    async def test_headless_registers_signal_handlers(self) -> None:
        """In headless mode, SIGINT and SIGTERM handlers are registered."""
        from tests.helpers import ConfigFactory

        config = ConfigFactory.create(dashboard_enabled=False)

        registered_signals: list[int] = []
        mock_loop = MagicMock()
        mock_loop.add_signal_handler = MagicMock(
            side_effect=lambda sig, cb: registered_signals.append(sig)
        )

        mock_orch = AsyncMock()
        mock_orch.run = AsyncMock()
        mock_orch.stop = AsyncMock()

        with (
            patch("cli.HydraOrchestrator", return_value=mock_orch),
            patch("asyncio.get_running_loop", return_value=mock_loop),
        ):
            await _run_main(config)

        assert signal.SIGINT in registered_signals
        assert signal.SIGTERM in registered_signals

    @pytest.mark.asyncio
    async def test_headless_sigint_calls_orchestrator_stop(self) -> None:
        """Simulating SIGINT callback should trigger orchestrator.stop()."""
        from tests.helpers import ConfigFactory

        config = ConfigFactory.create(dashboard_enabled=False)

        handlers: dict[int, object] = {}

        def capture_handler(sig: int, cb: object) -> None:
            handlers[sig] = cb

        mock_loop = MagicMock()
        mock_loop.add_signal_handler = MagicMock(side_effect=capture_handler)

        mock_orch = AsyncMock()
        mock_orch.stop = AsyncMock()

        async def fake_run() -> None:
            # Simulate signal arriving during run
            cb = handlers.get(signal.SIGINT)
            if cb:
                cb()  # type: ignore[operator]
            # Give the stop task a chance to run
            await asyncio.sleep(0)

        mock_orch.run = fake_run

        with (
            patch("cli.HydraOrchestrator", return_value=mock_orch),
            patch("asyncio.get_running_loop", return_value=mock_loop),
        ):
            await _run_main(config)

        mock_orch.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_dashboard_registers_signal_handlers(self) -> None:
        """In dashboard mode, SIGINT and SIGTERM handlers are registered."""
        from tests.helpers import ConfigFactory

        config = ConfigFactory.create(dashboard_enabled=True)

        registered_signals: list[int] = []

        real_loop = asyncio.get_running_loop()

        def tracking_add(sig: int, cb: object) -> None:
            registered_signals.append(sig)
            # Actually set the event so _run_main unblocks
            if callable(cb):
                cb()

        mock_dashboard = AsyncMock()
        mock_dashboard._orchestrator = None
        mock_dashboard.start = AsyncMock()
        mock_dashboard.stop = AsyncMock()

        with (
            patch.object(real_loop, "add_signal_handler", side_effect=tracking_add),
            patch("dashboard.HydraDashboard", return_value=mock_dashboard),
        ):
            await _run_main(config)

        assert signal.SIGINT in registered_signals
        assert signal.SIGTERM in registered_signals

    @pytest.mark.asyncio
    async def test_dashboard_sigint_stops_orchestrator(self) -> None:
        """In dashboard mode, SIGINT should stop the orchestrator if running."""
        from tests.helpers import ConfigFactory

        config = ConfigFactory.create(dashboard_enabled=True)

        real_loop = asyncio.get_running_loop()

        mock_orch = AsyncMock()
        mock_orch.running = True
        mock_orch.stop = AsyncMock()

        mock_dashboard = AsyncMock()
        mock_dashboard._orchestrator = mock_orch
        mock_dashboard.start = AsyncMock()
        mock_dashboard.stop = AsyncMock()

        def trigger_stop(sig: int, cb: object) -> None:
            if sig == signal.SIGINT and callable(cb):
                cb()

        with (
            patch.object(real_loop, "add_signal_handler", side_effect=trigger_stop),
            patch("dashboard.HydraDashboard", return_value=mock_dashboard),
        ):
            await _run_main(config)

        mock_orch.stop.assert_called_once()
        mock_dashboard.stop.assert_called_once()
