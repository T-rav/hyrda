"""Git worktree lifecycle management for Hydra."""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path

from config import HydraConfig
from subprocess_util import run_subprocess

logger = logging.getLogger("hydra.worktree")


class WorktreeManager:
    """Creates, configures, and destroys isolated git worktrees.

    Each worktree gets:
    - A fresh branch from ``main``
    - An independent venv via ``uv sync``
    - Symlinked ``.env`` and ``node_modules/`` dirs
    - Copied ``.claude/settings.local.json``
    - Pre-commit hooks installed
    """

    # Node UI directories that need symlinked node_modules
    _UI_DIRS = [
        "bot/health_ui",
        "tasks/ui",
        "control_plane/ui",
        "dashboard-service/health_ui",
    ]

    def __init__(self, config: HydraConfig) -> None:
        self._config = config
        self._repo_root = config.repo_root
        self._base = config.worktree_base

    def exists(self, issue_number: int) -> bool:
        """Check whether a worktree directory already exists for *issue_number*."""
        wt_path = self._base / f"issue-{issue_number}"
        return wt_path.is_dir()

    async def _delete_local_branch(self, branch: str) -> None:
        """Delete a local branch if it exists, ignoring errors."""
        with contextlib.suppress(RuntimeError):
            await run_subprocess(
                "git",
                "branch",
                "-D",
                branch,
                cwd=self._repo_root,
                gh_token=self._config.gh_token,
            )

    async def _remote_branch_exists(self, branch: str) -> bool:
        """Check whether *branch* exists on the remote."""
        try:
            output = await run_subprocess(
                "git",
                "ls-remote",
                "--heads",
                "origin",
                branch,
                cwd=self._repo_root,
                gh_token=self._config.gh_token,
            )
            return bool(output.strip())
        except RuntimeError:
            return False

    async def create(self, issue_number: int, branch: str) -> Path:
        """Create a worktree for *issue_number* on *branch*.

        If the branch already exists on the remote (previous run), fetches
        and checks it out so work can resume.  Otherwise creates a fresh
        branch from main.

        Returns the absolute path to the new worktree.
        """
        wt_path = self._base / f"issue-{issue_number}"
        logger.info(
            "Creating worktree %s on branch %s",
            wt_path,
            branch,
            extra={"issue": issue_number},
        )

        if self._config.dry_run:
            logger.info("[dry-run] Would create worktree at %s", wt_path)
            return wt_path

        # Ensure base directory exists
        self._base.mkdir(parents=True, exist_ok=True)

        # Clean up any stale local branch (from previous runs) to avoid
        # fetch conflicts and worktree checkout errors
        await self._delete_local_branch(branch)

        # Fetch latest main so we branch from the latest state
        await run_subprocess(
            "git",
            "fetch",
            "origin",
            self._config.main_branch,
            cwd=self._repo_root,
            gh_token=self._config.gh_token,
        )

        # Check if the branch already exists on the remote (resumable work)
        if await self._remote_branch_exists(branch):
            logger.info(
                "Remote branch %s exists — resuming from remote",
                branch,
                extra={"issue": issue_number},
            )
            await run_subprocess(
                "git",
                "fetch",
                "origin",
                f"+refs/heads/{branch}:refs/heads/{branch}",
                cwd=self._repo_root,
                gh_token=self._config.gh_token,
            )
        else:
            # Create a fresh branch from main
            await run_subprocess(
                "git",
                "branch",
                "-f",
                branch,
                f"origin/{self._config.main_branch}",
                cwd=self._repo_root,
                gh_token=self._config.gh_token,
            )

        # Create the worktree
        await run_subprocess(
            "git",
            "worktree",
            "add",
            str(wt_path),
            branch,
            cwd=self._repo_root,
            gh_token=self._config.gh_token,
        )

        # Set up the environment inside the worktree
        self._setup_env(wt_path)
        await self._configure_git_identity(wt_path)
        await self._create_venv(wt_path)
        await self._install_hooks(wt_path)

        logger.info(
            "Worktree ready at %s",
            wt_path,
            extra={"issue": issue_number},
        )
        return wt_path

    async def destroy(self, issue_number: int) -> None:
        """Remove the worktree for *issue_number*."""
        wt_path = self._base / f"issue-{issue_number}"
        if self._config.dry_run:
            logger.info("[dry-run] Would destroy worktree %s", wt_path)
            return

        if wt_path.exists():
            await run_subprocess(
                "git",
                "worktree",
                "remove",
                str(wt_path),
                "--force",
                cwd=self._repo_root,
                gh_token=self._config.gh_token,
            )
            logger.info(
                "Destroyed worktree %s",
                wt_path,
                extra={"issue": issue_number},
            )

        # Also clean up the branch
        branch = f"agent/issue-{issue_number}"
        with contextlib.suppress(RuntimeError):
            await run_subprocess(
                "git",
                "branch",
                "-D",
                branch,
                cwd=self._repo_root,
                gh_token=self._config.gh_token,
            )

    async def destroy_all(self) -> None:
        """Remove every worktree under the base directory."""
        if not self._base.exists():
            return
        for child in self._base.iterdir():
            if child.is_dir() and child.name.startswith("issue-"):
                try:
                    num = int(child.name.split("-", 1)[1])
                    await self.destroy(num)
                except (ValueError, RuntimeError) as exc:
                    logger.warning("Could not destroy %s: %s", child, exc)

        # Final prune
        with contextlib.suppress(RuntimeError):
            await run_subprocess(
                "git",
                "worktree",
                "prune",
                cwd=self._repo_root,
                gh_token=self._config.gh_token,
            )

    async def merge_main(self, worktree_path: Path) -> bool:
        """Merge latest main into the current branch inside *worktree_path*.

        Uses merge (not rebase) so the push remains fast-forward and
        doesn't require ``--force``.

        Returns *True* on success, *False* if conflicts arise.
        """
        try:
            await run_subprocess(
                "git",
                "fetch",
                "origin",
                self._config.main_branch,
                cwd=worktree_path,
                gh_token=self._config.gh_token,
            )
            await run_subprocess(
                "git",
                "merge",
                f"origin/{self._config.main_branch}",
                "--no-edit",
                cwd=worktree_path,
                gh_token=self._config.gh_token,
            )
            return True
        except RuntimeError:
            # Abort merge on conflict
            with contextlib.suppress(RuntimeError):
                await run_subprocess(
                    "git",
                    "merge",
                    "--abort",
                    cwd=worktree_path,
                    gh_token=self._config.gh_token,
                )
            return False

    # --- environment setup ---

    def _setup_env(self, wt_path: Path) -> None:
        """Symlink .env and node_modules into the worktree."""
        # Symlink .env
        env_src = self._repo_root / ".env"
        env_dst = wt_path / ".env"
        if env_src.exists() and not env_dst.exists():
            env_dst.symlink_to(env_src)

        # Copy .claude/settings.local.json (not symlink - agents may modify)
        local_settings_src = self._repo_root / ".claude" / "settings.local.json"
        local_settings_dst = wt_path / ".claude" / "settings.local.json"
        if local_settings_src.exists() and not local_settings_dst.exists():
            local_settings_dst.parent.mkdir(parents=True, exist_ok=True)
            local_settings_dst.write_text(local_settings_src.read_text())

        # Symlink node_modules for each UI directory
        for ui_dir in self._UI_DIRS:
            nm_src = self._repo_root / ui_dir / "node_modules"
            nm_dst = wt_path / ui_dir / "node_modules"
            if nm_src.exists() and not nm_dst.exists():
                nm_dst.parent.mkdir(parents=True, exist_ok=True)
                nm_dst.symlink_to(nm_src)

    async def _configure_git_identity(self, wt_path: Path) -> None:
        """Set git user.name and user.email in the worktree (local scope)."""
        if self._config.git_user_name:
            await run_subprocess(
                "git",
                "config",
                "user.name",
                self._config.git_user_name,
                cwd=wt_path,
                gh_token=self._config.gh_token,
            )
        if self._config.git_user_email:
            await run_subprocess(
                "git",
                "config",
                "user.email",
                self._config.git_user_email,
                cwd=wt_path,
                gh_token=self._config.gh_token,
            )

    async def _create_venv(self, wt_path: Path) -> None:
        """Create an independent venv in the worktree via ``uv sync``."""
        try:
            await run_subprocess(
                "uv", "sync", cwd=wt_path, gh_token=self._config.gh_token
            )
        except RuntimeError as exc:
            logger.warning("uv sync failed in %s: %s", wt_path, exc)

    async def _install_hooks(self, wt_path: Path) -> None:
        """Point the worktree at the shared .githooks directory."""
        try:
            await run_subprocess(
                "git",
                "config",
                "core.hooksPath",
                ".githooks",
                cwd=wt_path,
                gh_token=self._config.gh_token,
            )
        except RuntimeError as exc:
            logger.warning("git hooks setup failed: %s", exc)
