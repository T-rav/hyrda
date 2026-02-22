"""Tests for execution.py — SubprocessRunner protocol and HostRunner."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from execution import HostRunner, SimpleResult, SubprocessRunner, get_default_runner

# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestSubprocessRunnerProtocol:
    """Verify the SubprocessRunner protocol is runtime-checkable."""

    def test_host_runner_is_subprocess_runner(self) -> None:
        runner = HostRunner()
        assert isinstance(runner, SubprocessRunner)

    def test_mock_implementing_both_methods_satisfies_protocol(self) -> None:
        mock = AsyncMock(spec=SubprocessRunner)
        assert isinstance(mock, SubprocessRunner)


# ---------------------------------------------------------------------------
# SimpleResult
# ---------------------------------------------------------------------------


class TestSimpleResult:
    """SimpleResult dataclass tests."""

    def test_fields(self) -> None:
        result = SimpleResult(stdout="hello", stderr="", returncode=0)
        assert result.stdout == "hello"
        assert result.stderr == ""
        assert result.returncode == 0

    def test_non_zero_returncode(self) -> None:
        result = SimpleResult(stdout="", stderr="error", returncode=1)
        assert result.returncode == 1
        assert result.stderr == "error"


# ---------------------------------------------------------------------------
# HostRunner.create_streaming_process
# ---------------------------------------------------------------------------


class TestHostRunnerCreateStreamingProcess:
    """Tests for HostRunner.create_streaming_process."""

    @pytest.mark.asyncio
    async def test_calls_create_subprocess_exec_with_correct_args(self) -> None:
        mock_proc = AsyncMock()
        mock_create = AsyncMock(return_value=mock_proc)

        runner = HostRunner()
        with patch("asyncio.create_subprocess_exec", mock_create):
            result = await runner.create_streaming_process(
                ["claude", "-p"],
                cwd="/tmp/work",
                env={"FOO": "bar"},
                limit=1024 * 1024,
                start_new_session=True,
            )

        assert result is mock_proc
        mock_create.assert_called_once_with(
            "claude",
            "-p",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/tmp/work",
            env={"FOO": "bar"},
            limit=1024 * 1024,
            start_new_session=True,
        )

    @pytest.mark.asyncio
    async def test_cwd_none_when_not_given(self) -> None:
        mock_proc = AsyncMock()
        mock_create = AsyncMock(return_value=mock_proc)

        runner = HostRunner()
        with patch("asyncio.create_subprocess_exec", mock_create):
            await runner.create_streaming_process(["echo", "hi"])

        _, kwargs = mock_create.call_args
        assert kwargs["cwd"] is None

    @pytest.mark.asyncio
    async def test_default_limit_and_start_new_session(self) -> None:
        mock_proc = AsyncMock()
        mock_create = AsyncMock(return_value=mock_proc)

        runner = HostRunner()
        with patch("asyncio.create_subprocess_exec", mock_create):
            await runner.create_streaming_process(["echo", "hi"])

        _, kwargs = mock_create.call_args
        assert kwargs["limit"] == 65536
        assert kwargs["start_new_session"] is False

    @pytest.mark.asyncio
    async def test_custom_env_forwarded(self) -> None:
        mock_proc = AsyncMock()
        mock_create = AsyncMock(return_value=mock_proc)

        runner = HostRunner()
        env = {"PATH": "/usr/bin", "HOME": "/root"}
        with patch("asyncio.create_subprocess_exec", mock_create):
            await runner.create_streaming_process(["ls"], env=env)

        _, kwargs = mock_create.call_args
        assert kwargs["env"] == env


# ---------------------------------------------------------------------------
# HostRunner.run_simple
# ---------------------------------------------------------------------------


class TestHostRunnerRunSimple:
    """Tests for HostRunner.run_simple."""

    @pytest.mark.asyncio
    async def test_success_returns_simple_result(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"  output  ", b""))

        runner = HostRunner()
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            result = await runner.run_simple(["echo", "hi"])

        assert isinstance(result, SimpleResult)
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.returncode == 0

    @pytest.mark.asyncio
    async def test_non_zero_exit_returns_correct_returncode(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error msg"))

        runner = HostRunner()
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            result = await runner.run_simple(["false"])

        assert result.returncode == 1
        assert result.stderr == "error msg"

    @pytest.mark.asyncio
    async def test_timeout_kills_process_and_raises(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=TimeoutError)
        mock_proc.kill = AsyncMock()
        mock_proc.wait = AsyncMock()

        runner = HostRunner()
        with (
            patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)),
            pytest.raises(TimeoutError),
        ):
            await runner.run_simple(["sleep", "999"], timeout=0.01)

        mock_proc.kill.assert_called_once()
        mock_proc.wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_cwd_forwarded(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))
        mock_create = AsyncMock(return_value=mock_proc)

        runner = HostRunner()
        with patch("asyncio.create_subprocess_exec", mock_create):
            await runner.run_simple(["ls"], cwd="/tmp/dir")

        _, kwargs = mock_create.call_args
        assert kwargs["cwd"] == "/tmp/dir"

    @pytest.mark.asyncio
    async def test_env_forwarded(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"ok", b""))
        mock_create = AsyncMock(return_value=mock_proc)

        runner = HostRunner()
        env = {"MY_VAR": "123"}
        with patch("asyncio.create_subprocess_exec", mock_create):
            await runner.run_simple(["env"], env=env)

        _, kwargs = mock_create.call_args
        assert kwargs["env"] == env

    @pytest.mark.asyncio
    async def test_stdout_stderr_are_stripped(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(b"\n  hello world  \n", b"  warn  \n")
        )

        runner = HostRunner()
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)):
            result = await runner.run_simple(["echo"])

        assert result.stdout == "hello world"
        assert result.stderr == "warn"


# ---------------------------------------------------------------------------
# get_default_runner
# ---------------------------------------------------------------------------


class TestGetDefaultRunner:
    """Tests for get_default_runner factory."""

    def test_returns_host_runner(self) -> None:
        import execution

        # Reset singleton to ensure clean state
        execution._default_runner = None
        runner = get_default_runner()
        assert isinstance(runner, HostRunner)

    def test_returns_same_instance_on_repeated_calls(self) -> None:
        import execution

        execution._default_runner = None
        runner1 = get_default_runner()
        runner2 = get_default_runner()
        assert runner1 is runner2
