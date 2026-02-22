"""Tests for prep.py — repo audit logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from models import AuditCheckStatus
from tests.helpers import AuditCheckFactory, AuditResultFactory, ConfigFactory

# ---------------------------------------------------------------------------
# AuditResult model tests
# ---------------------------------------------------------------------------


class TestAuditResult:
    """Tests for the AuditResult model and its format_report method."""

    def test_missing_checks_returns_missing_and_partial(self) -> None:
        """Should include both MISSING and PARTIAL checks."""
        result = AuditResultFactory.create(
            checks=[
                AuditCheckFactory.create(name="A", status="present"),
                AuditCheckFactory.create(name="B", status="missing"),
                AuditCheckFactory.create(name="C", status="partial"),
            ]
        )
        names = [c.name for c in result.missing_checks]
        assert names == ["B", "C"]

    def test_missing_checks_empty_when_all_present(self) -> None:
        """Should return empty list when all checks pass."""
        result = AuditResultFactory.create(
            checks=[
                AuditCheckFactory.create(name="A", status="present"),
                AuditCheckFactory.create(name="B", status="present"),
            ]
        )
        assert result.missing_checks == []

    def test_has_critical_gaps_true(self) -> None:
        """Should return True when a critical check is MISSING."""
        result = AuditResultFactory.create(
            checks=[
                AuditCheckFactory.create(name="CI", status="missing", critical=True),
                AuditCheckFactory.create(name="Linting", status="present"),
            ]
        )
        assert result.has_critical_gaps is True

    def test_has_critical_gaps_false_when_critical_present(self) -> None:
        """Should return False when all critical checks pass."""
        result = AuditResultFactory.create(
            checks=[
                AuditCheckFactory.create(name="CI", status="present", critical=True),
                AuditCheckFactory.create(name="Linting", status="missing"),
            ]
        )
        assert result.has_critical_gaps is False

    def test_has_critical_gaps_false_when_critical_partial(self) -> None:
        """Should return False when critical check is PARTIAL (not MISSING)."""
        result = AuditResultFactory.create(
            checks=[
                AuditCheckFactory.create(
                    name="Makefile", status="partial", critical=True
                ),
            ]
        )
        assert result.has_critical_gaps is False

    def test_format_report_all_passing(self) -> None:
        """Should show checkmarks and 'No gaps found' message."""
        result = AuditResultFactory.create(
            repo="owner/repo",
            checks=[
                AuditCheckFactory.create(
                    name="Language", status="present", detail="Python 3.11"
                ),
                AuditCheckFactory.create(
                    name="Makefile", status="present", detail="all targets"
                ),
            ],
        )
        report = result.format_report()
        assert "owner/repo" in report
        assert "\u2713" in report
        assert "No gaps found" in report

    def test_format_report_with_gaps(self) -> None:
        """Should show X markers and missing count."""
        result = AuditResultFactory.create(
            repo="owner/repo",
            checks=[
                AuditCheckFactory.create(name="CI", status="missing", critical=True),
                AuditCheckFactory.create(name="Linting", status="present"),
                AuditCheckFactory.create(name="Git hooks", status="missing"),
            ],
        )
        report = result.format_report()
        assert "\u2717" in report
        assert "Missing (2)" in report
        assert "CI" in report
        assert "Git hooks" in report
        assert "hydra prep" in report


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


class TestCheckLanguage:
    """Tests for RepoAuditor._check_language."""

    def test_python_repo_with_pyproject_toml(self, tmp_path: Path) -> None:
        """Should detect Python with version from pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nrequires-python = ">=3.11"\n'
        )
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_language()
        assert check.status == AuditCheckStatus.PRESENT
        assert "Python" in check.detail
        assert "3.11" in check.detail

    def test_python_with_setup_py(self, tmp_path: Path) -> None:
        """Should detect Python via setup.py fallback."""
        (tmp_path / "setup.py").write_text("from setuptools import setup\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_language()
        assert check.status == AuditCheckStatus.PRESENT
        assert "Python" in check.detail

    def test_python_with_requirements_txt(self, tmp_path: Path) -> None:
        """Should detect Python via requirements.txt fallback."""
        (tmp_path / "requirements.txt").write_text("requests\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_language()
        assert check.status == AuditCheckStatus.PRESENT
        assert "Python" in check.detail

    def test_js_repo_with_package_json(self, tmp_path: Path) -> None:
        """Should detect JS/TS via package.json."""
        (tmp_path / "package.json").write_text('{"name": "test"}\n')
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_language()
        assert check.status == AuditCheckStatus.PRESENT
        assert "JS/TS" in check.detail

    def test_mixed_repo(self, tmp_path: Path) -> None:
        """Should detect both Python and JS/TS."""
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        (tmp_path / "package.json").write_text('{"name": "test"}\n')
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_language()
        assert check.status == AuditCheckStatus.PRESENT
        assert "Python" in check.detail
        assert "JS/TS" in check.detail

    def test_no_language_markers(self, tmp_path: Path) -> None:
        """Should report MISSING when no language markers found."""
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_language()
        assert check.status == AuditCheckStatus.MISSING


# ---------------------------------------------------------------------------
# Makefile detection
# ---------------------------------------------------------------------------


class TestCheckMakefile:
    """Tests for RepoAuditor._check_makefile."""

    def test_makefile_with_all_targets(self, tmp_path: Path) -> None:
        """Should report PRESENT when all required targets exist."""
        (tmp_path / "Makefile").write_text(
            "quality:\n\t@echo quality\n\nlint:\n\t@echo lint\n\ntest:\n\t@echo test\n"
        )
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_makefile()
        assert check.status == AuditCheckStatus.PRESENT
        assert check.critical is True

    def test_makefile_missing_quality_target(self, tmp_path: Path) -> None:
        """Should report PARTIAL when some targets are missing."""
        (tmp_path / "Makefile").write_text(
            "lint:\n\t@echo lint\n\ntest:\n\t@echo test\n"
        )
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_makefile()
        assert check.status == AuditCheckStatus.PARTIAL
        assert "quality" in check.detail

    def test_no_makefile(self, tmp_path: Path) -> None:
        """Should report MISSING when no Makefile exists."""
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_makefile()
        assert check.status == AuditCheckStatus.MISSING

    def test_makefile_with_dependencies_on_targets(self, tmp_path: Path) -> None:
        """Should detect targets that have dependencies."""
        (tmp_path / "Makefile").write_text(
            "quality: lint test\n\t@echo quality\n\nlint:\n\t@echo lint\n\ntest:\n\t@echo test\n"
        )
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_makefile()
        assert check.status == AuditCheckStatus.PRESENT


# ---------------------------------------------------------------------------
# CI detection
# ---------------------------------------------------------------------------


class TestCheckCI:
    """Tests for RepoAuditor._check_ci."""

    def test_workflow_with_push_trigger(self, tmp_path: Path) -> None:
        """Should report PRESENT when a workflow triggers on push."""
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text("on:\n  push:\n    branches: [main]\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_ci()
        assert check.status == AuditCheckStatus.PRESENT
        assert check.critical is True

    def test_workflow_with_pull_request_trigger(self, tmp_path: Path) -> None:
        """Should report PRESENT when a workflow triggers on pull_request."""
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yaml").write_text("on:\n  pull_request:\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_ci()
        assert check.status == AuditCheckStatus.PRESENT

    def test_workflow_without_push_trigger(self, tmp_path: Path) -> None:
        """Should report PARTIAL when workflows exist but none trigger on push/PR."""
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "release.yml").write_text("on:\n  workflow_dispatch:\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_ci()
        assert check.status == AuditCheckStatus.PARTIAL

    def test_no_workflows_dir(self, tmp_path: Path) -> None:
        """Should report MISSING when .github/workflows/ doesn't exist."""
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_ci()
        assert check.status == AuditCheckStatus.MISSING

    def test_workflow_dir_empty(self, tmp_path: Path) -> None:
        """Should report MISSING when workflows dir is empty."""
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_ci()
        assert check.status == AuditCheckStatus.MISSING


# ---------------------------------------------------------------------------
# Git hooks detection
# ---------------------------------------------------------------------------


class TestCheckGitHooks:
    """Tests for RepoAuditor._check_git_hooks."""

    def test_githooks_dir_with_precommit(self, tmp_path: Path) -> None:
        """Should report PRESENT when .githooks/pre-commit exists."""
        hooks_dir = tmp_path / ".githooks"
        hooks_dir.mkdir()
        (hooks_dir / "pre-commit").write_text("#!/bin/sh\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_git_hooks()
        assert check.status == AuditCheckStatus.PRESENT

    def test_husky_dir_with_precommit(self, tmp_path: Path) -> None:
        """Should report PRESENT when .husky/pre-commit exists."""
        hooks_dir = tmp_path / ".husky"
        hooks_dir.mkdir()
        (hooks_dir / "pre-commit").write_text("#!/bin/sh\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_git_hooks()
        assert check.status == AuditCheckStatus.PRESENT

    def test_no_hooks_dir(self, tmp_path: Path) -> None:
        """Should report MISSING when no hooks directories exist."""
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_git_hooks()
        assert check.status == AuditCheckStatus.MISSING


# ---------------------------------------------------------------------------
# Linting detection
# ---------------------------------------------------------------------------


class TestCheckLinting:
    """Tests for RepoAuditor._check_linting."""

    def test_ruff_toml(self, tmp_path: Path) -> None:
        """Should detect standalone ruff.toml."""
        (tmp_path / "ruff.toml").write_text("[lint]\nselect = ['E']\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_linting()
        assert check.status == AuditCheckStatus.PRESENT
        assert "ruff" in check.detail

    def test_ruff_in_pyproject_toml(self, tmp_path: Path) -> None:
        """Should detect [tool.ruff] in pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_linting()
        assert check.status == AuditCheckStatus.PRESENT
        assert "ruff" in check.detail

    def test_eslintrc(self, tmp_path: Path) -> None:
        """Should detect .eslintrc.json."""
        (tmp_path / ".eslintrc.json").write_text("{}\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_linting()
        assert check.status == AuditCheckStatus.PRESENT
        assert "eslint" in check.detail

    def test_biome_json(self, tmp_path: Path) -> None:
        """Should detect biome.json."""
        (tmp_path / "biome.json").write_text("{}\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_linting()
        assert check.status == AuditCheckStatus.PRESENT
        assert "biome" in check.detail

    def test_no_linting_config(self, tmp_path: Path) -> None:
        """Should report MISSING when no linting config found."""
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_linting()
        assert check.status == AuditCheckStatus.MISSING


# ---------------------------------------------------------------------------
# Type checking detection
# ---------------------------------------------------------------------------


class TestCheckTypeChecking:
    """Tests for RepoAuditor._check_type_checking."""

    def test_pyrightconfig_json(self, tmp_path: Path) -> None:
        """Should detect pyrightconfig.json."""
        (tmp_path / "pyrightconfig.json").write_text("{}\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_type_checking()
        assert check.status == AuditCheckStatus.PRESENT
        assert "pyright" in check.detail

    def test_pyright_in_pyproject_toml(self, tmp_path: Path) -> None:
        """Should detect [tool.pyright] in pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text("[tool.pyright]\nvenvPath = '.'\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_type_checking()
        assert check.status == AuditCheckStatus.PRESENT
        assert "pyright" in check.detail

    def test_tsconfig_json(self, tmp_path: Path) -> None:
        """Should detect tsconfig.json."""
        (tmp_path / "tsconfig.json").write_text("{}\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_type_checking()
        assert check.status == AuditCheckStatus.PRESENT
        assert "tsconfig" in check.detail

    def test_no_type_checking_config(self, tmp_path: Path) -> None:
        """Should report MISSING when no type checking config found."""
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_type_checking()
        assert check.status == AuditCheckStatus.MISSING


# ---------------------------------------------------------------------------
# Test framework detection
# ---------------------------------------------------------------------------


class TestCheckTestFramework:
    """Tests for RepoAuditor._check_test_framework."""

    def test_pytest_with_tests_dir(self, tmp_path: Path) -> None:
        """Should detect pytest with tests/ dir and count test files."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_foo.py").write_text("def test_x(): pass\n")
        (tests_dir / "test_bar.py").write_text("def test_y(): pass\n")
        (tests_dir / "conftest.py").write_text("import pytest\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_test_framework()
        assert check.status == AuditCheckStatus.PRESENT
        assert "pytest" in check.detail
        assert "2" in check.detail  # 2 test files

    def test_jest_with_tests_dir(self, tmp_path: Path) -> None:
        """Should detect jest-style __tests__/ directory."""
        tests_dir = tmp_path / "__tests__"
        tests_dir.mkdir()
        (tests_dir / "foo.test.js").write_text("test('x', () => {})\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_test_framework()
        assert check.status == AuditCheckStatus.PRESENT

    def test_vitest_config(self, tmp_path: Path) -> None:
        """Should detect vitest.config.ts."""
        (tmp_path / "vitest.config.ts").write_text("export default {}\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_test_framework()
        assert check.status == AuditCheckStatus.PRESENT
        assert "vitest" in check.detail

    def test_no_test_framework(self, tmp_path: Path) -> None:
        """Should report MISSING when no test framework detected."""
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_test_framework()
        assert check.status == AuditCheckStatus.MISSING


# ---------------------------------------------------------------------------
# Package manager detection
# ---------------------------------------------------------------------------


class TestCheckPackageManager:
    """Tests for RepoAuditor._check_package_manager."""

    def test_uv_lock(self, tmp_path: Path) -> None:
        """Should detect uv.lock."""
        (tmp_path / "uv.lock").write_text("[[package]]\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_package_manager()
        assert check.status == AuditCheckStatus.PRESENT
        assert "uv" in check.detail

    def test_pnpm_lock(self, tmp_path: Path) -> None:
        """Should detect pnpm-lock.yaml."""
        (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: 6\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_package_manager()
        assert check.status == AuditCheckStatus.PRESENT
        assert "pnpm" in check.detail

    def test_package_lock_json(self, tmp_path: Path) -> None:
        """Should detect package-lock.json."""
        (tmp_path / "package-lock.json").write_text("{}\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_package_manager()
        assert check.status == AuditCheckStatus.PRESENT
        assert "npm" in check.detail

    def test_yarn_lock(self, tmp_path: Path) -> None:
        """Should detect yarn.lock."""
        (tmp_path / "yarn.lock").write_text("# yarn lockfile v1\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_package_manager()
        assert check.status == AuditCheckStatus.PRESENT
        assert "yarn" in check.detail

    def test_poetry_lock(self, tmp_path: Path) -> None:
        """Should detect poetry.lock."""
        (tmp_path / "poetry.lock").write_text("[[package]]\n")
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_package_manager()
        assert check.status == AuditCheckStatus.PRESENT
        assert "poetry" in check.detail

    def test_no_lock_file(self, tmp_path: Path) -> None:
        """Should report MISSING when no lock file found."""
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        check = auditor._check_package_manager()
        assert check.status == AuditCheckStatus.MISSING


# ---------------------------------------------------------------------------
# GH CLI detection
# ---------------------------------------------------------------------------


class TestCheckGhCli:
    """Tests for RepoAuditor._check_gh_cli."""

    @pytest.mark.asyncio
    async def test_authenticated_with_push_access(self, tmp_path: Path) -> None:
        """Should report PRESENT when gh is authed with push access."""
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)

        with patch("prep.run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                "github.com\n  Logged in",  # gh auth status
                "WRITE",  # gh repo view
            ]
            check = await auditor._check_gh_cli()

        assert check.status == AuditCheckStatus.PRESENT
        assert "authenticated" in check.detail
        assert "push access" in check.detail

    @pytest.mark.asyncio
    async def test_authenticated_with_admin_access(self, tmp_path: Path) -> None:
        """Should report PRESENT for ADMIN permission."""
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)

        with patch("prep.run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                "Logged in",  # gh auth status
                "ADMIN",  # gh repo view
            ]
            check = await auditor._check_gh_cli()

        assert check.status == AuditCheckStatus.PRESENT

    @pytest.mark.asyncio
    async def test_not_authenticated(self, tmp_path: Path) -> None:
        """Should report MISSING when gh auth fails."""
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)

        with patch("prep.run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = RuntimeError("not logged in")
            check = await auditor._check_gh_cli()

        assert check.status == AuditCheckStatus.MISSING
        assert check.critical is True

    @pytest.mark.asyncio
    async def test_read_only_access(self, tmp_path: Path) -> None:
        """Should report PARTIAL when access is read-only."""
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)

        with patch("prep.run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                "Logged in",  # gh auth status
                "READ",  # gh repo view
            ]
            check = await auditor._check_gh_cli()

        assert check.status == AuditCheckStatus.PARTIAL
        assert "read-only" in check.detail


# ---------------------------------------------------------------------------
# Label detection
# ---------------------------------------------------------------------------


class TestCheckLabels:
    """Tests for RepoAuditor._check_labels."""

    @pytest.mark.asyncio
    async def test_all_labels_present(self, tmp_path: Path) -> None:
        """Should report PRESENT when all Hydra labels exist."""
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        # Build the full label list from config
        all_labels = auditor._get_hydra_labels()

        with patch("prep.run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "\n".join(all_labels)
            check = await auditor._check_labels()

        assert check.status == AuditCheckStatus.PRESENT

    @pytest.mark.asyncio
    async def test_partial_labels(self, tmp_path: Path) -> None:
        """Should report PARTIAL when some labels are missing."""
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)
        all_labels = auditor._get_hydra_labels()

        with patch("prep.run_subprocess", new_callable=AsyncMock) as mock_run:
            # Return only first half of labels
            mock_run.return_value = "\n".join(all_labels[: len(all_labels) // 2])
            check = await auditor._check_labels()

        assert check.status == AuditCheckStatus.PARTIAL

    @pytest.mark.asyncio
    async def test_no_labels(self, tmp_path: Path) -> None:
        """Should report MISSING when no Hydra labels exist."""
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)

        with patch("prep.run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "bug\nenhancement\ndocumentation"
            check = await auditor._check_labels()

        assert check.status == AuditCheckStatus.MISSING

    @pytest.mark.asyncio
    async def test_label_check_handles_gh_error(self, tmp_path: Path) -> None:
        """Should report MISSING when gh label list fails."""
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)

        with patch("prep.run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = RuntimeError("gh failed")
            check = await auditor._check_labels()

        assert check.status == AuditCheckStatus.MISSING


# ---------------------------------------------------------------------------
# Full audit run
# ---------------------------------------------------------------------------


class TestRunAudit:
    """Tests for the full audit workflow."""

    @pytest.mark.asyncio
    async def test_run_audit_produces_all_checks(self, tmp_path: Path) -> None:
        """Should produce checks for all categories."""
        config = ConfigFactory.create(repo_root=tmp_path)
        from prep import RepoAuditor

        auditor = RepoAuditor(config)

        with patch("prep.run_subprocess", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = RuntimeError("not available")
            result = await auditor.run_audit()

        check_names = [c.name for c in result.checks]
        assert "Language" in check_names
        assert "Makefile" in check_names
        assert "CI" in check_names
        assert "Git hooks" in check_names
        assert "Linting" in check_names
        assert "Type check" in check_names
        assert "Tests" in check_names
        assert "Pkg manager" in check_names
        assert "gh CLI" in check_names
        assert "Labels" in check_names


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCliAudit:
    """Tests for the --audit CLI flag."""

    def test_audit_flag_parsed(self) -> None:
        """Should parse --audit flag."""
        from cli import parse_args

        args = parse_args(["--audit"])
        assert args.audit is True

    def test_audit_flag_default_false(self) -> None:
        """Should default to False."""
        from cli import parse_args

        args = parse_args([])
        assert args.audit is False
