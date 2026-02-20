"""Tests for the shared subprocess helper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from subprocess_util import make_clean_env, run_subprocess


def _make_proc(
    returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""
) -> AsyncMock:
    """Build a minimal mock subprocess object."""
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


# --- success path ---


@pytest.mark.asyncio
async def test_returns_stdout_on_success() -> None:
    proc = _make_proc(stdout=b"  hello world  ")
    with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
        result = await run_subprocess("echo", "hi")

    assert result == "hello world"
    mock_exec.assert_awaited_once()


# --- error path ---


@pytest.mark.asyncio
async def test_raises_runtime_error_on_nonzero_exit() -> None:
    proc = _make_proc(returncode=1, stderr=b"boom")
    with (
        patch("asyncio.create_subprocess_exec", return_value=proc),
        pytest.raises(RuntimeError, match=r"boom"),
    ):
        await run_subprocess("false")


@pytest.mark.asyncio
async def test_error_message_includes_command_and_returncode() -> None:
    proc = _make_proc(returncode=42, stderr=b"bad stuff")
    with (
        patch("asyncio.create_subprocess_exec", return_value=proc),
        pytest.raises(RuntimeError, match=r"rc=42") as exc_info,
    ):
        await run_subprocess("git", "status")
    assert "('git', 'status')" in str(exc_info.value)


# --- environment ---


@pytest.mark.asyncio
async def test_strips_claudecode_from_env() -> None:
    proc = _make_proc()
    with (
        patch.dict("os.environ", {"CLAUDECODE": "1", "HOME": "/tmp"}, clear=False),
        patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec,
    ):
        await run_subprocess("ls")

    call_kwargs = mock_exec.call_args.kwargs
    assert "CLAUDECODE" not in call_kwargs["env"]


@pytest.mark.asyncio
async def test_sets_gh_token_when_provided() -> None:
    proc = _make_proc()
    with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
        await run_subprocess("gh", "pr", "list", gh_token="ghp_secret")

    call_kwargs = mock_exec.call_args.kwargs
    assert call_kwargs["env"]["GH_TOKEN"] == "ghp_secret"


@pytest.mark.asyncio
async def test_no_gh_token_when_empty() -> None:
    """When gh_token is empty, GH_TOKEN is not injected into the env."""
    proc = _make_proc()
    env_without_token = {"HOME": "/tmp", "PATH": "/usr/bin"}
    with (
        patch.dict("os.environ", env_without_token, clear=True),
        patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec,
    ):
        await run_subprocess("gh", "pr", "list", gh_token="")

    call_kwargs = mock_exec.call_args.kwargs
    assert "GH_TOKEN" not in call_kwargs["env"]


@pytest.mark.asyncio
async def test_does_not_inject_gh_token_when_absent_from_env() -> None:
    proc = _make_proc()
    env_without_token = {"HOME": "/tmp", "PATH": "/usr/bin"}
    with (
        patch.dict("os.environ", env_without_token, clear=True),
        patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec,
    ):
        await run_subprocess("ls", gh_token="")

    call_kwargs = mock_exec.call_args.kwargs
    assert "GH_TOKEN" not in call_kwargs["env"]


# --- cwd ---


@pytest.mark.asyncio
async def test_passes_cwd_when_provided() -> None:
    proc = _make_proc()
    with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
        await run_subprocess("ls", cwd=Path("/some/dir"))

    call_kwargs = mock_exec.call_args.kwargs
    assert call_kwargs["cwd"] == "/some/dir"


@pytest.mark.asyncio
async def test_no_cwd_when_none() -> None:
    proc = _make_proc()
    with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
        await run_subprocess("ls")

    call_kwargs = mock_exec.call_args.kwargs
    assert call_kwargs["cwd"] is None


# --- make_clean_env ---


def test_make_clean_env_strips_claudecode() -> None:
    with patch.dict("os.environ", {"CLAUDECODE": "1", "HOME": "/tmp"}, clear=False):
        env = make_clean_env()
    assert "CLAUDECODE" not in env


def test_make_clean_env_preserves_other_vars() -> None:
    with patch.dict("os.environ", {"FOO": "bar", "HOME": "/tmp"}, clear=True):
        env = make_clean_env()
    assert env["FOO"] == "bar"
    assert env["HOME"] == "/tmp"


def test_make_clean_env_sets_gh_token() -> None:
    env = make_clean_env(gh_token="ghp_secret")
    assert env["GH_TOKEN"] == "ghp_secret"


def test_make_clean_env_no_gh_token() -> None:
    env_without_token = {"HOME": "/tmp", "PATH": "/usr/bin"}
    with patch.dict("os.environ", env_without_token, clear=True):
        env = make_clean_env()
    assert "GH_TOKEN" not in env


def test_make_clean_env_does_not_mutate_os_environ() -> None:
    with patch.dict("os.environ", {"CLAUDECODE": "1"}, clear=False):
        make_clean_env(gh_token="ghp_secret")
        # Verify os.environ was NOT mutated inside the same context:
        # CLAUDECODE should still be present (not popped from the real env)
        import os

        assert os.environ.get("CLAUDECODE") == "1"
