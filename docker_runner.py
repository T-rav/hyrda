"""Docker-based subprocess runner for Hydra agent execution.

Executes agent commands inside Docker containers with volume mounting,
environment isolation, and stream handling. Implements the
:class:`SubprocessRunner` protocol from :mod:`execution`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from execution import HostRunner, SimpleResult, get_default_runner

if TYPE_CHECKING:
    from config import HydraFlowConfig

logger = logging.getLogger("hydraflow.docker_runner")


class DockerStdinWriter:
    """Wraps a Docker attach socket to provide a stdin-like write interface."""

    def __init__(self, socket: Any) -> None:
        self._socket = socket
        self._closed = False

    def write(self, data: bytes) -> None:
        if self._closed:
            return
        sock = getattr(self._socket, "_sock", self._socket)
        sock.sendall(data)

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        self._closed = True


class DockerStdoutReader:
    """Async iterator that reads lines from a Docker attach stream.

    Compatible with the ``async for raw in stdout_stream:`` pattern
    used in :func:`stream_claude_process`.
    """

    def __init__(self, socket: Any, loop: asyncio.AbstractEventLoop) -> None:
        self._socket = socket
        self._loop = loop
        self._buffer = b""
        self._eof = False

    def __aiter__(self) -> DockerStdoutReader:
        return self

    async def __anext__(self) -> bytes:
        while True:
            if b"\n" in self._buffer:
                line, self._buffer = self._buffer.split(b"\n", 1)
                return line + b"\n"
            if self._eof:
                if self._buffer:
                    remaining = self._buffer
                    self._buffer = b""
                    return remaining
                raise StopAsyncIteration

            chunk = await self._loop.run_in_executor(None, self._read_chunk)
            if not chunk:
                self._eof = True
            else:
                self._buffer += chunk

    def _read_chunk(self) -> bytes:
        sock = getattr(self._socket, "_sock", self._socket)
        try:
            return sock.recv(8192)
        except OSError:
            return b""

    async def read(self) -> bytes:
        """Read all remaining data (for stderr compatibility)."""
        chunks: list[bytes] = []
        while True:
            chunk = await self._loop.run_in_executor(None, self._read_chunk)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)


class DockerProcess:
    """Wraps a Docker container to present an ``asyncio.subprocess.Process``-like interface.

    This adapter allows :func:`stream_claude_process` to consume Docker
    container output without changes.
    """

    def __init__(
        self,
        container: Any,
        socket: Any,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._container = container
        self._socket = socket
        self._loop = loop
        self.stdin = DockerStdinWriter(socket)
        self.stdout = DockerStdoutReader(socket, loop)
        self.stderr = DockerStdoutReader(socket, loop)
        self.returncode: int | None = None
        self.pid: int | None = None

    def kill(self) -> None:
        with contextlib.suppress(Exception):
            self._container.kill()

    async def wait(self) -> int:
        result = await self._loop.run_in_executor(None, self._container.wait)
        code = int(result.get("StatusCode", 1))
        self.returncode = code
        return code


class DockerRunner:
    """Runs commands inside Docker containers with volume mounting and env isolation.

    Implements the :class:`SubprocessRunner` protocol from :mod:`execution`.
    """

    def __init__(
        self,
        *,
        image: str,
        repo_root: Path,
        log_dir: Path,
        gh_token: str = "",
        git_user_name: str = "",
        git_user_email: str = "",
        spawn_delay: float = 2.0,
        network: str = "",
        extra_mounts: list[str] | None = None,
    ) -> None:
        import docker  # noqa: PLC0415

        self._client = docker.from_env()
        self._image = image
        self._repo_root = repo_root
        self._log_dir = log_dir
        self._gh_token = gh_token
        self._git_user_name = git_user_name
        self._git_user_email = git_user_email
        self._spawn_delay = spawn_delay
        self._network = network
        self._extra_mounts = extra_mounts or []
        self._spawn_lock = asyncio.Lock()
        self._last_spawn_time: float = 0.0
        self._containers: set[Any] = set()

    def _build_mounts(self, cwd: str | None) -> dict[str, dict[str, str]]:
        """Build Docker volume mount specification."""
        mounts: dict[str, dict[str, str]] = {}
        if cwd:
            mounts[cwd] = {"bind": "/workspace", "mode": "rw"}
        mounts[str(self._repo_root)] = {"bind": "/repo", "mode": "ro"}
        self._log_dir.mkdir(parents=True, exist_ok=True)
        mounts[str(self._log_dir)] = {"bind": "/logs", "mode": "rw"}
        for spec in self._extra_mounts:
            parts = spec.split(":")
            if len(parts) >= 2:
                mode = parts[2] if len(parts) > 2 else "ro"
                mounts[parts[0]] = {"bind": parts[1], "mode": mode}
        return mounts

    def _build_env(self) -> dict[str, str]:
        """Build minimal environment for the container."""
        from subprocess_util import make_docker_env  # noqa: PLC0415

        return make_docker_env(
            gh_token=self._gh_token,
            git_user_name=self._git_user_name,
            git_user_email=self._git_user_email,
        )

    async def _enforce_spawn_delay(self) -> None:
        """Ensure minimum delay between container starts."""
        async with self._spawn_lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_spawn_time
            if elapsed < self._spawn_delay:
                await asyncio.sleep(self._spawn_delay - elapsed)
            self._last_spawn_time = asyncio.get_event_loop().time()

    async def create_streaming_process(
        self,
        cmd: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        stdin: int | None = None,  # noqa: ARG002
        stdout: int | None = None,  # noqa: ARG002
        stderr: int | None = None,  # noqa: ARG002
        limit: int = 1024 * 1024,  # noqa: ARG002
        start_new_session: bool = True,  # noqa: ARG002
    ) -> DockerProcess:
        """Create a streaming Docker container process.

        Mounts the worktree directory (``cwd``) as ``/workspace`` inside
        the container and returns a :class:`DockerProcess` wrapper that
        provides the same interface as ``asyncio.subprocess.Process``.
        """
        await self._enforce_spawn_delay()

        loop = asyncio.get_event_loop()
        mounts = self._build_mounts(cwd)
        container_env = env if env is not None else self._build_env()
        working_dir = "/workspace" if cwd else None

        container_kwargs: dict[str, Any] = {
            "image": self._image,
            "command": cmd,
            "environment": container_env,
            "volumes": mounts,
            "stdin_open": True,
            "detach": True,
        }
        if working_dir:
            container_kwargs["working_dir"] = working_dir
        if self._network:
            container_kwargs["network"] = self._network

        container = await loop.run_in_executor(
            None,
            lambda: self._client.containers.create(**container_kwargs),  # type: ignore[arg-type]
        )
        self._containers.add(container)

        try:
            await loop.run_in_executor(None, container.start)
            socket = await loop.run_in_executor(
                None,
                lambda: container.attach_socket(
                    params={"stdin": 1, "stdout": 1, "stderr": 1, "stream": 1}
                ),
            )
            return DockerProcess(container, socket, loop)
        except Exception:
            with contextlib.suppress(Exception):
                await loop.run_in_executor(None, lambda: container.remove(force=True))
            self._containers.discard(container)
            raise

    async def run_simple(
        self,
        cmd: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 120.0,
    ) -> SimpleResult:
        """Run a command in a Docker container and return the result."""
        await self._enforce_spawn_delay()

        loop = asyncio.get_event_loop()
        mounts = self._build_mounts(cwd)
        container_env = env if env is not None else self._build_env()
        working_dir = "/workspace" if cwd else None

        container_kwargs: dict[str, Any] = {
            "image": self._image,
            "command": cmd,
            "environment": container_env,
            "volumes": mounts,
            "detach": True,
        }
        if working_dir:
            container_kwargs["working_dir"] = working_dir
        if self._network:
            container_kwargs["network"] = self._network

        container = await loop.run_in_executor(
            None,
            lambda: self._client.containers.create(**container_kwargs),
        )
        self._containers.add(container)

        try:
            await loop.run_in_executor(None, container.start)

            result = await asyncio.wait_for(
                loop.run_in_executor(None, container.wait),
                timeout=timeout,
            )

            logs_stdout = await loop.run_in_executor(
                None,
                lambda: container.logs(stdout=True, stderr=False).decode(
                    errors="replace"
                ),
            )
            logs_stderr = await loop.run_in_executor(
                None,
                lambda: container.logs(stdout=False, stderr=True).decode(
                    errors="replace"
                ),
            )

            return SimpleResult(
                stdout=logs_stdout.strip(),
                stderr=logs_stderr.strip(),
                returncode=result["StatusCode"],
            )
        except TimeoutError:
            with contextlib.suppress(Exception):
                await loop.run_in_executor(None, container.kill)
            raise
        finally:
            with contextlib.suppress(Exception):
                await loop.run_in_executor(None, lambda: container.remove(force=True))
            self._containers.discard(container)

    async def cleanup(self) -> None:
        """Remove all tracked containers."""
        loop = asyncio.get_event_loop()
        for container in list(self._containers):
            with contextlib.suppress(Exception):
                await loop.run_in_executor(
                    None, lambda c=container: c.remove(force=True)
                )
        self._containers.clear()


def _check_docker_available() -> bool:
    """Check if Docker daemon is accessible."""
    try:
        import docker  # noqa: PLC0415

        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def get_docker_runner(config: HydraFlowConfig) -> DockerRunner | HostRunner:
    """Factory: returns DockerRunner if Docker is available, else HostRunner.

    Falls back to host runner with a warning if:
    - ``docker_enabled`` is False
    - ``docker_image`` is not configured
    - Docker daemon is not available
    """
    if not config.docker_enabled:
        return get_default_runner()

    if not config.docker_image:
        logger.warning(
            "docker_enabled=True but no docker_image configured; "
            "falling back to host runner"
        )
        return get_default_runner()

    if not _check_docker_available():
        logger.warning("Docker daemon not available; falling back to host runner")
        return get_default_runner()

    log_dir = config.repo_root / ".hydraflow" / "logs"
    return DockerRunner(
        image=config.docker_image,
        repo_root=config.repo_root,
        log_dir=log_dir,
        gh_token=config.gh_token,
        git_user_name=config.git_user_name,
        git_user_email=config.git_user_email,
        spawn_delay=config.docker_spawn_delay,
        network=config.docker_network,
        extra_mounts=config.docker_extra_mounts,
    )
