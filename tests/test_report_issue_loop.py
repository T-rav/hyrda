"""Tests for the ReportIssueLoop background worker."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import PendingReport
from report_issue_loop import ReportIssueLoop
from state import StateTracker
from tests.helpers import make_bg_loop_deps


def _make_loop(
    tmp_path: Path,
    *,
    enabled: bool = True,
    dry_run: bool = False,
) -> tuple[ReportIssueLoop, asyncio.Event, StateTracker, MagicMock]:
    """Build a ReportIssueLoop with test-friendly defaults."""
    deps = make_bg_loop_deps(tmp_path, enabled=enabled)

    if dry_run:
        object.__setattr__(deps.config, "dry_run", True)

    state = StateTracker(tmp_path / "state.json")
    pr_manager = MagicMock()
    pr_manager.save_screenshot_to_temp = AsyncMock(
        return_value="/tmp/hydraflow-screenshot.png"
    )
    pr_manager.create_issue = AsyncMock(return_value=123)
    runner = MagicMock()

    loop = ReportIssueLoop(
        config=deps.config,
        state=state,
        pr_manager=pr_manager,
        event_bus=deps.bus,
        stop_event=deps.stop_event,
        status_cb=deps.status_cb,
        enabled_cb=deps.enabled_cb,
        sleep_fn=deps.sleep_fn,
        runner=runner,
    )
    return loop, deps.stop_event, state, pr_manager


class TestReportIssueLoopDoWork:
    """Tests for ReportIssueLoop._do_work."""

    @pytest.mark.asyncio
    async def test_no_pending_reports_returns_none(self, tmp_path: Path) -> None:
        """When no reports are queued, _do_work returns None (no-op)."""
        loop, _stop, _state, _pr = _make_loop(tmp_path)
        result = await loop._do_work()
        assert result is None

    @pytest.mark.asyncio
    async def test_pending_report_dequeues_and_invokes_agent(
        self, tmp_path: Path
    ) -> None:
        """A queued report is dequeued and the agent CLI is invoked."""
        loop, _stop, state, _pr = _make_loop(tmp_path)
        report = PendingReport(description="Button is broken")
        state.enqueue_report(report)

        with patch(
            "report_issue_loop.stream_claude_process", new_callable=AsyncMock
        ) as mock_stream:
            mock_stream.return_value = "https://github.com/acme/repo/issues/77"
            result = await loop._do_work()

        assert result is not None
        assert result["processed"] == 1
        assert result["report_id"] == report.id
        assert result["issue_number"] == 77
        mock_stream.assert_awaited_once()
        _pr.create_issue.assert_not_awaited()
        assert mock_stream.call_args[1]["gh_token"] == loop._config.gh_token
        # Queue should be empty after processing
        assert state.dequeue_report() is None

    @pytest.mark.asyncio
    async def test_screenshot_saved_before_agent(self, tmp_path: Path) -> None:
        """When a screenshot is present, it is saved before invoking the agent."""
        loop, _stop, state, pr_mgr = _make_loop(tmp_path)
        report = PendingReport(
            description="UI glitch",
            screenshot_base64="iVBORw0KGgo=",
        )
        state.enqueue_report(report)

        with patch(
            "report_issue_loop.stream_claude_process", new_callable=AsyncMock
        ) as mock_stream:
            mock_stream.return_value = "done"
            await loop._do_work()

        pr_mgr.save_screenshot_to_temp.assert_awaited_once_with("iVBORw0KGgo=")

    @pytest.mark.asyncio
    async def test_empty_screenshot_skips_temp_save(self, tmp_path: Path) -> None:
        """When screenshot_base64 is empty, temp save is skipped."""
        loop, _stop, state, pr_mgr = _make_loop(tmp_path)
        report = PendingReport(description="No screenshot")
        state.enqueue_report(report)

        with patch(
            "report_issue_loop.stream_claude_process", new_callable=AsyncMock
        ) as mock_stream:
            mock_stream.return_value = "done"
            await loop._do_work()

        pr_mgr.save_screenshot_to_temp.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_agent_failure_falls_back_to_direct_issue_create(
        self, tmp_path: Path
    ) -> None:
        """If agent execution fails, fallback direct issue creation is attempted."""
        loop, _stop, state, pr_mgr = _make_loop(tmp_path)
        report = PendingReport(description="Crash test")
        state.enqueue_report(report)

        with patch(
            "report_issue_loop.stream_claude_process", new_callable=AsyncMock
        ) as mock_stream:
            mock_stream.side_effect = RuntimeError("agent died")
            result = await loop._do_work()

        assert result is not None
        assert result["processed"] == 1
        assert result["report_id"] == report.id
        assert result["issue_number"] == 123
        pr_mgr.create_issue.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_error_when_agent_and_fallback_both_fail(
        self, tmp_path: Path
    ) -> None:
        """When neither agent nor fallback creates an issue, report stays failed."""
        loop, _stop, state, pr_mgr = _make_loop(tmp_path)
        pr_mgr.create_issue.return_value = 0
        report = PendingReport(description="Still broken")
        state.enqueue_report(report)

        with patch(
            "report_issue_loop.stream_claude_process", new_callable=AsyncMock
        ) as mock_stream:
            mock_stream.return_value = "no url in output"
            result = await loop._do_work()

        assert result is not None
        assert result["error"] is True
        assert result["processed"] == 0
        assert result["report_id"] == report.id
        pr_mgr.create_issue.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dry_run_returns_none(self, tmp_path: Path) -> None:
        """In dry-run mode, _do_work returns early without processing."""
        loop, _stop, state, _pr = _make_loop(tmp_path, dry_run=True)
        report = PendingReport(description="Dry run test")
        state.enqueue_report(report)

        result = await loop._do_work()
        assert result is None
        # Report should still be in the queue
        assert state.dequeue_report() is not None

    @pytest.mark.asyncio
    async def test_prompt_includes_description(self, tmp_path: Path) -> None:
        """The agent prompt includes the report description."""
        loop, _stop, state, _pr = _make_loop(tmp_path)
        report = PendingReport(description="Login page 500 error")
        state.enqueue_report(report)

        with patch(
            "report_issue_loop.stream_claude_process", new_callable=AsyncMock
        ) as mock_stream:
            mock_stream.return_value = "done"
            await loop._do_work()

        call_kwargs = mock_stream.call_args
        prompt = call_kwargs.kwargs.get("prompt", "")
        assert "Login page 500 error" in prompt
        assert "gh issue create" in prompt

    @pytest.mark.asyncio
    async def test_environment_included_in_prompt(self, tmp_path: Path) -> None:
        """Environment details are included in the agent prompt body."""
        loop, _stop, state, _pr = _make_loop(tmp_path)
        report = PendingReport(
            description="Bug",
            environment={
                "source": "monitoring",
                "app_version": "2.0.0",
                "orchestrator_status": "running",
            },
        )
        state.enqueue_report(report)

        with patch(
            "report_issue_loop.stream_claude_process", new_callable=AsyncMock
        ) as mock_stream:
            mock_stream.return_value = "done"
            await loop._do_work()

        prompt = mock_stream.call_args.kwargs.get("prompt", "")
        assert "monitoring" in prompt
        assert "2.0.0" in prompt

    @pytest.mark.asyncio
    async def test_prompt_includes_screenshot_path(self, tmp_path: Path) -> None:
        """When a screenshot is saved, its path is embedded in the prompt markdown."""
        loop, _stop, state, pr_mgr = _make_loop(tmp_path)
        report = PendingReport(
            description="UI bug", screenshot_base64="iVBORw0KGgoAAAANSUhEUgAA"
        )
        state.enqueue_report(report)
        pr_mgr.save_screenshot_to_temp.return_value = "/tmp/test-screenshot.png"

        with patch(
            "report_issue_loop.stream_claude_process", new_callable=AsyncMock
        ) as mock_stream:
            mock_stream.return_value = "done"
            await loop._do_work()

        prompt = mock_stream.call_args.kwargs.get("prompt", "")
        assert "![Screenshot](/tmp/test-screenshot.png)" in prompt


class TestReportIssueLoopInterval:
    """Tests for interval configuration."""

    def test_default_interval_from_config(self, tmp_path: Path) -> None:
        """The default interval comes from config.report_issue_interval."""
        loop, _stop, _state, _pr = _make_loop(tmp_path)
        assert loop._get_default_interval() == 30
