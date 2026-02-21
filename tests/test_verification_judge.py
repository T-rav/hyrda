"""Tests for verification_judge.py — LLM-as-judge validation of acceptance criteria."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from events import EventType
from models import (
    CriterionResult,
    CriterionVerdict,
    InstructionsQuality,
    JudgeVerdict,
)
from tests.helpers import ConfigFactory
from verification_judge import VerificationJudge

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_judge(config, event_bus):
    return VerificationJudge(config=config, event_bus=event_bus)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestModels:
    def test_criterion_verdict_values(self):
        assert CriterionVerdict.PASS == "pass"
        assert CriterionVerdict.FAIL == "fail"

    def test_instructions_quality_values(self):
        assert InstructionsQuality.READY == "ready"
        assert InstructionsQuality.NEEDS_REFINEMENT == "needs-refinement"

    def test_judge_verdict_defaults(self):
        verdict = JudgeVerdict(issue_number=42)
        assert verdict.issue_number == 42
        assert verdict.criteria_results == []
        assert verdict.all_criteria_pass is False
        assert verdict.instructions_quality == InstructionsQuality.NEEDS_REFINEMENT
        assert verdict.instructions_feedback == ""
        assert verdict.refined is False
        assert verdict.summary == ""
        assert verdict.transcript == ""

    def test_criterion_result_defaults(self):
        result = CriterionResult(criterion_id="AC-1")
        assert result.criterion_id == "AC-1"
        assert result.verdict == CriterionVerdict.FAIL
        assert result.reasoning == ""
        assert result.evidence == ""


# ---------------------------------------------------------------------------
# _build_command
# ---------------------------------------------------------------------------


class TestBuildCommand:
    def test_uses_review_model(self, config, event_bus):
        judge = _make_judge(config, event_bus)
        cmd = judge._build_command()
        assert "--model" in cmd
        model_idx = cmd.index("--model")
        assert cmd[model_idx + 1] == config.review_model

    def test_includes_read_only_tools(self, config, event_bus):
        judge = _make_judge(config, event_bus)
        cmd = judge._build_command()
        assert "--disallowedTools" in cmd
        idx = cmd.index("--disallowedTools")
        assert "Write" in cmd[idx + 1]
        assert "Edit" in cmd[idx + 1]
        assert "NotebookEdit" in cmd[idx + 1]

    def test_omits_budget_when_zero(self, tmp_path):
        cfg = ConfigFactory.create(
            review_budget_usd=0,
            repo_root=tmp_path / "repo",
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        judge = _make_judge(cfg, None)
        cmd = judge._build_command()
        assert "--max-budget-usd" not in cmd

    def test_includes_budget_when_positive(self, config, event_bus):
        judge = _make_judge(config, event_bus)
        cmd = judge._build_command()
        assert "--max-budget-usd" in cmd
        budget_idx = cmd.index("--max-budget-usd")
        assert cmd[budget_idx + 1] == str(config.review_budget_usd)

    def test_includes_stream_json_format(self, config, event_bus):
        judge = _make_judge(config, event_bus)
        cmd = judge._build_command()
        assert "--output-format" in cmd
        fmt_idx = cmd.index("--output-format")
        assert cmd[fmt_idx + 1] == "stream-json"


# ---------------------------------------------------------------------------
# _read_criteria_file
# ---------------------------------------------------------------------------


class TestReadCriteriaFile:
    def test_returns_content_when_exists(self, config, event_bus, tmp_path):
        cfg = ConfigFactory.create(repo_root=tmp_path)
        judge = _make_judge(cfg, event_bus)
        criteria_dir = tmp_path / ".hydra" / "verification"
        criteria_dir.mkdir(parents=True)
        criteria_file = criteria_dir / "issue-42.md"
        criteria_file.write_text("# Acceptance Criteria\n\nAC-1: Button renders")

        result = judge._read_criteria_file(42)
        assert result is not None
        assert "AC-1" in result

    def test_returns_none_when_missing(self, config, event_bus, tmp_path):
        cfg = ConfigFactory.create(repo_root=tmp_path)
        judge = _make_judge(cfg, event_bus)
        result = judge._read_criteria_file(999)
        assert result is None


# ---------------------------------------------------------------------------
# _build_code_validation_prompt
# ---------------------------------------------------------------------------


class TestBuildCodeValidationPrompt:
    def test_includes_diff(self, config, event_bus, issue):
        judge = _make_judge(config, event_bus)
        prompt = judge._build_code_validation_prompt(
            issue, "diff --git a/foo.py\n+new line", "AC-1: Button renders"
        )
        assert "diff --git a/foo.py" in prompt

    def test_includes_criteria(self, config, event_bus, issue):
        judge = _make_judge(config, event_bus)
        prompt = judge._build_code_validation_prompt(
            issue, "diff text", "AC-1: Button renders\nAC-2: Tests pass"
        )
        assert "AC-1: Button renders" in prompt
        assert "AC-2: Tests pass" in prompt

    def test_includes_output_markers(self, config, event_bus, issue):
        judge = _make_judge(config, event_bus)
        prompt = judge._build_code_validation_prompt(issue, "diff", "AC-1: test")
        assert "CRITERIA_START" in prompt
        assert "CRITERIA_END" in prompt


# ---------------------------------------------------------------------------
# _build_instructions_validation_prompt
# ---------------------------------------------------------------------------


class TestBuildInstructionsValidationPrompt:
    def test_includes_quality_markers(self, config, event_bus, issue):
        judge = _make_judge(config, event_bus)
        prompt = judge._build_instructions_validation_prompt(
            issue, "## Instructions\n1. Click the button"
        )
        assert "QUALITY:" in prompt
        assert "FEEDBACK:" in prompt

    def test_includes_evaluation_criteria(self, config, event_bus, issue):
        judge = _make_judge(config, event_bus)
        prompt = judge._build_instructions_validation_prompt(
            issue, "## Instructions\n1. Click button"
        )
        assert "specific" in prompt.lower() or "actionable" in prompt.lower()
        assert "expected" in prompt.lower()


# ---------------------------------------------------------------------------
# _parse_criteria_results
# ---------------------------------------------------------------------------


class TestParseCriteriaResults:
    def test_parse_pass_and_fail(self, config, event_bus):
        judge = _make_judge(config, event_bus)
        transcript = (
            "Some preamble\n"
            "CRITERIA_START\n"
            "AC-1: PASS — Button renders correctly, covered by test_button.py\n"
            "AC-2: FAIL — No test for edge case when input is empty\n"
            "AC-3: PASS — API endpoint returns 200 with correct schema\n"
            "CRITERIA_END\n"
            "SUMMARY: 2 of 3 criteria pass"
        )
        results = judge._parse_criteria_results(transcript)
        assert len(results) == 3
        assert results[0].criterion_id == "AC-1"
        assert results[0].verdict == CriterionVerdict.PASS
        assert "Button renders" in results[0].reasoning
        assert results[1].criterion_id == "AC-2"
        assert results[1].verdict == CriterionVerdict.FAIL
        assert results[2].verdict == CriterionVerdict.PASS

    def test_no_markers_returns_empty(self, config, event_bus):
        judge = _make_judge(config, event_bus)
        transcript = "This transcript has no criteria markers at all."
        results = judge._parse_criteria_results(transcript)
        assert results == []

    def test_handles_dash_separator(self, config, event_bus):
        judge = _make_judge(config, event_bus)
        transcript = "CRITERIA_START\nAC-1: PASS - Works correctly\nCRITERIA_END\n"
        results = judge._parse_criteria_results(transcript)
        assert len(results) == 1
        assert results[0].verdict == CriterionVerdict.PASS
        assert "Works correctly" in results[0].reasoning


# ---------------------------------------------------------------------------
# _parse_instructions_quality
# ---------------------------------------------------------------------------


class TestParseInstructionsQuality:
    def test_parse_quality_ready(self, config, event_bus):
        judge = _make_judge(config, event_bus)
        transcript = "QUALITY: READY\nFEEDBACK: Instructions are clear and actionable."
        quality, feedback = judge._parse_instructions_quality(transcript)
        assert quality == InstructionsQuality.READY
        assert "clear" in feedback.lower()

    def test_parse_quality_needs_refinement(self, config, event_bus):
        judge = _make_judge(config, event_bus)
        transcript = "QUALITY: NEEDS_REFINEMENT\nFEEDBACK: Steps 2 and 3 are too vague."
        quality, feedback = judge._parse_instructions_quality(transcript)
        assert quality == InstructionsQuality.NEEDS_REFINEMENT
        assert "vague" in feedback.lower()

    def test_no_match_defaults_to_needs_refinement(self, config, event_bus):
        judge = _make_judge(config, event_bus)
        transcript = "No structured output here."
        quality, feedback = judge._parse_instructions_quality(transcript)
        assert quality == InstructionsQuality.NEEDS_REFINEMENT
        assert feedback == ""


# ---------------------------------------------------------------------------
# _extract_refined_instructions
# ---------------------------------------------------------------------------


class TestExtractRefinedInstructions:
    def test_with_markers(self, config, event_bus):
        judge = _make_judge(config, event_bus)
        transcript = (
            "Here is the refinement.\n"
            "REFINED_INSTRUCTIONS_START\n"
            "1. Open the app at /settings\n"
            "2. Click the 'Dark Mode' toggle\n"
            "3. Verify the background changes to #1a1a2e\n"
            "REFINED_INSTRUCTIONS_END\n"
            "Done."
        )
        refined = judge._extract_refined_instructions(transcript)
        assert "Open the app" in refined
        assert "Dark Mode" in refined
        assert "REFINED_INSTRUCTIONS_START" not in refined
        assert "REFINED_INSTRUCTIONS_END" not in refined

    def test_no_markers_returns_empty(self, config, event_bus):
        judge = _make_judge(config, event_bus)
        transcript = "No refined instructions here."
        refined = judge._extract_refined_instructions(transcript)
        assert refined == ""


# ---------------------------------------------------------------------------
# judge() — integration tests
# ---------------------------------------------------------------------------


class TestJudge:
    @pytest.mark.asyncio
    async def test_no_criteria_file_returns_early(self, config, event_bus, issue):
        judge = _make_judge(config, event_bus)
        verdict = await judge.judge(issue, "some diff")
        assert verdict.issue_number == issue.number
        assert verdict.criteria_results == []
        assert verdict.summary == ""

    @pytest.mark.asyncio
    async def test_dry_run_returns_early(self, dry_config, event_bus, issue, tmp_path):
        cfg = ConfigFactory.create(
            dry_run=True,
            repo_root=tmp_path / "repo",
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        # Create criteria file
        criteria_dir = cfg.repo_root / ".hydra" / "verification"
        criteria_dir.mkdir(parents=True)
        (criteria_dir / "issue-42.md").write_text("AC-1: Test")

        judge = _make_judge(cfg, event_bus)
        verdict = await judge.judge(issue, "diff")
        assert verdict.summary == "Dry-run: judge skipped"

    @pytest.mark.asyncio
    async def test_success_all_pass(self, config, event_bus, issue, tmp_path):
        cfg = ConfigFactory.create(
            repo_root=tmp_path / "repo",
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        # Create criteria file
        criteria_dir = cfg.repo_root / ".hydra" / "verification"
        criteria_dir.mkdir(parents=True)
        (criteria_dir / "issue-42.md").write_text(
            "# Acceptance Criteria\nAC-1: Feature works\nAC-2: Tests pass\n\n"
            "## Verification Instructions\n1. Run tests\n2. Check output"
        )

        judge = _make_judge(cfg, event_bus)

        code_transcript = (
            "CRITERIA_START\n"
            "AC-1: PASS — Feature implemented correctly\n"
            "AC-2: PASS — All tests pass\n"
            "CRITERIA_END\n"
            "SUMMARY: All criteria met"
        )
        instructions_transcript = (
            "QUALITY: READY\nFEEDBACK: Instructions are clear and specific."
        )

        execute_calls = [
            AsyncMock(return_value=code_transcript),
            AsyncMock(return_value=instructions_transcript),
        ]
        call_count = 0

        async def mock_execute(cmd, prompt, issue_number):
            nonlocal call_count
            result = await execute_calls[call_count](cmd, prompt, issue_number)
            call_count += 1
            return result

        with patch.object(judge, "_execute", side_effect=mock_execute):
            verdict = await judge.judge(issue, "diff text")

        assert verdict.all_criteria_pass is True
        assert len(verdict.criteria_results) == 2
        assert all(c.verdict == CriterionVerdict.PASS for c in verdict.criteria_results)
        assert verdict.instructions_quality == InstructionsQuality.READY
        assert verdict.refined is False

    @pytest.mark.asyncio
    async def test_some_criteria_fail(self, config, event_bus, issue, tmp_path):
        cfg = ConfigFactory.create(
            repo_root=tmp_path / "repo",
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        criteria_dir = cfg.repo_root / ".hydra" / "verification"
        criteria_dir.mkdir(parents=True)
        (criteria_dir / "issue-42.md").write_text("AC-1: Feature\nAC-2: Tests")

        judge = _make_judge(cfg, event_bus)

        code_transcript = (
            "CRITERIA_START\n"
            "AC-1: PASS — Feature works\n"
            "AC-2: FAIL — Missing edge case test\n"
            "CRITERIA_END\n"
            "SUMMARY: 1 of 2 pass"
        )
        instructions_transcript = "QUALITY: READY\nFEEDBACK: Instructions are fine."

        call_count = 0

        async def mock_execute(cmd, prompt, issue_number):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return code_transcript
            return instructions_transcript

        with patch.object(judge, "_execute", side_effect=mock_execute):
            verdict = await judge.judge(issue, "diff text")

        assert verdict.all_criteria_pass is False
        assert len(verdict.criteria_results) == 2
        fail_count = sum(
            1 for c in verdict.criteria_results if c.verdict == CriterionVerdict.FAIL
        )
        assert fail_count == 1

    @pytest.mark.asyncio
    async def test_instructions_refined(self, config, event_bus, issue, tmp_path):
        cfg = ConfigFactory.create(
            repo_root=tmp_path / "repo",
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        criteria_dir = cfg.repo_root / ".hydra" / "verification"
        criteria_dir.mkdir(parents=True)
        (criteria_dir / "issue-42.md").write_text(
            "AC-1: Feature\n\n## Verification Instructions\n1. Test it"
        )

        judge = _make_judge(cfg, event_bus)

        code_transcript = (
            "CRITERIA_START\nAC-1: PASS — Feature works\nCRITERIA_END\nSUMMARY: Pass"
        )
        needs_refinement_transcript = (
            "QUALITY: NEEDS_REFINEMENT\nFEEDBACK: Step 1 is too vague."
        )
        refinement_transcript = (
            "REFINED_INSTRUCTIONS_START\n"
            "1. Open the app\n"
            "2. Click the button\n"
            "REFINED_INSTRUCTIONS_END"
        )
        ready_transcript = "QUALITY: READY\nFEEDBACK: Now clear and specific."

        call_count = 0

        async def mock_execute(cmd, prompt, issue_number):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return code_transcript
            if call_count == 2:
                return needs_refinement_transcript
            if call_count == 3:
                return refinement_transcript
            return ready_transcript

        with patch.object(judge, "_execute", side_effect=mock_execute):
            verdict = await judge.judge(issue, "diff text")

        assert verdict.refined is True
        assert verdict.instructions_quality == InstructionsQuality.READY

    @pytest.mark.asyncio
    async def test_refinement_still_fails(self, config, event_bus, issue, tmp_path):
        cfg = ConfigFactory.create(
            repo_root=tmp_path / "repo",
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        criteria_dir = cfg.repo_root / ".hydra" / "verification"
        criteria_dir.mkdir(parents=True)
        (criteria_dir / "issue-42.md").write_text(
            "AC-1: Feature\n\n## Verification Instructions\n1. Test it"
        )

        judge = _make_judge(cfg, event_bus)

        code_transcript = "CRITERIA_START\nAC-1: PASS — OK\nCRITERIA_END\nSUMMARY: Pass"
        needs_refinement = "QUALITY: NEEDS_REFINEMENT\nFEEDBACK: Still vague."
        refinement_transcript = (
            "REFINED_INSTRUCTIONS_START\n1. Try it\nREFINED_INSTRUCTIONS_END"
        )
        still_bad = "QUALITY: NEEDS_REFINEMENT\nFEEDBACK: Still not clear enough."

        call_count = 0

        async def mock_execute(cmd, prompt, issue_number):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return code_transcript
            if call_count == 2:
                return needs_refinement
            if call_count == 3:
                return refinement_transcript
            return still_bad

        with patch.object(judge, "_execute", side_effect=mock_execute):
            verdict = await judge.judge(issue, "diff text")

        assert verdict.refined is True
        assert verdict.instructions_quality == InstructionsQuality.NEEDS_REFINEMENT
        # Max 1 retry — should have called exactly 4 times
        assert call_count == 4

    @pytest.mark.asyncio
    async def test_saves_report(self, config, event_bus, issue, tmp_path):
        cfg = ConfigFactory.create(
            repo_root=tmp_path / "repo",
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        criteria_dir = cfg.repo_root / ".hydra" / "verification"
        criteria_dir.mkdir(parents=True)
        (criteria_dir / "issue-42.md").write_text("AC-1: Feature works")

        judge = _make_judge(cfg, event_bus)

        code_transcript = "CRITERIA_START\nAC-1: PASS — OK\nCRITERIA_END\nSUMMARY: Pass"
        instructions_transcript = "QUALITY: READY\nFEEDBACK: Good."

        call_count = 0

        async def mock_execute(cmd, prompt, issue_number):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return code_transcript
            return instructions_transcript

        with patch.object(judge, "_execute", side_effect=mock_execute):
            await judge.judge(issue, "diff text")

        report_path = cfg.repo_root / ".hydra" / "verification" / "issue-42-judge.md"
        assert report_path.exists()
        content = report_path.read_text()
        assert "AC-1" in content
        assert "PASS" in content.upper() or "pass" in content

    @pytest.mark.asyncio
    async def test_publishes_events(self, config, event_bus, issue, tmp_path):
        cfg = ConfigFactory.create(
            repo_root=tmp_path / "repo",
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        criteria_dir = cfg.repo_root / ".hydra" / "verification"
        criteria_dir.mkdir(parents=True)
        (criteria_dir / "issue-42.md").write_text("AC-1: Feature")

        judge = _make_judge(cfg, event_bus)

        code_transcript = "CRITERIA_START\nAC-1: PASS — OK\nCRITERIA_END\nSUMMARY: Pass"
        instructions_transcript = "QUALITY: READY\nFEEDBACK: Good."

        call_count = 0

        async def mock_execute(cmd, prompt, issue_number):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return code_transcript
            return instructions_transcript

        with patch.object(judge, "_execute", side_effect=mock_execute):
            await judge.judge(issue, "diff text")

        events = event_bus.get_history()
        judge_events = [e for e in events if e.type == EventType.VERIFICATION_JUDGE]
        assert len(judge_events) >= 2
        statuses = [e.data["status"] for e in judge_events]
        assert "judging" in statuses
        assert "done" in statuses


# ---------------------------------------------------------------------------
# _save_judge_report
# ---------------------------------------------------------------------------


class TestSaveJudgeReport:
    def test_creates_directory(self, event_bus, tmp_path):
        cfg = ConfigFactory.create(repo_root=tmp_path)
        judge = _make_judge(cfg, event_bus)
        verdict = JudgeVerdict(
            issue_number=42,
            criteria_results=[
                CriterionResult(
                    criterion_id="AC-1",
                    verdict=CriterionVerdict.PASS,
                    reasoning="Feature works",
                ),
            ],
            all_criteria_pass=True,
            instructions_quality=InstructionsQuality.READY,
            summary="All good",
        )
        judge._save_judge_report(42, verdict)
        report = tmp_path / ".hydra" / "verification" / "issue-42-judge.md"
        assert report.exists()

    def test_formats_criteria_table(self, event_bus, tmp_path):
        cfg = ConfigFactory.create(repo_root=tmp_path)
        judge = _make_judge(cfg, event_bus)
        verdict = JudgeVerdict(
            issue_number=42,
            criteria_results=[
                CriterionResult(
                    criterion_id="AC-1",
                    verdict=CriterionVerdict.PASS,
                    reasoning="Feature works",
                ),
                CriterionResult(
                    criterion_id="AC-2",
                    verdict=CriterionVerdict.FAIL,
                    reasoning="Missing test",
                ),
            ],
            all_criteria_pass=False,
            instructions_quality=InstructionsQuality.READY,
            summary="1 of 2 pass",
        )
        judge._save_judge_report(42, verdict)
        content = (
            tmp_path / ".hydra" / "verification" / "issue-42-judge.md"
        ).read_text()
        assert "AC-1" in content
        assert "AC-2" in content
        assert "PASS" in content or "pass" in content
        assert "FAIL" in content or "fail" in content

    def test_includes_instructions_quality(self, event_bus, tmp_path):
        cfg = ConfigFactory.create(repo_root=tmp_path)
        judge = _make_judge(cfg, event_bus)
        verdict = JudgeVerdict(
            issue_number=42,
            instructions_quality=InstructionsQuality.NEEDS_REFINEMENT,
            instructions_feedback="Steps are too vague",
            summary="Needs work",
        )
        judge._save_judge_report(42, verdict)
        content = (
            tmp_path / ".hydra" / "verification" / "issue-42-judge.md"
        ).read_text()
        assert "needs-refinement" in content.lower() or "NEEDS" in content


# ---------------------------------------------------------------------------
# _update_criteria_file
# ---------------------------------------------------------------------------


class TestUpdateCriteriaFile:
    def test_replaces_instructions_section(self, event_bus, tmp_path):
        cfg = ConfigFactory.create(repo_root=tmp_path)
        judge = _make_judge(cfg, event_bus)
        criteria_dir = tmp_path / ".hydra" / "verification"
        criteria_dir.mkdir(parents=True)
        original = (
            "# Acceptance Criteria\n\n"
            "AC-1: Feature works\n\n"
            "## Verification Instructions\n\n"
            "1. Old step\n"
            "2. Another old step\n"
        )
        (criteria_dir / "issue-42.md").write_text(original)

        judge._update_criteria_file(
            42, "1. New step one\n2. New step two\n3. New step three"
        )

        updated = (criteria_dir / "issue-42.md").read_text()
        assert "New step one" in updated
        assert "Old step" not in updated
        assert "AC-1: Feature works" in updated

    def test_appends_when_no_instructions_section(self, event_bus, tmp_path):
        cfg = ConfigFactory.create(repo_root=tmp_path)
        judge = _make_judge(cfg, event_bus)
        criteria_dir = tmp_path / ".hydra" / "verification"
        criteria_dir.mkdir(parents=True)
        (criteria_dir / "issue-42.md").write_text("# Criteria\n\nAC-1: Feature")

        judge._update_criteria_file(42, "1. New instructions")

        updated = (criteria_dir / "issue-42.md").read_text()
        assert "New instructions" in updated
        assert "AC-1: Feature" in updated


# ---------------------------------------------------------------------------
# terminate
# ---------------------------------------------------------------------------


class TestTerminate:
    def test_kills_active_processes(self, config, event_bus):
        judge = _make_judge(config, event_bus)
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        judge._active_procs.add(mock_proc)

        with patch("runner_utils.os.killpg") as mock_killpg:
            judge.terminate()

        mock_killpg.assert_called_once()

    def test_handles_no_active_processes(self, config, event_bus):
        judge = _make_judge(config, event_bus)
        judge.terminate()  # Should not raise
