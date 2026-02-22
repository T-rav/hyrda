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
        wt_path = self._config.worktree_path_for_issue(issue_number)
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
        wt_path = self._config.worktree_path_for_issue(issue_number)
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
        branch = self._config.branch_for_issue(issue_number)
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

    async def merge_main(self, worktree_path: Path, branch: str) -> bool:
        """Merge latest main into *branch* inside *worktree_path*.

        First pulls the branch itself so the local copy is in sync with
        the remote, then merges ``origin/main``.  Because this uses merge
        the subsequent push is always fast-forward.

        Returns *True* on success, *False* if conflicts arise.
        """
        try:
            await run_subprocess(
                "git",
                "fetch",
                "origin",
                self._config.main_branch,
                branch,
                cwd=worktree_path,
                gh_token=self._config.gh_token,
            )
            # Fast-forward local branch to match remote so push stays ff
            await run_subprocess(
                "git",
                "merge",
                "--ff-only",
                f"origin/{branch}",
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

    async def start_merge_main(self, worktree_path: Path, branch: str) -> bool:
        """Begin merging main into *branch*, leaving conflicts for manual resolution.

        Like :meth:`merge_main` but does **not** abort on conflict.
        The caller is expected to resolve the conflict markers and
        complete the merge with ``git add . && git commit --no-edit``.

        Returns *True* if the merge completed cleanly (no conflicts),
        *False* if conflicts remain in the working tree.
        """
        try:
            await run_subprocess(
                "git",
                "fetch",
                "origin",
                self._config.main_branch,
                branch,
                cwd=worktree_path,
                gh_token=self._config.gh_token,
            )
            # Fast-forward local branch to match remote
            await run_subprocess(
                "git",
                "merge",
                "--ff-only",
                f"origin/{branch}",
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
            # Leave conflict markers in place — caller will resolve
            return False

    async def abort_merge(self, worktree_path: Path) -> None:
        """Abort an in-progress merge in *worktree_path*."""
        with contextlib.suppress(RuntimeError):
            await run_subprocess(
                "git",
                "merge",
                "--abort",
                cwd=worktree_path,
                gh_token=self._config.gh_token,
            )

    async def get_main_commits_since_diverge(self, worktree_path: Path) -> str:
        """Return recent commits on main since the branch diverged.

        Runs ``git log --oneline HEAD..origin/main`` in *worktree_path*
        (after fetching main) and returns up to 30 commit summaries as a
        newline-separated string.  Returns an empty string on failure.
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
            output = await run_subprocess(
                "git",
                "log",
                "--oneline",
                f"HEAD..origin/{self._config.main_branch}",
                "-30",
                cwd=worktree_path,
                gh_token=self._config.gh_token,
            )
            return output.strip()
        except RuntimeError:
            logger.warning(
                "Could not get main commits since diverge in %s",
                worktree_path,
            )
            return ""

    # --- environment setup ---

    def _setup_env(self, wt_path: Path) -> None:
        """Symlink .env and node_modules into the worktree."""
        # Symlink .env
        env_src = self._repo_root / ".env"
        env_dst = wt_path / ".env"
        if env_src.exists() and not env_dst.exists():
            try:
                env_dst.symlink_to(env_src)
            except OSError:
                logger.debug(
                    "Could not symlink %s → %s", env_dst, env_src, exc_info=True
                )

        # Copy .claude/settings.local.json (not symlink - agents may modify)
        local_settings_src = self._repo_root / ".claude" / "settings.local.json"
        local_settings_dst = wt_path / ".claude" / "settings.local.json"
        if local_settings_src.exists() and not local_settings_dst.exists():
            try:
                local_settings_dst.parent.mkdir(parents=True, exist_ok=True)
                local_settings_dst.write_text(local_settings_src.read_text())
            except OSError:
                logger.debug(
                    "Could not copy settings to %s",
                    local_settings_dst,
                    exc_info=True,
                )

        # Symlink node_modules for each UI directory
        for ui_dir in self._UI_DIRS:
            nm_src = self._repo_root / ui_dir / "node_modules"
            nm_dst = wt_path / ui_dir / "node_modules"
            if nm_src.exists() and not nm_dst.exists():
                try:
                    nm_dst.parent.mkdir(parents=True, exist_ok=True)
                    nm_dst.symlink_to(nm_src)
                except OSError:
                    logger.debug(
                        "Could not symlink %s → %s",
                        nm_dst,
                        nm_src,
                        exc_info=True,
                    )

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
        except (RuntimeError, FileNotFoundError) as exc:
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
