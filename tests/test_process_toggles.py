"""Tests for TriageResult parsing (issue_type normalisation)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from triage import TriageRunner

# ---------------------------------------------------------------------------
# TriageResult parsing tests
# ---------------------------------------------------------------------------


class TestTriageResultParsing:
    """Test _result_from_dict parses issue_type correctly."""

    def test_parses_issue_type_feature(self) -> None:
        result = TriageRunner._result_from_dict(
            {"ready": True, "issue_type": "feature"}, 1
        )
        assert result.issue_type == "feature"

    def test_parses_issue_type_bug(self) -> None:
        result = TriageRunner._result_from_dict({"ready": True, "issue_type": "bug"}, 1)
        assert result.issue_type == "bug"

    def test_parses_issue_type_epic(self) -> None:
        result = TriageRunner._result_from_dict(
            {"ready": True, "issue_type": "epic"}, 1
        )
        assert result.issue_type == "epic"

    def test_defaults_to_feature_when_missing(self) -> None:
        result = TriageRunner._result_from_dict({"ready": True}, 1)
        assert result.issue_type == "feature"

    def test_normalises_unknown_to_feature(self) -> None:
        result = TriageRunner._result_from_dict(
            {"ready": True, "issue_type": "task"}, 1
        )
        assert result.issue_type == "feature"

    def test_normalises_none_to_feature(self) -> None:
        result = TriageRunner._result_from_dict({"ready": True, "issue_type": None}, 1)
        assert result.issue_type == "feature"

    def test_normalises_case_insensitive(self) -> None:
        result = TriageRunner._result_from_dict({"ready": True, "issue_type": "BUG"}, 1)
        assert result.issue_type == "bug"


# ---------------------------------------------------------------------------
# HITL enrichment tests
# ---------------------------------------------------------------------------


class TestHITLEnrichment:
    """Test that issueTypeReview flag is set correctly based on cause."""

    def test_epic_cause_sets_flag(self) -> None:
        cause = "Epic detected — awaiting human review (Auto Route Epics toggle is off)"
        assert "epic detected" in cause.lower()

    def test_bug_cause_sets_flag(self) -> None:
        cause = "Bug report detected — awaiting human review (Auto Route Bug Reports toggle is off)"
        assert "bug report detected" in cause.lower()

    def test_other_cause_no_flag(self) -> None:
        cause = "Insufficient issue detail for triage"
        assert "epic detected" not in cause.lower()
        assert "bug report detected" not in cause.lower()

    def test_none_cause_no_flag(self) -> None:
        cause = None
        # Should not crash or set the flag
        assert not (cause and "epic detected" in cause.lower())


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------


class TestProcessToggleEdgeCases:
    """Edge cases for process toggle routing."""

    @pytest.mark.asyncio
    async def test_unready_epic_takes_normal_hitl_path(self, tmp_path: Path) -> None:
        """ready=False + issue_type=epic uses the normal insufficient-detail path."""
        config = ConfigFactory.create(
            repo_root=tmp_path / "repo",
            state_file=tmp_path / "state.json",
            auto_process_epics=False,
        )
        phase, state, triage, prs, store, _stop = _make_phase(config)
        issue = TaskFactory.create(id=50, title="Epic: vague idea", body="A" * 100)

        triage.evaluate = AsyncMock(
            return_value=TriageResult(
                issue_number=50,
                ready=False,
                reasons=["Too vague"],
                issue_type="epic",
            )
        )
        store.get_triageable = lambda _max_count: [issue]

        await phase.triage_issues()

        # Should use the normal escalation (insufficient detail), not the type-review one
        cause = state.get_hitl_cause(50)
        assert cause == "Insufficient issue detail for triage"
        prs.post_comment.assert_called_once()
        comment = prs.post_comment.call_args.args[1]
        assert "Needs More Information" in comment

    @pytest.mark.asyncio
    async def test_dry_run_skips_type_review_routing(self, tmp_path: Path) -> None:
        """In dry_run mode, type review routing is not evaluated."""
        config = ConfigFactory.create(
            repo_root=tmp_path / "repo",
            state_file=tmp_path / "state.json",
            auto_process_epics=False,
            dry_run=True,
        )
        phase, _state, triage, prs, store, _stop = _make_phase(config)
        issue = TaskFactory.create(id=51, title="Epic: something big", body="A" * 100)

        triage.evaluate = AsyncMock(
            return_value=TriageResult(issue_number=51, ready=True, issue_type="epic")
        )
        store.get_triageable = lambda _max_count: [issue]

        await phase.triage_issues()

        # In dry_run, no label transitions or HITL routing happen
        prs.swap_pipeline_labels.assert_not_called()
        prs.transition.assert_not_called()
        prs.post_comment.assert_not_called()
