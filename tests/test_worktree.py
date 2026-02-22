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
        """create should clean up stale branch, fetch main, then 'git branch -f' and 'git worktree add'."""
        manager = WorktreeManager(config)

        # Pre-create the base directory so mkdir doesn't cause issues
        config.worktree_base.mkdir(parents=True, exist_ok=True)

        success_proc = _make_proc(returncode=0)

        with (
            patch(
                "asyncio.create_subprocess_exec", return_value=success_proc
            ) as mock_exec,
            patch.object(manager, "_delete_local_branch", new_callable=AsyncMock),
            patch.object(manager, "_remote_branch_exists", return_value=False),
            patch.object(manager, "_setup_env"),
            patch.object(manager, "_create_venv", new_callable=AsyncMock),
            patch.object(manager, "_install_hooks", new_callable=AsyncMock),
        ):
            # _setup_env, _create_venv, and _install_hooks must not fail; patch them out
            await manager.create(issue_number=7, branch="agent/issue-7")

        calls = mock_exec.call_args_list
        # First call: git fetch origin main
        assert calls[0].args[:3] == ("git", "fetch", "origin")
        # Second call: git branch -f
        assert calls[1].args[:4] == ("git", "branch", "-f", "agent/issue-7")
        # Third call: git worktree add
        assert calls[2].args[:3] == ("git", "worktree", "add")

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
            patch.object(manager, "_delete_local_branch", new_callable=AsyncMock),
            patch.object(
                manager, "_remote_branch_exists", return_value=True
            ) as mock_remote,
            patch.object(manager, "_setup_env"),
            patch.object(manager, "_create_venv", new_callable=AsyncMock),
            patch.object(manager, "_install_hooks", new_callable=AsyncMock),
        ):
            await manager.create(issue_number=7, branch="agent/issue-7")

        mock_remote.assert_awaited_once_with("agent/issue-7")
        calls = mock_exec.call_args_list
        # First call: git fetch origin main
        assert calls[0].args[:3] == ("git", "fetch", "origin")
        # Second call: git fetch with force refspec for the branch
        assert calls[1].args[:3] == ("git", "fetch", "origin")
        assert "+refs/heads/agent/issue-7:refs/heads/agent/issue-7" in calls[1].args
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
            patch.object(manager, "_delete_local_branch", new_callable=AsyncMock),
            patch.object(manager, "_remote_branch_exists", return_value=False),
            patch.object(manager, "_setup_env"),
            patch.object(manager, "_create_venv", new_callable=AsyncMock),
            patch.object(manager, "_install_hooks", new_callable=AsyncMock),
        ):
            await manager.create(issue_number=7, branch="agent/issue-7")

        calls = mock_exec.call_args_list
        # First call: git fetch origin main; second call: git branch -f
        assert calls[1].args[:4] == ("git", "branch", "-f", "agent/issue-7")

    @pytest.mark.asyncio
    async def test_create_calls_setup_env_create_venv_and_install_hooks(
        self, config, tmp_path: Path
    ) -> None:
        """create should invoke _setup_env, _create_venv, and _install_hooks."""
        manager = WorktreeManager(config)
        config.worktree_base.mkdir(parents=True, exist_ok=True)

        success_proc = _make_proc()

        setup_env = MagicMock()
        create_venv = AsyncMock()
        install_hooks = AsyncMock()

        with (
            patch("asyncio.create_subprocess_exec", return_value=success_proc),
            patch.object(manager, "_delete_local_branch", new_callable=AsyncMock),
            patch.object(manager, "_remote_branch_exists", return_value=False),
            patch.object(manager, "_setup_env", setup_env),
            patch.object(manager, "_create_venv", create_venv),
            patch.object(manager, "_install_hooks", install_hooks),
        ):
            result = await manager.create(issue_number=7, branch="agent/issue-7")

        setup_env.assert_called_once()
        create_venv.assert_awaited_once()
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
            patch.object(manager, "_delete_local_branch", new_callable=AsyncMock),
            patch.object(manager, "_remote_branch_exists", return_value=False),
            patch.object(manager, "_setup_env"),
            patch.object(manager, "_create_venv", new_callable=AsyncMock),
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

    @pytest.mark.asyncio
    async def test_create_raises_when_fetch_origin_main_fails(
        self, config, tmp_path: Path
    ) -> None:
        """create should propagate RuntimeError when 'git fetch origin main' fails."""
        manager = WorktreeManager(config)
        config.worktree_base.mkdir(parents=True, exist_ok=True)

        fail_proc = _make_proc(returncode=1, stderr=b"fatal: network error")

        with (
            patch("asyncio.create_subprocess_exec", return_value=fail_proc),
            patch.object(manager, "_delete_local_branch", new_callable=AsyncMock),
            pytest.raises(RuntimeError, match="network error"),
        ):
            await manager.create(issue_number=7, branch="agent/issue-7")

    @pytest.mark.asyncio
    async def test_create_raises_when_worktree_add_fails_after_branch_created(
        self, config, tmp_path: Path
    ) -> None:
        """create should propagate RuntimeError when 'git worktree add' fails after branch creation."""
        manager = WorktreeManager(config)
        config.worktree_base.mkdir(parents=True, exist_ok=True)

        success_proc = _make_proc(returncode=0)
        fail_proc = _make_proc(returncode=1, stderr=b"fatal: worktree add failed")

        call_count = 0

        async def fake_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Calls 1-2: fetch + branch -f succeed; call 3: worktree add fails
            if call_count <= 2:
                return success_proc
            return fail_proc

        with (
            patch("asyncio.create_subprocess_exec", side_effect=fake_exec),
            patch.object(manager, "_delete_local_branch", new_callable=AsyncMock),
            patch.object(manager, "_remote_branch_exists", return_value=False),
            pytest.raises(RuntimeError, match="worktree add failed"),
        ):
            await manager.create(issue_number=7, branch="agent/issue-7")

    @pytest.mark.asyncio
    async def test_create_propagates_setup_env_error(
        self, config, tmp_path: Path
    ) -> None:
        """create should propagate OSError from _setup_env (not wrapped in try/except)."""
        manager = WorktreeManager(config)
        config.worktree_base.mkdir(parents=True, exist_ok=True)

        success_proc = _make_proc(returncode=0)

        with (
            patch("asyncio.create_subprocess_exec", return_value=success_proc),
            patch.object(manager, "_delete_local_branch", new_callable=AsyncMock),
            patch.object(manager, "_remote_branch_exists", return_value=False),
            patch.object(
                manager, "_setup_env", side_effect=OSError("Permission denied")
            ),
            pytest.raises(OSError, match="Permission denied"),
        ):
            await manager.create(issue_number=7, branch="agent/issue-7")

    @pytest.mark.asyncio
    async def test_create_venv_failure_does_not_block_create(
        self, config, tmp_path: Path
    ) -> None:
        """create should return a valid path even when uv sync fails inside _create_venv."""
        manager = WorktreeManager(config)
        config.worktree_base.mkdir(parents=True, exist_ok=True)

        success_proc = _make_proc(returncode=0)
        fail_proc = _make_proc(returncode=1, stderr=b"uv sync failed")

        call_count = 0

        async def fake_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # uv sync is the 4th subprocess call (fetch, branch, worktree add, uv sync)
            if args[0:2] == ("uv", "sync"):
                return fail_proc
            return success_proc

        with (
            patch("asyncio.create_subprocess_exec", side_effect=fake_exec),
            patch.object(manager, "_delete_local_branch", new_callable=AsyncMock),
            patch.object(manager, "_remote_branch_exists", return_value=False),
            patch.object(manager, "_setup_env"),
        ):
            result = await manager.create(issue_number=7, branch="agent/issue-7")

        # _create_venv catches RuntimeError internally, so create completes
        assert result == config.worktree_base / "issue-7"


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
    async def test_destroy_raises_when_worktree_remove_force_fails(
        self, config, tmp_path: Path
    ) -> None:
        """destroy should propagate RuntimeError when 'git worktree remove --force' fails."""
        manager = WorktreeManager(config)

        wt_path = config.worktree_base / "issue-7"
        wt_path.mkdir(parents=True, exist_ok=True)

        fail_proc = _make_proc(returncode=1, stderr=b"fatal: dirty worktree")

        with (
            patch("asyncio.create_subprocess_exec", return_value=fail_proc),
            pytest.raises(RuntimeError, match="dirty worktree"),
        ):
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
            patch("worktree.run_subprocess", new_callable=AsyncMock),
        ):
            # Also patch run_subprocess for the final prune
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
            patch("worktree.run_subprocess", new_callable=AsyncMock),
        ):
            await manager.destroy_all()

        assert destroyed == [5]


# ---------------------------------------------------------------------------
# WorktreeManager.rebase
# ---------------------------------------------------------------------------


class TestMergeMain:
    """Tests for WorktreeManager.rebase."""

    @pytest.mark.asyncio
    async def test_merge_main_success_returns_true(
        self, config, tmp_path: Path
    ) -> None:
        """merge_main should return True when fetch, ff-pull, and merge succeed."""
        manager = WorktreeManager(config)
        success_proc = _make_proc()

        with patch("asyncio.create_subprocess_exec", return_value=success_proc):
            result = await manager.merge_main(tmp_path, "agent/issue-7")

        assert result is True

    @pytest.mark.asyncio
    async def test_merge_main_conflict_aborts_and_returns_false(
        self, config, tmp_path: Path
    ) -> None:
        """merge_main should abort and return False when conflicts occur."""
        manager = WorktreeManager(config)

        success_proc = _make_proc(returncode=0)
        merge_fail_proc = _make_proc(
            returncode=1, stderr=b"CONFLICT (content): Merge conflict"
        )
        abort_proc = _make_proc(returncode=0)

        call_count = 0

        async def fake_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return success_proc  # git fetch + ff-only merge succeed
            if call_count == 3:
                return merge_fail_proc  # git merge origin/main fails
            return abort_proc  # git merge --abort

        with patch(
            "asyncio.create_subprocess_exec", side_effect=fake_exec
        ) as mock_exec:
            result = await manager.merge_main(tmp_path, "agent/issue-7")

        assert result is False
        # Verify abort was called
        abort_calls = [c for c in mock_exec.call_args_list if "--abort" in c.args]
        assert len(abort_calls) == 1

    @pytest.mark.asyncio
    async def test_merge_main_fetch_failure_returns_false(
        self, config, tmp_path: Path
    ) -> None:
        """merge_main should return False if the initial fetch fails."""
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
            result = await manager.merge_main(tmp_path, "agent/issue-7")

        assert result is False


# ---------------------------------------------------------------------------
# WorktreeManager._delete_local_branch
# ---------------------------------------------------------------------------


class TestDeleteLocalBranch:
    """Tests for WorktreeManager._delete_local_branch."""

    @pytest.mark.asyncio
    async def test_deletes_existing_branch(self, config, tmp_path: Path) -> None:
        """Should call git branch -D for the given branch."""
        manager = WorktreeManager(config)
        success_proc = _make_proc(returncode=0)

        with patch(
            "asyncio.create_subprocess_exec", return_value=success_proc
        ) as mock_exec:
            await manager._delete_local_branch("agent/issue-7")

        mock_exec.assert_called_once()
        assert mock_exec.call_args.args[:4] == ("git", "branch", "-D", "agent/issue-7")

    @pytest.mark.asyncio
    async def test_swallows_error_when_branch_missing(
        self, config, tmp_path: Path
    ) -> None:
        """Should not raise when the branch does not exist."""
        manager = WorktreeManager(config)
        fail_proc = _make_proc(returncode=1, stderr=b"error: branch not found")

        with patch("asyncio.create_subprocess_exec", return_value=fail_proc):
            # Should not raise
            await manager._delete_local_branch("agent/issue-999")


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

    def test_setup_env_does_not_symlink_venv(self, config, tmp_path: Path) -> None:
        """_setup_env should NOT create a symlink for venv/ (independent venvs via uv sync)."""
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
        assert not venv_dst.exists()

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

        env_src = repo_root / ".env"
        env_src.write_text("EXISTING=true")

        env_dst = wt_path / ".env"
        env_dst.symlink_to(env_src)

        # Should not raise
        manager._setup_env(wt_path)
        assert env_dst.is_symlink()

    def test_setup_env_handles_symlink_oserror(self, config, tmp_path: Path) -> None:
        """_setup_env should handle OSError on symlink and continue."""
        manager = WorktreeManager(config)
        repo_root = config.repo_root
        wt_path = tmp_path / "worktree"
        wt_path.mkdir()
        repo_root.mkdir(parents=True, exist_ok=True)

        # Create .env source so the symlink path is entered
        env_src = repo_root / ".env"
        env_src.write_text("SECRET=val")

        # Also create node_modules source under a real _UI_DIRS entry
        ui_nm_src = repo_root / "bot" / "health_ui" / "node_modules"
        ui_nm_src.mkdir(parents=True)

        with patch.object(Path, "symlink_to", side_effect=OSError("perm denied")):
            manager._setup_env(wt_path)  # should not raise

    def test_setup_env_handles_copy_oserror(self, config, tmp_path: Path) -> None:
        """_setup_env should handle OSError when copying settings and continue."""
        manager = WorktreeManager(config)
        repo_root = config.repo_root
        wt_path = tmp_path / "worktree"
        wt_path.mkdir()
        repo_root.mkdir(parents=True, exist_ok=True)

        # Create settings source
        claude_dir = repo_root / ".claude"
        claude_dir.mkdir()
        settings_src = claude_dir / "settings.local.json"
        settings_src.write_text('{"allowed": []}')

        with patch.object(Path, "write_text", side_effect=OSError("read-only")):
            manager._setup_env(wt_path)  # should not raise


# ---------------------------------------------------------------------------
# WorktreeManager._configure_git_identity
# ---------------------------------------------------------------------------


class TestConfigureGitIdentity:
    """Tests for WorktreeManager._configure_git_identity."""

    @pytest.mark.asyncio
    async def test_sets_user_name_and_email(self, tmp_path: Path) -> None:
        """Should run git config for both user.name and user.email."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            git_user_name="Bot",
            git_user_email="bot@example.com",
            repo_root=tmp_path,
            worktree_base=tmp_path / "worktrees",
            state_file=tmp_path / "state.json",
        )
        manager = WorktreeManager(cfg)
        success_proc = _make_proc(returncode=0)

        with patch(
            "asyncio.create_subprocess_exec", return_value=success_proc
        ) as mock_exec:
            await manager._configure_git_identity(tmp_path)

        calls = mock_exec.call_args_list
        assert len(calls) == 2
        assert calls[0].args == ("git", "config", "user.name", "Bot")
        assert calls[1].args == ("git", "config", "user.email", "bot@example.com")

    @pytest.mark.asyncio
    async def test_skips_when_both_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should not run any git config commands when identity is empty."""
        monkeypatch.delenv("HYDRA_GIT_USER_NAME", raising=False)
        monkeypatch.delenv("HYDRA_GIT_USER_EMAIL", raising=False)

        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            repo_root=tmp_path,
            worktree_base=tmp_path / "worktrees",
            state_file=tmp_path / "state.json",
        )
        manager = WorktreeManager(cfg)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            await manager._configure_git_identity(tmp_path)

        mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_sets_only_name_when_email_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should only set user.name when email is empty."""
        monkeypatch.delenv("HYDRA_GIT_USER_NAME", raising=False)
        monkeypatch.delenv("HYDRA_GIT_USER_EMAIL", raising=False)

        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            git_user_name="Bot",
            git_user_email="",
            repo_root=tmp_path,
            worktree_base=tmp_path / "worktrees",
            state_file=tmp_path / "state.json",
        )
        manager = WorktreeManager(cfg)
        success_proc = _make_proc(returncode=0)

        with patch(
            "asyncio.create_subprocess_exec", return_value=success_proc
        ) as mock_exec:
            await manager._configure_git_identity(tmp_path)

        calls = mock_exec.call_args_list
        assert len(calls) == 1
        assert calls[0].args == ("git", "config", "user.name", "Bot")

    @pytest.mark.asyncio
    async def test_sets_only_email_when_name_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should only set user.email when name is empty."""
        monkeypatch.delenv("HYDRA_GIT_USER_NAME", raising=False)
        monkeypatch.delenv("HYDRA_GIT_USER_EMAIL", raising=False)

        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            git_user_name="",
            git_user_email="bot@example.com",
            repo_root=tmp_path,
            worktree_base=tmp_path / "worktrees",
            state_file=tmp_path / "state.json",
        )
        manager = WorktreeManager(cfg)
        success_proc = _make_proc(returncode=0)

        with patch(
            "asyncio.create_subprocess_exec", return_value=success_proc
        ) as mock_exec:
            await manager._configure_git_identity(tmp_path)

        calls = mock_exec.call_args_list
        assert len(calls) == 1
        assert calls[0].args == ("git", "config", "user.email", "bot@example.com")

    @pytest.mark.asyncio
    async def test_called_during_create(self, tmp_path: Path) -> None:
        """_configure_git_identity should be called during create()."""
        from tests.helpers import ConfigFactory

        cfg = ConfigFactory.create(
            git_user_name="Bot",
            git_user_email="bot@example.com",
            repo_root=tmp_path,
            worktree_base=tmp_path / "worktrees",
            state_file=tmp_path / "state.json",
        )
        manager = WorktreeManager(cfg)
        cfg.worktree_base.mkdir(parents=True, exist_ok=True)

        success_proc = _make_proc()
        configure_identity = AsyncMock()

        with (
            patch("asyncio.create_subprocess_exec", return_value=success_proc),
            patch.object(manager, "_delete_local_branch", new_callable=AsyncMock),
            patch.object(manager, "_remote_branch_exists", return_value=False),
            patch.object(manager, "_setup_env"),
            patch.object(manager, "_configure_git_identity", configure_identity),
            patch.object(manager, "_create_venv", new_callable=AsyncMock),
            patch.object(manager, "_install_hooks", new_callable=AsyncMock),
        ):
            await manager.create(issue_number=7, branch="agent/issue-7")

        configure_identity.assert_awaited_once()


# ---------------------------------------------------------------------------
# WorktreeManager._create_venv
# ---------------------------------------------------------------------------


class TestCreateVenv:
    """Tests for WorktreeManager._create_venv."""

    @pytest.mark.asyncio
    async def test_create_venv_runs_uv_sync(self, config, tmp_path: Path) -> None:
        """_create_venv should run 'uv sync' in the worktree."""
        manager = WorktreeManager(config)
        success_proc = _make_proc()

        with patch(
            "asyncio.create_subprocess_exec", return_value=success_proc
        ) as mock_exec:
            await manager._create_venv(tmp_path)

        mock_exec.assert_called_once()
        assert mock_exec.call_args.args[:2] == ("uv", "sync")

    @pytest.mark.asyncio
    async def test_create_venv_swallows_errors(self, config, tmp_path: Path) -> None:
        """_create_venv should not propagate errors if uv sync fails."""
        manager = WorktreeManager(config)
        fail_proc = _make_proc(returncode=1, stderr=b"uv not found")

        with patch("asyncio.create_subprocess_exec", return_value=fail_proc):
            # Should not raise
            await manager._create_venv(tmp_path)

    @pytest.mark.asyncio
    async def test_create_venv_swallows_file_not_found_error(
        self, config, tmp_path: Path
    ) -> None:
        """_create_venv should handle missing uv binary (FileNotFoundError)."""
        manager = WorktreeManager(config)

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("uv"),
        ):
            await manager._create_venv(tmp_path)  # should not raise


# ---------------------------------------------------------------------------
# WorktreeManager._install_hooks
# ---------------------------------------------------------------------------


class TestInstallHooks:
    """Tests for WorktreeManager._install_hooks."""

    @pytest.mark.asyncio
    async def test_install_hooks_sets_hooks_path(self, config, tmp_path: Path) -> None:
        """_install_hooks should set core.hooksPath to .githooks."""
        manager = WorktreeManager(config)
        success_proc = _make_proc()

        with patch(
            "asyncio.create_subprocess_exec", return_value=success_proc
        ) as mock_exec:
            await manager._install_hooks(tmp_path)

        mock_exec.assert_called_once()
        assert mock_exec.call_args.args[:4] == (
            "git",
            "config",
            "core.hooksPath",
            ".githooks",
        )

    @pytest.mark.asyncio
    async def test_install_hooks_swallows_errors(self, config, tmp_path: Path) -> None:
        """_install_hooks should not propagate errors if git config fails."""
        manager = WorktreeManager(config)
        fail_proc = _make_proc(returncode=1, stderr=b"error")

        with patch("asyncio.create_subprocess_exec", return_value=fail_proc):
            # Should not raise
            await manager._install_hooks(tmp_path)


# ---------------------------------------------------------------------------
# WorktreeManager.start_merge_main
# ---------------------------------------------------------------------------


class TestStartMergeMain:
    """Tests for WorktreeManager.start_merge_main."""

    @pytest.mark.asyncio
    async def test_start_merge_main_clean_merge_returns_true(
        self, config, tmp_path: Path
    ) -> None:
        """start_merge_main should return True when all commands succeed."""
        manager = WorktreeManager(config)
        success_proc = _make_proc()

        with patch("asyncio.create_subprocess_exec", return_value=success_proc):
            result = await manager.start_merge_main(tmp_path, "agent/issue-7")

        assert result is True

    @pytest.mark.asyncio
    async def test_start_merge_main_conflict_returns_false_without_abort(
        self, config, tmp_path: Path
    ) -> None:
        """start_merge_main should return False on conflict and NOT call --abort."""
        manager = WorktreeManager(config)

        success_proc = _make_proc(returncode=0)
        merge_fail_proc = _make_proc(
            returncode=1, stderr=b"CONFLICT (content): Merge conflict"
        )

        call_count = 0

        async def fake_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return success_proc  # git fetch + ff-only merge succeed
            return merge_fail_proc  # git merge origin/main fails

        with patch(
            "asyncio.create_subprocess_exec", side_effect=fake_exec
        ) as mock_exec:
            result = await manager.start_merge_main(tmp_path, "agent/issue-7")

        assert result is False
        # Critical: start_merge_main must NOT call git merge --abort
        for call in mock_exec.call_args_list:
            assert "--abort" not in call.args, (
                "start_merge_main must NOT abort on conflict — "
                "caller resolves conflicts"
            )

    @pytest.mark.asyncio
    async def test_start_merge_main_fetch_failure_returns_false(
        self, config, tmp_path: Path
    ) -> None:
        """start_merge_main should return False if fetch fails."""
        manager = WorktreeManager(config)

        fetch_fail_proc = _make_proc(returncode=1, stderr=b"fatal: network error")

        with patch("asyncio.create_subprocess_exec", return_value=fetch_fail_proc):
            result = await manager.start_merge_main(tmp_path, "agent/issue-7")

        assert result is False


# ---------------------------------------------------------------------------
# WorktreeManager.abort_merge
# ---------------------------------------------------------------------------


class TestAbortMerge:
    """Tests for WorktreeManager.abort_merge."""

    @pytest.mark.asyncio
    async def test_abort_merge_calls_git_merge_abort(
        self, config, tmp_path: Path
    ) -> None:
        """abort_merge should call 'git merge --abort' with correct cwd."""
        manager = WorktreeManager(config)
        success_proc = _make_proc(returncode=0)

        with patch(
            "asyncio.create_subprocess_exec", return_value=success_proc
        ) as mock_exec:
            await manager.abort_merge(tmp_path)

        mock_exec.assert_called_once()
        args = mock_exec.call_args.args
        assert args[:3] == ("git", "merge", "--abort")

    @pytest.mark.asyncio
    async def test_abort_merge_swallows_runtime_error(
        self, config, tmp_path: Path
    ) -> None:
        """abort_merge should suppress RuntimeError via contextlib.suppress."""
        manager = WorktreeManager(config)
        fail_proc = _make_proc(returncode=1, stderr=b"fatal: no merge in progress")

        with patch("asyncio.create_subprocess_exec", return_value=fail_proc):
            # Should not raise
            await manager.abort_merge(tmp_path)


# ---------------------------------------------------------------------------
# WorktreeManager.get_main_commits_since_diverge
# ---------------------------------------------------------------------------


class TestGetMainCommitsSinceDiverge:
    """Tests for WorktreeManager.get_main_commits_since_diverge."""

    @pytest.mark.asyncio
    async def test_returns_commit_log(self, config, tmp_path: Path) -> None:
        """Should return oneline commits from HEAD..origin/main."""
        manager = WorktreeManager(config)

        fetch_proc = _make_proc(returncode=0)
        log_output = b"abc1234 Add feature X\ndef5678 Fix bug Y\n"
        log_proc = _make_proc(returncode=0, stdout=log_output)

        call_count = 0

        async def fake_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return fetch_proc
            return log_proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            result = await manager.get_main_commits_since_diverge(tmp_path)

        assert "abc1234 Add feature X" in result
        assert "def5678 Fix bug Y" in result

    @pytest.mark.asyncio
    async def test_returns_empty_on_fetch_failure(self, config, tmp_path: Path) -> None:
        """Should return empty string when git fetch fails."""
        manager = WorktreeManager(config)
        fail_proc = _make_proc(returncode=1, stderr=b"fatal: network error")

        with patch("asyncio.create_subprocess_exec", return_value=fail_proc):
            result = await manager.get_main_commits_since_diverge(tmp_path)

        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_empty_on_log_failure(self, config, tmp_path: Path) -> None:
        """Should return empty string when git log fails."""
        manager = WorktreeManager(config)

        fetch_proc = _make_proc(returncode=0)
        log_fail_proc = _make_proc(returncode=1, stderr=b"fatal: bad revision")

        call_count = 0

        async def fake_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return fetch_proc
            return log_fail_proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            result = await manager.get_main_commits_since_diverge(tmp_path)

        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_diverged_commits(
        self, config, tmp_path: Path
    ) -> None:
        """Should return empty string when branch is up to date with main."""
        manager = WorktreeManager(config)

        fetch_proc = _make_proc(returncode=0)
        log_proc = _make_proc(returncode=0, stdout=b"")

        call_count = 0

        async def fake_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return fetch_proc
            return log_proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            result = await manager.get_main_commits_since_diverge(tmp_path)

        assert result == ""

    @pytest.mark.asyncio
    async def test_passes_limit_flag(self, config, tmp_path: Path) -> None:
        """Should pass -30 to limit the number of commits."""
        manager = WorktreeManager(config)

        success_proc = _make_proc(returncode=0, stdout=b"abc123 commit\n")

        with patch(
            "asyncio.create_subprocess_exec", return_value=success_proc
        ) as mock_exec:
            await manager.get_main_commits_since_diverge(tmp_path)

        # Second call is git log
        log_call = mock_exec.call_args_list[1]
        assert "-30" in log_call.args


# NOTE: Tests for the subprocess helper (stdout parsing, error handling,
# GH_TOKEN injection, CLAUDECODE stripping) are now in test_subprocess_util.py
# since the logic was extracted into subprocess_util.run_subprocess.
