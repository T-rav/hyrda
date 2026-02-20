"""Tests for dx/hydra/config.py."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

# conftest.py already inserts the hydra package directory into sys.path
from config import HydraConfig, _detect_repo_slug, _find_repo_root

# ---------------------------------------------------------------------------
# _find_repo_root
# ---------------------------------------------------------------------------


class TestFindRepoRoot:
    """Tests for the _find_repo_root() helper."""

    def test_finds_git_root_from_repo_subdirectory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should return the directory containing .git when walking up."""
        # Arrange
        git_root = tmp_path / "project"
        git_root.mkdir()
        (git_root / ".git").mkdir()
        nested = git_root / "src" / "pkg"
        nested.mkdir(parents=True)

        monkeypatch.chdir(nested)

        # Act
        result = _find_repo_root()

        # Assert
        assert result == git_root.resolve()

    def test_finds_git_root_from_repo_root_itself(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should return cwd when .git exists directly in cwd."""
        # Arrange
        git_root = tmp_path / "project"
        git_root.mkdir()
        (git_root / ".git").mkdir()

        monkeypatch.chdir(git_root)

        # Act
        result = _find_repo_root()

        # Assert
        assert result == git_root.resolve()

    def test_returns_cwd_when_no_git_root_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should fall back to cwd when no .git directory exists in the hierarchy."""
        # Arrange – tmp_path has no .git anywhere above it inside tmp_path
        no_git_dir = tmp_path / "no_git"
        no_git_dir.mkdir()
        monkeypatch.chdir(no_git_dir)

        # Act
        result = _find_repo_root()

        # Assert – result is a resolved Path (either cwd or a real parent that
        # happens to contain .git on the host machine; we only care it is a Path)
        assert isinstance(result, Path)

    def test_returns_resolved_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The returned path should be an absolute resolved Path."""
        # Arrange
        git_root = tmp_path / "proj"
        git_root.mkdir()
        (git_root / ".git").mkdir()
        monkeypatch.chdir(git_root)

        # Act
        result = _find_repo_root()

        # Assert
        assert result.is_absolute()

    def test_finds_git_root_initialized_with_subprocess(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should find the root of a real git repo created with git init."""
        # Arrange
        git_root = tmp_path / "real_repo"
        git_root.mkdir()
        subprocess.run(["git", "init", str(git_root)], check=True, capture_output=True)
        nested = git_root / "a" / "b" / "c"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)

        # Act
        result = _find_repo_root()

        # Assert
        assert result == git_root.resolve()


# ---------------------------------------------------------------------------
# _detect_repo_slug
# ---------------------------------------------------------------------------


class TestDetectRepoSlug:
    """Tests for the _detect_repo_slug() helper."""

    def test_ssh_remote_url(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should parse SSH remote URL and strip .git suffix."""
        # Arrange
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *_args, **_kwargs: subprocess.CompletedProcess(
                args=[], returncode=0, stdout="git@github.com:owner/repo.git\n"
            ),
        )

        # Act
        result = _detect_repo_slug(tmp_path)

        # Assert
        assert result == "owner/repo"

    def test_https_remote_url(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should parse HTTPS remote URL and strip .git suffix."""
        # Arrange
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *_args, **_kwargs: subprocess.CompletedProcess(
                args=[], returncode=0, stdout="https://github.com/owner/repo.git\n"
            ),
        )

        # Act
        result = _detect_repo_slug(tmp_path)

        # Assert
        assert result == "owner/repo"

    def test_ssh_url_without_git_suffix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should parse SSH remote URL without .git suffix."""
        # Arrange
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *_args, **_kwargs: subprocess.CompletedProcess(
                args=[], returncode=0, stdout="git@github.com:owner/repo\n"
            ),
        )

        # Act
        result = _detect_repo_slug(tmp_path)

        # Assert
        assert result == "owner/repo"

    def test_https_url_without_git_suffix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should parse HTTPS remote URL without .git suffix."""
        # Arrange
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *_args, **_kwargs: subprocess.CompletedProcess(
                args=[], returncode=0, stdout="https://github.com/owner/repo\n"
            ),
        )

        # Act
        result = _detect_repo_slug(tmp_path)

        # Assert
        assert result == "owner/repo"

    def test_empty_remote_returns_empty_string(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should return empty string when git remote output is empty."""
        # Arrange
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *_args, **_kwargs: subprocess.CompletedProcess(
                args=[], returncode=0, stdout=""
            ),
        )

        # Act
        result = _detect_repo_slug(tmp_path)

        # Assert
        assert result == ""

    def test_subprocess_file_not_found_returns_empty_string(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should return empty string when git is not installed."""

        # Arrange
        def _raise(*_args: object, **_kwargs: object) -> None:
            raise FileNotFoundError("git not found")

        monkeypatch.setattr(subprocess, "run", _raise)

        # Act
        result = _detect_repo_slug(tmp_path)

        # Assert
        assert result == ""

    def test_subprocess_os_error_returns_empty_string(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should return empty string on OSError."""

        # Arrange
        def _raise(*_args: object, **_kwargs: object) -> None:
            raise OSError("subprocess failed")

        monkeypatch.setattr(subprocess, "run", _raise)

        # Act
        result = _detect_repo_slug(tmp_path)

        # Assert
        assert result == ""

    def test_non_github_remote_returns_empty_string(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should return empty string for non-GitHub hosts."""
        # Arrange
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *_args, **_kwargs: subprocess.CompletedProcess(
                args=[], returncode=0, stdout="https://gitlab.com/owner/repo.git\n"
            ),
        )

        # Act
        result = _detect_repo_slug(tmp_path)

        # Assert
        assert result == ""


# ---------------------------------------------------------------------------
# HydraConfig – defaults
# ---------------------------------------------------------------------------


class TestHydraConfigDefaults:
    """Tests that default field values are correct."""

    def test_label_default(self, tmp_path: Path) -> None:
        # Arrange / Act
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )

        # Assert
        assert cfg.ready_label == ["hydra-ready"]

    def test_batch_size_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.batch_size == 15

    def test_repo_auto_detects_from_git_remote(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        # repo is auto-detected from git remote; in non-git dirs it falls back to ""
        assert isinstance(cfg.repo, str)

    def test_max_workers_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_workers == 2

    def test_find_label_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.find_label == ["hydra-find"]

    def test_max_planners_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_planners == 1

    def test_max_reviewers_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_reviewers == 3

    def test_max_hitl_workers_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_hitl_workers == 1

    def test_hitl_active_label_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.hitl_active_label == ["hydra-hitl-active"]

    def test_max_budget_usd_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_budget_usd == pytest.approx(0)

    def test_model_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.model == "sonnet"

    def test_review_model_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.review_model == "opus"

    def test_review_budget_usd_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.review_budget_usd == pytest.approx(0)

    def test_main_branch_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.main_branch == "main"

    def test_dashboard_port_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.dashboard_port == 5555

    def test_dashboard_enabled_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.dashboard_enabled is True

    def test_dry_run_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.dry_run is False


# ---------------------------------------------------------------------------
# HydraConfig – custom values override defaults
# ---------------------------------------------------------------------------


class TestHydraConfigCustomValues:
    """Tests that custom constructor values take precedence over defaults."""

    def test_custom_label(self, tmp_path: Path) -> None:
        # Arrange / Act
        cfg = HydraConfig(
            ready_label=["sprint"],
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )

        # Assert
        assert cfg.ready_label == ["sprint"]

    def test_custom_batch_size(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            batch_size=10,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.batch_size == 10

    def test_custom_repo(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo="myorg/myrepo",
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.repo == "myorg/myrepo"

    def test_custom_max_workers(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            max_workers=3,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_workers == 3

    def test_custom_max_budget_usd(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            max_budget_usd=20.0,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_budget_usd == pytest.approx(20.0)

    def test_custom_model(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            model="haiku",
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.model == "haiku"

    def test_custom_review_model(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            review_model="sonnet",
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.review_model == "sonnet"

    def test_custom_review_budget_usd(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            review_budget_usd=10.0,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.review_budget_usd == pytest.approx(10.0)

    def test_custom_main_branch(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            main_branch="develop",
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.main_branch == "develop"

    def test_custom_dashboard_port(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            dashboard_port=8080,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.dashboard_port == 8080

    def test_custom_dashboard_enabled_false(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            dashboard_enabled=False,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.dashboard_enabled is False

    def test_custom_max_hitl_workers(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            max_hitl_workers=3,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_hitl_workers == 3

    def test_custom_hitl_active_label(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            hitl_active_label=["custom-active"],
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.hitl_active_label == ["custom-active"]

    def test_custom_dry_run_true(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            dry_run=True,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.dry_run is True


# ---------------------------------------------------------------------------
# HydraConfig – path resolution via resolve_paths model_validator
# ---------------------------------------------------------------------------


class TestHydraConfigPathResolution:
    """Tests for the resolve_paths model validator."""

    def test_explicit_repo_root_is_preserved(self, tmp_path: Path) -> None:
        # Arrange
        explicit_root = tmp_path / "my_repo"
        explicit_root.mkdir()

        # Act
        cfg = HydraConfig(
            repo_root=explicit_root,
            worktree_base=explicit_root / "wt",
            state_file=explicit_root / "state.json",
        )

        # Assert
        assert cfg.repo_root == explicit_root

    def test_explicit_worktree_base_is_preserved(self, tmp_path: Path) -> None:
        # Arrange
        explicit_root = tmp_path / "repo"
        explicit_wt = tmp_path / "worktrees"

        # Act
        cfg = HydraConfig(
            repo_root=explicit_root,
            worktree_base=explicit_wt,
            state_file=explicit_root / "state.json",
        )

        # Assert
        assert cfg.worktree_base == explicit_wt

    def test_explicit_state_file_is_preserved(self, tmp_path: Path) -> None:
        # Arrange
        explicit_root = tmp_path / "repo"
        explicit_state = tmp_path / "custom-state.json"

        # Act
        cfg = HydraConfig(
            repo_root=explicit_root,
            worktree_base=explicit_root / "wt",
            state_file=explicit_state,
        )

        # Assert
        assert cfg.state_file == explicit_state

    def test_default_worktree_base_derived_from_repo_root(self, tmp_path: Path) -> None:
        """When worktree_base is left as Path('.'), it should be derived as repo_root.parent / 'hyrda-worktrees'."""
        # Arrange
        git_root = tmp_path / "hyrda"
        git_root.mkdir()
        (git_root / ".git").mkdir()

        # Act – pass repo_root explicitly but leave worktree_base and state_file at their defaults (Path("."))
        cfg = HydraConfig(repo_root=git_root)

        # Assert
        assert cfg.worktree_base == git_root.parent / "hyrda-worktrees"

    def test_default_state_file_derived_from_repo_root(self, tmp_path: Path) -> None:
        """When state_file is left as Path('.'), it should resolve to repo_root / '.hydra/state.json'."""
        # Arrange
        git_root = tmp_path / "hyrda"
        git_root.mkdir()
        (git_root / ".git").mkdir()

        # Act
        cfg = HydraConfig(repo_root=git_root)

        # Assert
        assert cfg.state_file == git_root / ".hydra" / "state.json"

    def test_auto_detected_repo_root_is_absolute(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When repo_root is not provided, the auto-detected value must be absolute."""
        # Arrange – place cwd inside a git repo
        git_root = tmp_path / "autodetect_repo"
        git_root.mkdir()
        (git_root / ".git").mkdir()
        monkeypatch.chdir(git_root)

        # Act
        cfg = HydraConfig()

        # Assert
        assert cfg.repo_root.is_absolute()

    def test_auto_detected_worktree_base_uses_hyrda_worktrees_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auto-derived worktree_base should be named 'hyrda-worktrees'."""
        # Arrange
        git_root = tmp_path / "repo"
        git_root.mkdir()
        (git_root / ".git").mkdir()
        monkeypatch.chdir(git_root)

        # Act
        cfg = HydraConfig()

        # Assert
        assert cfg.worktree_base.name == "hyrda-worktrees"

    def test_auto_detected_state_file_named_hydra_state_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auto-derived state_file should be inside .hydra/ and named 'state.json'."""
        # Arrange
        git_root = tmp_path / "repo"
        git_root.mkdir()
        (git_root / ".git").mkdir()
        monkeypatch.chdir(git_root)

        # Act
        cfg = HydraConfig()

        # Assert
        assert cfg.state_file.name == "state.json"
        assert cfg.state_file.parent.name == ".hydra"


# ---------------------------------------------------------------------------
# HydraConfig – validation constraints
# ---------------------------------------------------------------------------


class TestHydraConfigValidationConstraints:
    """Tests for Pydantic field constraints (ge/le/gt)."""

    # batch_size: ge=1, le=50

    def test_batch_size_minimum_boundary(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            batch_size=1,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.batch_size == 1

    def test_batch_size_maximum_boundary(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            batch_size=50,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.batch_size == 50

    def test_batch_size_below_minimum_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            HydraConfig(
                batch_size=0,
                repo_root=tmp_path,
                worktree_base=tmp_path / "wt",
                state_file=tmp_path / "s.json",
            )

    def test_batch_size_above_maximum_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            HydraConfig(
                batch_size=51,
                repo_root=tmp_path,
                worktree_base=tmp_path / "wt",
                state_file=tmp_path / "s.json",
            )

    # max_workers: ge=1, le=10

    def test_max_workers_minimum_boundary(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            max_workers=1,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_workers == 1

    def test_max_workers_maximum_boundary(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            max_workers=10,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_workers == 10

    def test_max_workers_below_minimum_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            HydraConfig(
                max_workers=0,
                repo_root=tmp_path,
                worktree_base=tmp_path / "wt",
                state_file=tmp_path / "s.json",
            )

    def test_max_workers_above_maximum_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            HydraConfig(
                max_workers=11,
                repo_root=tmp_path,
                worktree_base=tmp_path / "wt",
                state_file=tmp_path / "s.json",
            )

    # max_planners: ge=1, le=10

    def test_max_planners_minimum_boundary(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            max_planners=1,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_planners == 1

    def test_max_planners_maximum_boundary(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            max_planners=10,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_planners == 10

    def test_max_planners_below_minimum_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            HydraConfig(
                max_planners=0,
                repo_root=tmp_path,
                worktree_base=tmp_path / "wt",
                state_file=tmp_path / "s.json",
            )

    def test_max_planners_above_maximum_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            HydraConfig(
                max_planners=11,
                repo_root=tmp_path,
                worktree_base=tmp_path / "wt",
                state_file=tmp_path / "s.json",
            )

    # max_reviewers: ge=1, le=10

    def test_max_reviewers_minimum_boundary(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            max_reviewers=1,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_reviewers == 1

    def test_max_reviewers_maximum_boundary(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            max_reviewers=10,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_reviewers == 10

    def test_max_reviewers_below_minimum_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            HydraConfig(
                max_reviewers=0,
                repo_root=tmp_path,
                worktree_base=tmp_path / "wt",
                state_file=tmp_path / "s.json",
            )

    def test_max_reviewers_above_maximum_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            HydraConfig(
                max_reviewers=11,
                repo_root=tmp_path,
                worktree_base=tmp_path / "wt",
                state_file=tmp_path / "s.json",
            )

    # max_hitl_workers: ge=1, le=5

    def test_max_hitl_workers_minimum_boundary(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            max_hitl_workers=1,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_hitl_workers == 1

    def test_max_hitl_workers_maximum_boundary(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            max_hitl_workers=5,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_hitl_workers == 5

    def test_max_hitl_workers_below_minimum_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            HydraConfig(
                max_hitl_workers=0,
                repo_root=tmp_path,
                worktree_base=tmp_path / "wt",
                state_file=tmp_path / "s.json",
            )

    def test_max_hitl_workers_above_maximum_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            HydraConfig(
                max_hitl_workers=6,
                repo_root=tmp_path,
                worktree_base=tmp_path / "wt",
                state_file=tmp_path / "s.json",
            )

    # max_budget_usd: gt=0

    def test_max_budget_usd_positive_value_accepted(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            max_budget_usd=0.01,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_budget_usd == pytest.approx(0.01)

    def test_max_budget_usd_zero_is_unlimited(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            max_budget_usd=0.0,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_budget_usd == pytest.approx(0)

    def test_max_budget_usd_negative_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            HydraConfig(
                max_budget_usd=-1.0,
                repo_root=tmp_path,
                worktree_base=tmp_path / "wt",
                state_file=tmp_path / "s.json",
            )

    # review_budget_usd: gt=0

    def test_review_budget_usd_positive_value_accepted(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            review_budget_usd=0.50,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.review_budget_usd == pytest.approx(0.50)

    def test_review_budget_usd_zero_is_unlimited(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            review_budget_usd=0.0,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.review_budget_usd == pytest.approx(0)

    # dashboard_port: ge=1024, le=65535

    def test_dashboard_port_minimum_boundary(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            dashboard_port=1024,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.dashboard_port == 1024

    def test_dashboard_port_maximum_boundary(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            dashboard_port=65535,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.dashboard_port == 65535

    def test_dashboard_port_below_minimum_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            HydraConfig(
                dashboard_port=1023,
                repo_root=tmp_path,
                worktree_base=tmp_path / "wt",
                state_file=tmp_path / "s.json",
            )

    def test_dashboard_port_above_maximum_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            HydraConfig(
                dashboard_port=65536,
                repo_root=tmp_path,
                worktree_base=tmp_path / "wt",
                state_file=tmp_path / "s.json",
            )

    # ci_check_timeout: ge=30, le=3600

    def test_ci_check_timeout_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.ci_check_timeout == 600

    def test_ci_check_timeout_minimum_boundary(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            ci_check_timeout=30,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.ci_check_timeout == 30

    def test_ci_check_timeout_below_minimum_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            HydraConfig(
                ci_check_timeout=29,
                repo_root=tmp_path,
                worktree_base=tmp_path / "wt",
                state_file=tmp_path / "s.json",
            )

    # ci_poll_interval: ge=5, le=120

    def test_ci_poll_interval_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.ci_poll_interval == 30

    def test_ci_poll_interval_minimum_boundary(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            ci_poll_interval=5,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.ci_poll_interval == 5

    def test_ci_poll_interval_below_minimum_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            HydraConfig(
                ci_poll_interval=4,
                repo_root=tmp_path,
                worktree_base=tmp_path / "wt",
                state_file=tmp_path / "s.json",
            )

    # max_ci_fix_attempts: ge=0, le=5

    def test_max_ci_fix_attempts_default(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_ci_fix_attempts == 2

    def test_max_ci_fix_attempts_zero_disables(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            max_ci_fix_attempts=0,
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.max_ci_fix_attempts == 0

    def test_max_ci_fix_attempts_above_maximum_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            HydraConfig(
                max_ci_fix_attempts=6,
                repo_root=tmp_path,
                worktree_base=tmp_path / "wt",
                state_file=tmp_path / "s.json",
            )


# ---------------------------------------------------------------------------
# HydraConfig – gh_token resolution
# ---------------------------------------------------------------------------


class TestHydraConfigGhToken:
    """Tests for the gh_token field and HYDRA_GH_TOKEN env var resolution."""

    def test_gh_token_default_is_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("HYDRA_GH_TOKEN", raising=False)
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.gh_token == ""

    def test_gh_token_explicit_value_preserved(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            gh_token="ghp_explicit123",
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.gh_token == "ghp_explicit123"

    def test_gh_token_picks_up_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HYDRA_GH_TOKEN", "ghp_from_env")
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.gh_token == "ghp_from_env"

    def test_gh_token_explicit_overrides_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HYDRA_GH_TOKEN", "ghp_from_env")
        cfg = HydraConfig(
            gh_token="ghp_explicit",
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.gh_token == "ghp_explicit"


# ---------------------------------------------------------------------------
# HydraConfig – git identity resolution
# ---------------------------------------------------------------------------


class TestHydraConfigGitIdentity:
    """Tests for git_user_name/git_user_email fields and env var resolution."""

    def test_git_user_name_default_is_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("HYDRA_GIT_USER_NAME", raising=False)
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.git_user_name == ""

    def test_git_user_email_default_is_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("HYDRA_GIT_USER_EMAIL", raising=False)
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.git_user_email == ""

    def test_git_user_name_explicit_value_preserved(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            git_user_name="Bot",
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.git_user_name == "Bot"

    def test_git_user_email_explicit_value_preserved(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            git_user_email="bot@example.com",
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.git_user_email == "bot@example.com"

    def test_git_user_name_picks_up_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HYDRA_GIT_USER_NAME", "EnvBot")
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.git_user_name == "EnvBot"

    def test_git_user_email_picks_up_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HYDRA_GIT_USER_EMAIL", "env@example.com")
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.git_user_email == "env@example.com"

    def test_git_user_name_explicit_overrides_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HYDRA_GIT_USER_NAME", "EnvBot")
        cfg = HydraConfig(
            git_user_name="ExplicitBot",
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.git_user_name == "ExplicitBot"

    def test_git_user_email_explicit_overrides_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HYDRA_GIT_USER_EMAIL", "env@example.com")
        cfg = HydraConfig(
            git_user_email="explicit@example.com",
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.git_user_email == "explicit@example.com"


# ---------------------------------------------------------------------------
# HydraConfig – hitl_active_label env var override
# ---------------------------------------------------------------------------


class TestHydraConfigHitlActiveLabel:
    """Tests for hitl_active_label env var override."""

    def test_hitl_active_label_env_var_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HYDRA_LABEL_HITL_ACTIVE", "custom-active")
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.hitl_active_label == ["custom-active"]

    def test_hitl_active_label_env_var_not_applied_when_explicit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HYDRA_LABEL_HITL_ACTIVE", "env-active")
        cfg = HydraConfig(
            hitl_active_label=["explicit-active"],
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.hitl_active_label == ["explicit-active"]


# ---------------------------------------------------------------------------
# HydraConfig – branch_for_issue / worktree_path_for_issue helpers
# ---------------------------------------------------------------------------


class TestBranchForIssue:
    """Tests for HydraConfig.branch_for_issue()."""

    def test_returns_canonical_branch_name(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.branch_for_issue(42) == "agent/issue-42"

    def test_single_digit_issue(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.branch_for_issue(1) == "agent/issue-1"

    def test_large_issue_number(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.branch_for_issue(99999) == "agent/issue-99999"


class TestWorktreePathForIssue:
    """Tests for HydraConfig.worktree_path_for_issue()."""

    def test_returns_path_under_worktree_base(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.worktree_path_for_issue(42) == tmp_path / "wt" / "issue-42"

    def test_single_digit_issue(self, tmp_path: Path) -> None:
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.worktree_path_for_issue(1) == tmp_path / "wt" / "issue-1"

    def test_uses_configured_worktree_base(self, tmp_path: Path) -> None:
        custom_base = tmp_path / "custom-worktrees"
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=custom_base,
            state_file=tmp_path / "s.json",
        )
        assert cfg.worktree_path_for_issue(7) == custom_base / "issue-7"
