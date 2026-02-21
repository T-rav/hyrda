"""Tests for analysis.py — PlanAnalyzer pre-implementation analysis."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis import PlanAnalyzer
from models import AnalysisResult, AnalysisSection, AnalysisVerdict

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PLAN_ALL_EXIST = """\
## Files to Modify

### `models.py`
- Add AnalysisVerdict enum

### `orchestrator.py`
- Integrate analysis step

## New Files

### `analysis.py`
- New analysis module

## Testing Strategy

All tests use `tmp_path` fixtures. Run with pytest.
"""


def _setup_repo(tmp_path: Path, files: list[str] | None = None) -> Path:
    """Create a minimal repo structure for analysis tests."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "tests").mkdir()
    (repo / ".hydra" / "plans").mkdir(parents=True)

    # Create pyproject.toml with pytest config
    (repo / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\n"
    )

    for f in files or []:
        p = repo / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {f}\n")

    return repo


# ---------------------------------------------------------------------------
# _extract_file_paths tests
# ---------------------------------------------------------------------------


class TestExtractFilePaths:
    """Tests for PlanAnalyzer._extract_file_paths."""

    def test_extract_file_paths_from_list_items(self) -> None:
        section = "- models.py: Add enum\n- config.py: Update config"
        result = PlanAnalyzer._extract_file_paths(section)
        assert "models.py" in result
        assert "config.py" in result

    def test_extract_file_paths_from_backticks(self) -> None:
        section = "Modify `path/to/file.py` and `other/file.ts`."
        result = PlanAnalyzer._extract_file_paths(section)
        assert "path/to/file.py" in result
        assert "other/file.ts" in result

    def test_extract_file_paths_from_headings(self) -> None:
        section = "### config.py\nSome description\n### models.py\nOther desc"
        result = PlanAnalyzer._extract_file_paths(section)
        assert "config.py" in result
        assert "models.py" in result

    def test_extract_file_paths_with_subdirectories(self) -> None:
        section = "- `tests/test_models.py`: Test the models"
        result = PlanAnalyzer._extract_file_paths(section)
        assert "tests/test_models.py" in result

    def test_extract_file_paths_deduplicates(self) -> None:
        section = "- `models.py`: once\n### `models.py`\nAgain"
        result = PlanAnalyzer._extract_file_paths(section)
        assert result.count("models.py") == 1

    def test_extract_file_paths_empty_section(self) -> None:
        result = PlanAnalyzer._extract_file_paths("")
        assert result == []

    def test_extract_file_paths_from_bold(self) -> None:
        section = "Modify **path/to/file.py** for the change."
        result = PlanAnalyzer._extract_file_paths(section)
        assert "path/to/file.py" in result

    def test_extract_file_paths_strips_leading_dot_slash(self) -> None:
        section = "- `./src/main.py`: entry point"
        result = PlanAnalyzer._extract_file_paths(section)
        assert "src/main.py" in result

    def test_extract_file_paths_numbered_headings(self) -> None:
        section = "### 1. `agent.py` — AgentRunner\nDesc"
        result = PlanAnalyzer._extract_file_paths(section)
        assert "agent.py" in result

    def test_extract_file_paths_filters_non_code_extensions(self) -> None:
        section = "- `notes.txt`: not a code file\n- `data.csv`: data"
        result = PlanAnalyzer._extract_file_paths(section)
        assert result == []


# ---------------------------------------------------------------------------
# _extract_section tests
# ---------------------------------------------------------------------------


class TestExtractSection:
    """Tests for PlanAnalyzer._extract_section."""

    def test_extract_section_finds_files_to_modify(self) -> None:
        text = "## Files to Modify\n\n- `models.py`\n\n## New Files\n\n- `analysis.py`"
        result = PlanAnalyzer._extract_section(text, "Files to Modify")
        assert "models.py" in result
        assert "analysis.py" not in result

    def test_extract_section_case_insensitive(self) -> None:
        text = "## files to modify\n\n- `models.py`\n\n## Other"
        result = PlanAnalyzer._extract_section(text, "Files to Modify")
        assert "models.py" in result

    def test_extract_section_returns_empty_when_missing(self) -> None:
        text = "## Summary\n\nSome text."
        result = PlanAnalyzer._extract_section(text, "Files to Modify")
        assert result == ""

    def test_extract_section_stops_at_next_heading(self) -> None:
        text = (
            "## Files to Modify\n\n- `models.py`\n\n## Testing Strategy\n\nUse pytest."
        )
        result = PlanAnalyzer._extract_section(text, "Files to Modify")
        assert "models.py" in result
        assert "pytest" not in result


# ---------------------------------------------------------------------------
# File validation tests
# ---------------------------------------------------------------------------


class TestFileValidation:
    """Tests for _validate_file_references."""

    def test_validate_file_references_all_exist(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path, ["models.py", "orchestrator.py"])
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = (
            "## Files to Modify\n\n- `models.py`: change\n- `orchestrator.py`: change"
        )
        section = analyzer._validate_file_references(plan)

        assert section.verdict == AnalysisVerdict.PASS
        assert "2" in section.details[0]

    def test_validate_file_references_some_missing(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path, ["models.py"])
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = "## Files to Modify\n\n- `models.py`: exists\n- `missing.py`: gone"
        section = analyzer._validate_file_references(plan)

        assert section.verdict == AnalysisVerdict.WARN
        assert any("missing.py" in d for d in section.details)

    def test_validate_file_references_no_section(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path)
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = "## Summary\n\nJust a summary."
        section = analyzer._validate_file_references(plan)

        assert section.verdict == AnalysisVerdict.PASS

    def test_validate_new_file_directories_exist(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path)
        analyzer = PlanAnalyzer(repo_root=repo)

        # tests/ dir exists from _setup_repo
        plan = "## New Files\n\n- `tests/test_new.py`: new test"
        warnings = analyzer._check_new_file_directories(plan)

        assert warnings == []

    def test_validate_new_file_directories_missing(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path)
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = "## New Files\n\n- `nonexistent_dir/new_file.py`: new module"
        warnings = analyzer._check_new_file_directories(plan)

        assert len(warnings) == 1
        assert "nonexistent_dir" in warnings[0]


# ---------------------------------------------------------------------------
# Concurrent conflict tests
# ---------------------------------------------------------------------------


class TestConcurrentConflicts:
    """Tests for _check_concurrent_conflicts."""

    def test_concurrent_no_other_plans(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path, ["models.py"])
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = "## Files to Modify\n\n- `models.py`: change"
        section, overlapping = analyzer._check_concurrent_conflicts(plan, 42)

        assert section.verdict == AnalysisVerdict.PASS
        assert overlapping == {}

    def test_concurrent_no_overlap(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path, ["models.py", "config.py"])
        plans_dir = repo / ".hydra" / "plans"

        # Write another plan that touches different files
        (plans_dir / "issue-10.md").write_text(
            "## Files to Modify\n\n- `config.py`: change"
        )
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = "## Files to Modify\n\n- `models.py`: change"
        section, overlapping = analyzer._check_concurrent_conflicts(plan, 42)

        assert section.verdict == AnalysisVerdict.PASS
        assert overlapping == {}

    def test_concurrent_small_overlap_warns(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path, ["models.py", "config.py"])
        plans_dir = repo / ".hydra" / "plans"

        # Other plan also modifies models.py
        (plans_dir / "issue-10.md").write_text(
            "## Files to Modify\n\n- `models.py`: change"
        )
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = "## Files to Modify\n\n- `models.py`: our change\n- `config.py`: update"
        section, overlapping = analyzer._check_concurrent_conflicts(plan, 42)

        assert section.verdict == AnalysisVerdict.WARN
        assert 10 in overlapping
        assert "models.py" in overlapping[10]

    def test_concurrent_large_overlap_blocks(self, tmp_path: Path) -> None:
        repo = _setup_repo(
            tmp_path,
            ["a.py", "b.py", "c.py", "d.py", "e.py"],
        )
        plans_dir = repo / ".hydra" / "plans"

        # Other plan touches 4 of the same files (exceeds default max of 3)
        (plans_dir / "issue-10.md").write_text(
            "## Files to Modify\n\n"
            "- `a.py`: change\n"
            "- `b.py`: change\n"
            "- `c.py`: change\n"
            "- `d.py`: change\n"
        )
        analyzer = PlanAnalyzer(repo_root=repo, max_file_overlap=3)

        plan = (
            "## Files to Modify\n\n"
            "- `a.py`: change\n"
            "- `b.py`: change\n"
            "- `c.py`: change\n"
            "- `d.py`: change\n"
            "- `e.py`: change\n"
        )
        section, overlapping = analyzer._check_concurrent_conflicts(plan, 42)

        assert section.verdict == AnalysisVerdict.BLOCK
        assert 10 in overlapping
        assert len(overlapping[10]) == 4

    def test_concurrent_skips_own_plan(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path, ["models.py"])
        plans_dir = repo / ".hydra" / "plans"

        # Write own plan (should be skipped)
        (plans_dir / "issue-42.md").write_text(
            "## Files to Modify\n\n- `models.py`: change"
        )
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = "## Files to Modify\n\n- `models.py`: change"
        section, overlapping = analyzer._check_concurrent_conflicts(plan, 42)

        assert section.verdict == AnalysisVerdict.PASS
        assert overlapping == {}

    def test_concurrent_overlapping_issues_dict_populated(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path, ["models.py", "config.py"])
        plans_dir = repo / ".hydra" / "plans"

        (plans_dir / "issue-10.md").write_text(
            "## Files to Modify\n\n- `models.py`: change"
        )
        (plans_dir / "issue-20.md").write_text(
            "## Files to Modify\n\n- `config.py`: change"
        )
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = "## Files to Modify\n\n- `models.py`: change\n- `config.py`: change"
        _, overlapping = analyzer._check_concurrent_conflicts(plan, 42)

        assert 10 in overlapping
        assert 20 in overlapping
        assert "models.py" in overlapping[10]
        assert "config.py" in overlapping[20]

    def test_concurrent_plans_dir_missing(self, tmp_path: Path) -> None:
        """When .hydra/plans/ doesn't exist, conflict check should PASS."""
        repo = tmp_path / "repo"
        repo.mkdir()
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = "## Files to Modify\n\n- `models.py`: change"
        section, overlapping = analyzer._check_concurrent_conflicts(plan, 42)

        assert section.verdict == AnalysisVerdict.PASS
        assert overlapping == {}

    def test_concurrent_configurable_threshold(self, tmp_path: Path) -> None:
        """max_file_overlap=5 should allow 5 overlapping files without blocking."""
        repo = _setup_repo(
            tmp_path,
            ["a.py", "b.py", "c.py", "d.py", "e.py"],
        )
        plans_dir = repo / ".hydra" / "plans"

        (plans_dir / "issue-10.md").write_text(
            "## Files to Modify\n\n"
            "- `a.py`: change\n"
            "- `b.py`: change\n"
            "- `c.py`: change\n"
            "- `d.py`: change\n"
            "- `e.py`: change\n"
        )
        analyzer = PlanAnalyzer(repo_root=repo, max_file_overlap=5)

        plan = (
            "## Files to Modify\n\n"
            "- `a.py`: change\n"
            "- `b.py`: change\n"
            "- `c.py`: change\n"
            "- `d.py`: change\n"
            "- `e.py`: change\n"
        )
        section, _ = analyzer._check_concurrent_conflicts(plan, 42)

        assert section.verdict == AnalysisVerdict.WARN


# ---------------------------------------------------------------------------
# Test pattern validation tests
# ---------------------------------------------------------------------------


class TestTestPatternValidation:
    """Tests for _validate_test_patterns."""

    def test_validate_test_patterns_valid(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path)  # creates tests/ and pyproject.toml with pytest
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = "## Testing Strategy\n\nWrite tests in `tests/` using pytest."
        section = analyzer._validate_test_patterns(plan)

        assert section.verdict == AnalysisVerdict.PASS

    def test_validate_test_patterns_missing_test_dir(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        # pyproject.toml with pytest but no tests/ dir
        (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = "## Testing Strategy\n\nTests in `tests/`."
        section = analyzer._validate_test_patterns(plan)

        assert section.verdict == AnalysisVerdict.WARN
        assert any("tests/" in d for d in section.details)

    def test_validate_test_patterns_no_testing_section(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path)
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = "## Summary\n\nNo testing section."
        section = analyzer._validate_test_patterns(plan)

        assert section.verdict == AnalysisVerdict.PASS

    def test_validate_test_patterns_no_pyproject(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "tests").mkdir()
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = "## Testing Strategy\n\nUse pytest."
        section = analyzer._validate_test_patterns(plan)

        assert section.verdict == AnalysisVerdict.WARN
        assert any("pyproject.toml" in d for d in section.details)

    def test_validate_test_patterns_pyproject_without_pytest(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "tests").mkdir()
        (repo / "pyproject.toml").write_text(
            "[build-system]\nrequires = ['setuptools']\n"
        )
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = "## Testing Strategy\n\nUse pytest."
        section = analyzer._validate_test_patterns(plan)

        assert section.verdict == AnalysisVerdict.WARN
        assert any("No pytest configuration" in d for d in section.details)

    def test_validate_test_patterns_makefile_with_test_target(
        self, tmp_path: Path
    ) -> None:
        repo = _setup_repo(tmp_path)
        (repo / "Makefile").write_text("test:\n\tpytest tests/\n")
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = "## Testing Strategy\n\nRun make test."
        section = analyzer._validate_test_patterns(plan)

        assert section.verdict == AnalysisVerdict.PASS
        assert any("Makefile" in d for d in section.details)

    def test_validate_test_patterns_makefile_without_test_target(
        self, tmp_path: Path
    ) -> None:
        repo = _setup_repo(tmp_path)
        (repo / "Makefile").write_text("build:\n\techo build\n")
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = "## Testing Strategy\n\nRun make test."
        section = analyzer._validate_test_patterns(plan)

        assert section.verdict == AnalysisVerdict.WARN
        assert any("No test target" in d for d in section.details)


# ---------------------------------------------------------------------------
# Full analyze() tests
# ---------------------------------------------------------------------------


class TestAnalyze:
    """Tests for the full analyze() method."""

    def test_analyze_all_pass(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path, ["models.py", "orchestrator.py"])
        analyzer = PlanAnalyzer(repo_root=repo)

        result = analyzer.analyze(PLAN_ALL_EXIST, 42)

        assert not result.blocked
        assert len(result.sections) == 3
        assert all(
            s.verdict in (AnalysisVerdict.PASS, AnalysisVerdict.WARN)
            for s in result.sections
        )

    def test_analyze_blocked_result(self, tmp_path: Path) -> None:
        repo = _setup_repo(
            tmp_path,
            ["a.py", "b.py", "c.py", "d.py"],
        )
        plans_dir = repo / ".hydra" / "plans"
        (plans_dir / "issue-10.md").write_text(
            "## Files to Modify\n\n- `a.py`: x\n- `b.py`: x\n- `c.py`: x\n- `d.py`: x\n"
        )
        analyzer = PlanAnalyzer(repo_root=repo, max_file_overlap=3)

        plan = (
            "## Files to Modify\n\n"
            "- `a.py`: x\n- `b.py`: x\n- `c.py`: x\n- `d.py`: x\n"
            "\n## Testing Strategy\n\nUse pytest."
        )
        result = analyzer.analyze(plan, 42)

        assert result.blocked

    def test_analyze_not_blocked_on_warn(self, tmp_path: Path) -> None:
        repo = _setup_repo(tmp_path, ["models.py"])
        plans_dir = repo / ".hydra" / "plans"
        (plans_dir / "issue-10.md").write_text(
            "## Files to Modify\n\n- `models.py`: change"
        )
        analyzer = PlanAnalyzer(repo_root=repo)

        plan = (
            "## Files to Modify\n\n- `models.py`: change\n"
            "\n## Testing Strategy\n\nUse pytest."
        )
        result = analyzer.analyze(plan, 42)

        assert not result.blocked
        # Conflict section should be WARN
        conflict = next(s for s in result.sections if s.name == "Conflict Check")
        assert conflict.verdict == AnalysisVerdict.WARN


# ---------------------------------------------------------------------------
# format_comment() tests
# ---------------------------------------------------------------------------


class TestFormatComment:
    """Tests for AnalysisResult.format_comment."""

    def test_format_comment_includes_all_sections(self) -> None:
        result = AnalysisResult(
            issue_number=42,
            sections=[
                AnalysisSection(
                    name="File Validation",
                    verdict=AnalysisVerdict.PASS,
                    details=["All good."],
                ),
                AnalysisSection(
                    name="Conflict Check",
                    verdict=AnalysisVerdict.WARN,
                    details=["Minor overlap."],
                ),
                AnalysisSection(
                    name="Test Pattern Check",
                    verdict=AnalysisVerdict.PASS,
                    details=["Tests valid."],
                ),
            ],
        )
        comment = result.format_comment()

        assert "## Pre-Implementation Analysis" in comment
        assert "File Validation" in comment
        assert "Conflict Check" in comment
        assert "Test Pattern Check" in comment

    def test_format_comment_shows_verdict_icons(self) -> None:
        result = AnalysisResult(
            issue_number=42,
            sections=[
                AnalysisSection(name="A", verdict=AnalysisVerdict.PASS, details=[]),
                AnalysisSection(name="B", verdict=AnalysisVerdict.WARN, details=[]),
                AnalysisSection(name="C", verdict=AnalysisVerdict.BLOCK, details=[]),
            ],
        )
        comment = result.format_comment()

        assert "\u2705 PASS" in comment
        assert "\u26a0\ufe0f WARN" in comment
        assert "\U0001f6d1 BLOCK" in comment

    def test_format_comment_includes_details(self) -> None:
        result = AnalysisResult(
            issue_number=42,
            sections=[
                AnalysisSection(
                    name="File Validation",
                    verdict=AnalysisVerdict.WARN,
                    details=["Missing file: `foo.py`", "Missing file: `bar.py`"],
                ),
            ],
        )
        comment = result.format_comment()

        assert "- Missing file: `foo.py`" in comment
        assert "- Missing file: `bar.py`" in comment

    def test_format_comment_includes_footer(self) -> None:
        result = AnalysisResult(
            issue_number=42,
            sections=[
                AnalysisSection(name="A", verdict=AnalysisVerdict.PASS, details=[]),
            ],
        )
        comment = result.format_comment()

        assert "*Generated by Hydra Analyzer*" in comment
