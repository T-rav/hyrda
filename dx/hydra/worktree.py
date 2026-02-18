"""Git worktree lifecycle management for Hydra."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from pathlib import Path

from config import HydraConfig

logger = logging.getLogger("hydra.worktree")


class WorktreeManager:
    """Creates, configures, and destroys isolated git worktrees.

    Each worktree gets:
    - A fresh branch from ``main``
    - Symlinked ``venv/``, ``.env``, and ``node_modules/`` dirs
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

    async def _remote_branch_exists(self, branch: str) -> bool:
        """Check whether *branch* exists on the remote."""
        try:
            output = await self._run(
                "git", "ls-remote", "--heads", "origin", branch,
                cwd=self._repo_root,
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

        # Check if the branch already exists on the remote (resumable work)
        if await self._remote_branch_exists(branch):
            logger.info(
                "Remote branch %s exists — resuming from remote",
                branch,
                extra={"issue": issue_number},
            )
            await self._run(
                "git", "fetch", "origin", f"{branch}:{branch}",
                cwd=self._repo_root,
            )
        else:
            # Create a fresh branch from main
            await self._run(
                "git",
                "branch",
                "-f",
                branch,
                f"origin/{self._config.main_branch}",
                cwd=self._repo_root,
            )

        # Create the worktree
        await self._run(
            "git",
            "worktree",
            "add",
            str(wt_path),
            branch,
            cwd=self._repo_root,
        )

        # Set up the environment inside the worktree
        self._setup_env(wt_path)
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
            await self._run(
                "git",
                "worktree",
                "remove",
                str(wt_path),
                "--force",
                cwd=self._repo_root,
            )
            logger.info(
                "Destroyed worktree %s",
                wt_path,
                extra={"issue": issue_number},
            )

        # Also clean up the branch
        branch = f"agent/issue-{issue_number}"
        with contextlib.suppress(RuntimeError):
            await self._run(
                "git",
                "branch",
                "-D",
                branch,
                cwd=self._repo_root,
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
            await self._run("git", "worktree", "prune", cwd=self._repo_root)

    async def rebase(self, worktree_path: Path, branch: str) -> bool:
        """Rebase *branch* onto latest main inside *worktree_path*.

        Returns *True* on success, *False* if conflicts arise.
        """
        try:
            await self._run(
                "git",
                "fetch",
                "origin",
                self._config.main_branch,
                cwd=worktree_path,
            )
            await self._run(
                "git",
                "rebase",
                f"origin/{self._config.main_branch}",
                cwd=worktree_path,
            )
            return True
        except RuntimeError:
            # Abort rebase on conflict
            with contextlib.suppress(RuntimeError):
                await self._run("git", "rebase", "--abort", cwd=worktree_path)
            return False

    # --- environment setup ---

    def _setup_env(self, wt_path: Path) -> None:
        """Symlink venv, .env, and node_modules into the worktree."""
        # Symlink venv/
        venv_src = self._repo_root / "venv"
        venv_dst = wt_path / "venv"
        if venv_src.exists() and not venv_dst.exists():
            venv_dst.symlink_to(venv_src)

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

    async def _install_hooks(self, wt_path: Path) -> None:
        """Run ``pre-commit install`` in the worktree."""
        try:
            await self._run("pre-commit", "install", cwd=wt_path)
        except RuntimeError as exc:
            logger.warning("pre-commit install failed: %s", exc)

    # --- subprocess helper ---

    @staticmethod
    async def _run(*cmd: str, cwd: Path) -> str:
        """Run a subprocess and return stdout.

        Raises :class:`RuntimeError` on non-zero exit.
        """
        env = {**os.environ}
        # Prevent CLAUDECODE nesting detection
        env.pop("CLAUDECODE", None)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"Command {cmd!r} failed (rc={proc.returncode}): "
                f"{stderr.decode().strip()}"
            )
        return stdout.decode().strip()
