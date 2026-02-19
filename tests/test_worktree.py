"""Tests for dx/hydra/worktree.py — WorktreeManager."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from worktree import WorktreeManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_proc(
    returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""
) -> AsyncMock:
    """Build a minimal mock subprocess object."""
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


# ---------------------------------------------------------------------------
# WorktreeManager.exists
# ---------------------------------------------------------------------------


class TestExists:
    """Tests for WorktreeManager.exists."""

    def test_returns_true_when_worktree_dir_exists(
        self, config, tmp_path: Path
    ) -> None:
        """exists should return True when the issue directory is present."""
        manager = WorktreeManager(config)
        wt_path = config.worktree_base / "issue-7"
        wt_path.mkdir(parents=True, exist_ok=True)

        assert manager.exists(7) is True

    def test_returns_false_when_worktree_dir_absent(self, config) -> None:
        """exists should return False when no directory exists for the issue."""
        manager = WorktreeManager(config)
        assert manager.exists(999) is False


# ---------------------------------------------------------------------------
# WorktreeManager.create
# ---------------------------------------------------------------------------


class TestCreate:
    """Tests for WorktreeManager.create."""

    @pytest.mark.asyncio
    async def test_create_calls_git_branch_and_worktree_add(
        self, config, tmp_path: Path
    ) -> None:
        """create should call 'git branch -f' then 'git worktree add'."""
        manager = WorktreeManager(config)

        # Pre-create the base directory so mkdir doesn't cause issues
        config.worktree_base.mkdir(parents=True, exist_ok=True)

        success_proc = _make_proc(returncode=0)

        with (
            patch(
                "asyncio.create_subprocess_exec", return_value=success_proc
            ) as mock_exec,
            patch.object(manager, "_remote_branch_exists", return_value=False),
            patch.object(manager, "_setup_env"),
            patch.object(manager, "_install_hooks", new_callable=AsyncMock),
        ):
            # _setup_env and _install_hooks must not fail; patch them out
            await manager.create(issue_number=7, branch="agent/issue-7")

        calls = mock_exec.call_args_list
        # First call: git branch -f
        assert calls[0].args[:4] == ("git", "branch", "-f", "agent/issue-7")
        # Second call: git worktree add
        assert calls[1].args[:3] == ("git", "worktree", "add")

    @pytest.mark.asyncio
    async def test_create_fetches_remote_branch_when_exists(
        self, config, tmp_path: Path
    ) -> None:
        """create should fetch the remote branch instead of force-creating from main."""
        manager = WorktreeManager(config)
        config.worktree_base.mkdir(parents=True, exist_ok=True)

        success_proc = _make_proc(returncode=0)

        with (
            patch(
                "asyncio.create_subprocess_exec", return_value=success_proc
            ) as mock_exec,
            patch.object(
                manager, "_remote_branch_exists", return_value=True
            ) as mock_remote,
            patch.object(manager, "_setup_env"),
            patch.object(manager, "_install_hooks", new_callable=AsyncMock),
        ):
            await manager.create(issue_number=7, branch="agent/issue-7")

        mock_remote.assert_awaited_once_with("agent/issue-7")
        calls = mock_exec.call_args_list
        # First call should be git fetch origin <branch>:<branch>
        assert calls[0].args[:3] == ("git", "fetch", "origin")
        assert "agent/issue-7:agent/issue-7" in calls[0].args
        # Should NOT have git branch -f
        for call in calls:
            assert call.args[:3] != ("git", "branch", "-f"), (
                "Should not force-create branch when remote exists"
            )

    @pytest.mark.asyncio
    async def test_create_fresh_branch_when_no_remote(
        self, config, tmp_path: Path
    ) -> None:
        """create should force-create branch from main when no remote branch exists."""
        manager = WorktreeManager(config)
        config.worktree_base.mkdir(parents=True, exist_ok=True)

        success_proc = _make_proc(returncode=0)

        with (
            patch(
                "asyncio.create_subprocess_exec", return_value=success_proc
            ) as mock_exec,
            patch.object(manager, "_remote_branch_exists", return_value=False),
            patch.object(manager, "_setup_env"),
            patch.object(manager, "_install_hooks", new_callable=AsyncMock),
        ):
            await manager.create(issue_number=7, branch="agent/issue-7")

        calls = mock_exec.call_args_list
        # First call should be git branch -f
        assert calls[0].args[:4] == ("git", "branch", "-f", "agent/issue-7")

    @pytest.mark.asyncio
    async def test_create_calls_setup_env_and_install_hooks(
        self, config, tmp_path: Path
    ) -> None:
        """create should invoke _setup_env and _install_hooks after adding the worktree."""
        manager = WorktreeManager(config)
        config.worktree_base.mkdir(parents=True, exist_ok=True)

        success_proc = _make_proc()

        setup_env = MagicMock()
        install_hooks = AsyncMock()

        with (
            patch("asyncio.create_subprocess_exec", return_value=success_proc),
            patch.object(manager, "_remote_branch_exists", return_value=False),
            patch.object(manager, "_setup_env", setup_env),
            patch.object(manager, "_install_hooks", install_hooks),
        ):
            result = await manager.create(issue_number=7, branch="agent/issue-7")

        setup_env.assert_called_once()
        install_hooks.assert_awaited_once()
        assert result == config.worktree_base / "issue-7"

    @pytest.mark.asyncio
    async def test_create_returns_correct_path(self, config, tmp_path: Path) -> None:
        """create should return <worktree_base>/issue-<number>."""
        manager = WorktreeManager(config)
        config.worktree_base.mkdir(parents=True, exist_ok=True)

        success_proc = _make_proc()

        with (
            patch("asyncio.create_subprocess_exec", return_value=success_proc),
            patch.object(manager, "_remote_branch_exists", return_value=False),
            patch.object(manager, "_setup_env"),
            patch.object(manager, "_install_hooks", new_callable=AsyncMock),
        ):
            result = await manager.create(issue_number=99, branch="agent/issue-99")

        assert result == config.worktree_base / "issue-99"

    @pytest.mark.asyncio
    async def test_create_dry_run_skips_git_commands(
        self, dry_config, tmp_path: Path
    ) -> None:
        """In dry-run mode, create should not call any git subprocesses."""
        manager = WorktreeManager(dry_config)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            result = await manager.create(issue_number=7, branch="agent/issue-7")

        mock_exec.assert_not_called()
        assert result == dry_config.worktree_base / "issue-7"


# ---------------------------------------------------------------------------
# WorktreeManager.destroy
# ---------------------------------------------------------------------------


class TestDestroy:
    """Tests for WorktreeManager.destroy."""

    @pytest.mark.asyncio
    async def test_destroy_calls_worktree_remove_and_branch_delete(
        self, config, tmp_path: Path
    ) -> None:
        """destroy should call 'git worktree remove' and 'git branch -D'."""
        manager = WorktreeManager(config)

        # Simulate existing worktree path
        wt_path = config.worktree_base / "issue-7"
        wt_path.mkdir(parents=True, exist_ok=True)

        success_proc = _make_proc()

        with patch(
            "asyncio.create_subprocess_exec", return_value=success_proc
        ) as mock_exec:
            await manager.destroy(issue_number=7)

        args_list = [c.args for c in mock_exec.call_args_list]
        assert ("git", "worktree", "remove", str(wt_path), "--force") in args_list
        assert ("git", "branch", "-D", "agent/issue-7") in args_list

    @pytest.mark.asyncio
    async def test_destroy_handles_non_existent_worktree_gracefully(
        self, config, tmp_path: Path
    ) -> None:
        """destroy should not crash if the worktree directory does not exist."""
        manager = WorktreeManager(config)

        # wt_path does NOT exist — destroy should not call worktree remove
        success_proc = _make_proc()

        with patch(
            "asyncio.create_subprocess_exec", return_value=success_proc
        ) as mock_exec:
            await manager.destroy(issue_number=999)

        args_list = [c.args for c in mock_exec.call_args_list]
        # git worktree remove should NOT have been called
        for args in args_list:
            assert args[:3] != ("git", "worktree", "remove"), (
                "Should not attempt worktree remove when path does not exist"
            )

    @pytest.mark.asyncio
    async def test_destroy_tolerates_missing_branch(
        self, config, tmp_path: Path
    ) -> None:
        """destroy should swallow RuntimeError from 'git branch -D' gracefully."""
        manager = WorktreeManager(config)

        wt_path = config.worktree_base / "issue-7"
        wt_path.mkdir(parents=True, exist_ok=True)

        remove_proc = _make_proc(returncode=0)
        branch_delete_proc = _make_proc(returncode=1, stderr=b"error: branch not found")

        call_count = 0

        async def fake_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return remove_proc  # worktree remove succeeds
            return branch_delete_proc  # branch -D fails

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            # Should NOT raise
            await manager.destroy(issue_number=7)

    @pytest.mark.asyncio
    async def test_destroy_dry_run_skips_git_commands(
        self, dry_config, tmp_path: Path
    ) -> None:
        """In dry-run mode, destroy should not call any subprocesses."""
        manager = WorktreeManager(dry_config)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            await manager.destroy(issue_number=7)

        mock_exec.assert_not_called()


# ---------------------------------------------------------------------------
# WorktreeManager.destroy_all
# ---------------------------------------------------------------------------


class TestDestroyAll:
    """Tests for WorktreeManager.destroy_all."""

    @pytest.mark.asyncio
    async def test_destroy_all_iterates_issue_directories(
        self, config, tmp_path: Path
    ) -> None:
        """destroy_all should call destroy for each issue-N directory."""
        manager = WorktreeManager(config)

        # Create two issue directories
        (config.worktree_base / "issue-1").mkdir(parents=True, exist_ok=True)
        (config.worktree_base / "issue-2").mkdir(parents=True, exist_ok=True)

        destroyed: list[int] = []

        async def fake_destroy(issue_number: int) -> None:
            destroyed.append(issue_number)

        with (
            patch.object(manager, "destroy", side_effect=fake_destroy),
            patch.object(manager, "_run", new_callable=AsyncMock),
        ):
            # Also patch _run for the final prune
            await manager.destroy_all()

        assert sorted(destroyed) == [1, 2]

    @pytest.mark.asyncio
    async def test_destroy_all_noop_when_base_missing(self, config) -> None:
        """destroy_all should return immediately if worktree_base does not exist."""
        manager = WorktreeManager(config)
        # config.worktree_base was NOT created

        with patch.object(manager, "destroy", new_callable=AsyncMock) as mock_destroy:
            await manager.destroy_all()

        mock_destroy.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_destroy_all_ignores_non_issue_dirs(
        self, config, tmp_path: Path
    ) -> None:
        """destroy_all should skip directories not named issue-N."""
        manager = WorktreeManager(config)

        (config.worktree_base / "random-dir").mkdir(parents=True, exist_ok=True)
        (config.worktree_base / "issue-5").mkdir(parents=True, exist_ok=True)

        destroyed: list[int] = []

        async def fake_destroy(issue_number: int) -> None:
            destroyed.append(issue_number)

        with (
            patch.object(manager, "destroy", side_effect=fake_destroy),
            patch.object(manager, "_run", new_callable=AsyncMock),
        ):
            await manager.destroy_all()

        assert destroyed == [5]


# ---------------------------------------------------------------------------
# WorktreeManager.rebase
# ---------------------------------------------------------------------------


class TestRebase:
    """Tests for WorktreeManager.rebase."""

    @pytest.mark.asyncio
    async def test_rebase_success_returns_true(self, config, tmp_path: Path) -> None:
        """rebase should return True when both fetch and rebase succeed."""
        manager = WorktreeManager(config)
        success_proc = _make_proc()

        with patch("asyncio.create_subprocess_exec", return_value=success_proc):
            result = await manager.rebase(tmp_path, "agent/issue-7")

        assert result is True

    @pytest.mark.asyncio
    async def test_rebase_failure_aborts_and_returns_false(
        self, config, tmp_path: Path
    ) -> None:
        """rebase should abort and return False when rebase conflicts occur."""
        manager = WorktreeManager(config)

        fetch_proc = _make_proc(returncode=0)
        rebase_fail_proc = _make_proc(
            returncode=1, stderr=b"CONFLICT (content): Merge conflict"
        )
        abort_proc = _make_proc(returncode=0)

        call_count = 0

        async def fake_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return fetch_proc  # git fetch succeeds
            if call_count == 2:
                return rebase_fail_proc  # git rebase fails
            return abort_proc  # git rebase --abort

        with patch(
            "asyncio.create_subprocess_exec", side_effect=fake_exec
        ) as mock_exec:
            result = await manager.rebase(tmp_path, "agent/issue-7")

        assert result is False
        # Verify abort was called
        abort_calls = [c for c in mock_exec.call_args_list if "--abort" in c.args]
        assert len(abort_calls) == 1

    @pytest.mark.asyncio
    async def test_rebase_fetch_failure_returns_false(
        self, config, tmp_path: Path
    ) -> None:
        """rebase should return False if the initial fetch fails."""
        manager = WorktreeManager(config)

        fetch_fail_proc = _make_proc(returncode=1, stderr=b"fatal: network error")
        abort_proc = _make_proc(returncode=0)

        call_count = 0

        async def fake_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return fetch_fail_proc
            return abort_proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            result = await manager.rebase(tmp_path, "agent/issue-7")

        assert result is False


# ---------------------------------------------------------------------------
# WorktreeManager._remote_branch_exists
# ---------------------------------------------------------------------------


class TestRemoteBranchExists:
    """Tests for WorktreeManager._remote_branch_exists."""

    @pytest.mark.asyncio
    async def test_returns_true_when_ls_remote_has_output(
        self, config, tmp_path: Path
    ) -> None:
        manager = WorktreeManager(config)
        proc = _make_proc(returncode=0, stdout=b"abc123\trefs/heads/agent/issue-7")

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await manager._remote_branch_exists("agent/issue-7")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_ls_remote_empty(
        self, config, tmp_path: Path
    ) -> None:
        manager = WorktreeManager(config)
        proc = _make_proc(returncode=0, stdout=b"")

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await manager._remote_branch_exists("agent/issue-99")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_error(self, config, tmp_path: Path) -> None:
        manager = WorktreeManager(config)
        proc = _make_proc(returncode=1, stderr=b"fatal: network error")

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await manager._remote_branch_exists("agent/issue-7")

        assert result is False


# ---------------------------------------------------------------------------
# WorktreeManager._setup_env
# ---------------------------------------------------------------------------


class TestSetupEnv:
    """Tests for WorktreeManager._setup_env."""

    def test_setup_env_symlinks_venv(self, config, tmp_path: Path) -> None:
        """_setup_env should create a symlink for venv/ if source exists."""
        manager = WorktreeManager(config)

        repo_root = config.repo_root
        wt_path = tmp_path / "worktree"
        wt_path.mkdir()

        # Create fake repo structure
        repo_root.mkdir(parents=True, exist_ok=True)
        venv_src = repo_root / "venv"
        venv_src.mkdir()

        manager._setup_env(wt_path)

        venv_dst = wt_path / "venv"
        assert venv_dst.is_symlink()
        assert venv_dst.resolve() == venv_src.resolve()

    def test_setup_env_symlinks_dotenv(self, config, tmp_path: Path) -> None:
        """_setup_env should create a symlink for .env if source exists."""
        manager = WorktreeManager(config)

        repo_root = config.repo_root
        wt_path = tmp_path / "worktree"
        wt_path.mkdir()

        repo_root.mkdir(parents=True, exist_ok=True)
        env_src = repo_root / ".env"
        env_src.write_text("SLACK_BOT_TOKEN=test")

        manager._setup_env(wt_path)

        env_dst = wt_path / ".env"
        assert env_dst.is_symlink()

    def test_setup_env_copies_settings_local_json(self, config, tmp_path: Path) -> None:
        """_setup_env should copy (not symlink) .claude/settings.local.json."""
        manager = WorktreeManager(config)

        repo_root = config.repo_root
        wt_path = tmp_path / "worktree"
        wt_path.mkdir()

        repo_root.mkdir(parents=True, exist_ok=True)
        claude_dir = repo_root / ".claude"
        claude_dir.mkdir()
        settings_src = claude_dir / "settings.local.json"
        settings_src.write_text('{"allowed": []}')

        manager._setup_env(wt_path)

        settings_dst = wt_path / ".claude" / "settings.local.json"
        assert settings_dst.exists()
        assert not settings_dst.is_symlink(), (
            "settings.local.json must be copied, not symlinked"
        )
        assert settings_dst.read_text() == '{"allowed": []}'

    def test_setup_env_symlinks_node_modules(self, config, tmp_path: Path) -> None:
        """_setup_env should symlink node_modules for each UI directory."""
        manager = WorktreeManager(config)

        repo_root = config.repo_root
        wt_path = tmp_path / "worktree"
        wt_path.mkdir()
        repo_root.mkdir(parents=True, exist_ok=True)

        # Create one node_modules under a UI dir
        ui_nm_src = repo_root / "bot" / "health_ui" / "node_modules"
        ui_nm_src.mkdir(parents=True)

        manager._setup_env(wt_path)

        ui_nm_dst = wt_path / "bot" / "health_ui" / "node_modules"
        assert ui_nm_dst.is_symlink()

    def test_setup_env_skips_missing_sources(self, config, tmp_path: Path) -> None:
        """_setup_env should not create any symlinks when source dirs are absent."""
        manager = WorktreeManager(config)

        repo_root = config.repo_root
        repo_root.mkdir(parents=True, exist_ok=True)
        wt_path = tmp_path / "worktree"
        wt_path.mkdir()

        # No venv, .env, or node_modules present
        manager._setup_env(wt_path)

        assert not (wt_path / "venv").exists()
        assert not (wt_path / ".env").exists()
        assert not (wt_path / ".claude" / "settings.local.json").exists()

    def test_setup_env_does_not_overwrite_existing_symlinks(
        self, config, tmp_path: Path
    ) -> None:
        """_setup_env should not recreate a symlink that already exists."""
        manager = WorktreeManager(config)

        repo_root = config.repo_root
        wt_path = tmp_path / "worktree"
        wt_path.mkdir()
        repo_root.mkdir(parents=True, exist_ok=True)

        venv_src = repo_root / "venv"
        venv_src.mkdir()

        venv_dst = wt_path / "venv"
        venv_dst.symlink_to(venv_src)

        # Should not raise
        manager._setup_env(wt_path)
        assert venv_dst.is_symlink()


# ---------------------------------------------------------------------------
# WorktreeManager._install_hooks
# ---------------------------------------------------------------------------


class TestInstallHooks:
    """Tests for WorktreeManager._install_hooks."""

    @pytest.mark.asyncio
    async def test_install_hooks_calls_pre_commit_install(
        self, config, tmp_path: Path
    ) -> None:
        """_install_hooks should run 'pre-commit install' in the worktree."""
        manager = WorktreeManager(config)
        success_proc = _make_proc()

        with patch(
            "asyncio.create_subprocess_exec", return_value=success_proc
        ) as mock_exec:
            await manager._install_hooks(tmp_path)

        mock_exec.assert_called_once()
        assert mock_exec.call_args.args[:2] == ("pre-commit", "install")

    @pytest.mark.asyncio
    async def test_install_hooks_swallows_errors(self, config, tmp_path: Path) -> None:
        """_install_hooks should not propagate errors if pre-commit install fails."""
        manager = WorktreeManager(config)
        fail_proc = _make_proc(returncode=1, stderr=b"pre-commit not found")

        with patch("asyncio.create_subprocess_exec", return_value=fail_proc):
            # Should not raise
            await manager._install_hooks(tmp_path)


# ---------------------------------------------------------------------------
# WorktreeManager._run
# ---------------------------------------------------------------------------


class TestRun:
    """Tests for WorktreeManager._run static method."""

    @pytest.mark.asyncio
    async def test_run_returns_stdout_on_success(self, tmp_path: Path) -> None:
        """_run should return the decoded stdout string on zero exit code."""
        success_proc = _make_proc(returncode=0, stdout=b"hello world")

        with patch("asyncio.create_subprocess_exec", return_value=success_proc):
            result = await WorktreeManager._run("echo", "hello world", cwd=tmp_path)

        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_run_raises_runtime_error_on_non_zero_exit(
        self, tmp_path: Path
    ) -> None:
        """_run should raise RuntimeError when the subprocess exits non-zero."""
        fail_proc = _make_proc(returncode=1, stderr=b"fatal error")

        with (
            patch("asyncio.create_subprocess_exec", return_value=fail_proc),
            pytest.raises(RuntimeError, match="fatal error"),
        ):
            await WorktreeManager._run("false", cwd=tmp_path)

    @pytest.mark.asyncio
    async def test_run_error_message_includes_command_and_returncode(
        self, tmp_path: Path
    ) -> None:
        """RuntimeError message should include the command tuple and return code."""
        fail_proc = _make_proc(returncode=2, stderr=b"bad argument")

        with (
            patch("asyncio.create_subprocess_exec", return_value=fail_proc),
            pytest.raises(RuntimeError) as exc_info,
        ):
            await WorktreeManager._run("git", "push", cwd=tmp_path)

        msg = str(exc_info.value)
        assert "rc=2" in msg

    @pytest.mark.asyncio
    async def test_run_strips_whitespace_from_stdout(self, tmp_path: Path) -> None:
        """_run should strip leading/trailing whitespace from the returned stdout."""
        success_proc = _make_proc(returncode=0, stdout=b"  trimmed output  \n")

        with patch("asyncio.create_subprocess_exec", return_value=success_proc):
            result = await WorktreeManager._run("cmd", cwd=tmp_path)

        assert result == "trimmed output"
