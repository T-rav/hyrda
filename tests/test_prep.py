"""Tests for prep.py — Hydra lifecycle label preparation."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from prep import HYDRA_LABELS, PrepResult, _list_existing_labels, ensure_labels
from tests.helpers import ConfigFactory

# ---------------------------------------------------------------------------
# PrepResult.summary()
# ---------------------------------------------------------------------------


class TestPrepResultSummary:
    """Tests for PrepResult.summary() formatting."""

    def test_all_created(self) -> None:
        result = PrepResult(created=["a", "b", "c"], existed=[], failed=[])
        assert result.summary() == "Created 3 labels, 0 already existed"

    def test_all_existed(self) -> None:
        result = PrepResult(created=[], existed=["a", "b"], failed=[])
        assert result.summary() == "Created 0 labels, 2 already existed"

    def test_mixed(self) -> None:
        result = PrepResult(
            created=["a", "b", "c", "d", "e"],
            existed=["f", "g"],
            failed=[],
        )
        assert result.summary() == "Created 5 labels, 2 already existed"

    def test_with_failures(self) -> None:
        result = PrepResult(
            created=["a"],
            existed=["b"],
            failed=["c", "d"],
        )
        assert result.summary() == "Created 1 labels, 1 already existed, 2 failed"

    def test_empty(self) -> None:
        result = PrepResult()
        assert result.summary() == "Created 0 labels, 0 already existed"


# ---------------------------------------------------------------------------
# _list_existing_labels
# ---------------------------------------------------------------------------


def _make_subprocess_mock(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> AsyncMock:
    """Build a mock for asyncio.create_subprocess_exec."""
    mock_proc = AsyncMock()
    mock_proc.returncode = returncode
    mock_proc.communicate = AsyncMock(return_value=(stdout.encode(), stderr.encode()))
    mock_proc.wait = AsyncMock(return_value=returncode)
    return AsyncMock(return_value=mock_proc)


class TestListExistingLabels:
    """Tests for _list_existing_labels()."""

    @pytest.mark.asyncio
    async def test_parses_json(self) -> None:
        config = ConfigFactory.create()
        labels_json = json.dumps([{"name": "bug"}, {"name": "hydra-plan"}])
        mock = _make_subprocess_mock(stdout=labels_json)

        with patch("asyncio.create_subprocess_exec", mock):
            result = await _list_existing_labels(config)

        assert result == {"bug", "hydra-plan"}

    @pytest.mark.asyncio
    async def test_empty_repo(self) -> None:
        config = ConfigFactory.create()
        mock = _make_subprocess_mock(stdout="[]")

        with patch("asyncio.create_subprocess_exec", mock):
            result = await _list_existing_labels(config)

        assert result == set()

    @pytest.mark.asyncio
    async def test_error_returns_empty(self) -> None:
        config = ConfigFactory.create()
        mock = _make_subprocess_mock(returncode=1, stderr="not found")

        with patch("asyncio.create_subprocess_exec", mock):
            result = await _list_existing_labels(config)

        assert result == set()


# ---------------------------------------------------------------------------
# ensure_labels
# ---------------------------------------------------------------------------


class TestEnsureLabels:
    """Tests for ensure_labels()."""

    @pytest.mark.asyncio
    async def test_creates_all_labels(self) -> None:
        """When no labels exist, all are created."""
        config = ConfigFactory.create()
        # First call: gh label list (returns empty)
        # Subsequent calls: gh label create (returns success)
        call_count = 0

        async def side_effect(*args, **_kwargs):
            nonlocal call_count
            call_count += 1
            proc = AsyncMock()
            proc.returncode = 0
            proc.wait = AsyncMock(return_value=0)
            # First call is label list
            if args[1] == "label" and args[2] == "list":
                proc.communicate = AsyncMock(return_value=(b"[]", b""))
            else:
                proc.communicate = AsyncMock(return_value=(b"", b""))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=side_effect):
            result = await ensure_labels(config)

        # All labels should be created (none existed)
        assert len(result.created) == len(HYDRA_LABELS)
        assert len(result.existed) == 0
        assert len(result.failed) == 0

    @pytest.mark.asyncio
    async def test_reports_existing(self) -> None:
        """Labels already in the repo are classified as 'existed'."""
        config = ConfigFactory.create()
        # Use actual label names from config (ConfigFactory uses "test-label"
        # for ready_label, not "hydra-ready")
        existing = (
            list(config.find_label)
            + list(config.planner_label)
            + list(config.ready_label)
        )
        existing_json = json.dumps([{"name": n} for n in existing])

        async def side_effect(*args, **_kwargs):
            proc = AsyncMock()
            proc.returncode = 0
            proc.wait = AsyncMock(return_value=0)
            if args[1] == "label" and args[2] == "list":
                proc.communicate = AsyncMock(return_value=(existing_json.encode(), b""))
            else:
                proc.communicate = AsyncMock(return_value=(b"", b""))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=side_effect):
            result = await ensure_labels(config)

        assert set(result.existed) == set(existing)
        assert len(result.created) + len(result.existed) == len(HYDRA_LABELS)
        assert len(result.failed) == 0

    @pytest.mark.asyncio
    async def test_uses_config_label_names(self) -> None:
        """Custom label names from config are used for creation."""
        config = ConfigFactory.create(
            find_label=["my-find"],
            planner_label=["my-plan"],
            ready_label=["my-ready"],
        )

        created_labels: list[str] = []

        async def side_effect(*args, **_kwargs):
            proc = AsyncMock()
            proc.returncode = 0
            proc.wait = AsyncMock(return_value=0)
            if args[1] == "label" and args[2] == "list":
                proc.communicate = AsyncMock(return_value=(b"[]", b""))
            else:
                # Capture the label name (arg after "create")
                arg_list = list(args)
                create_idx = arg_list.index("create")
                created_labels.append(arg_list[create_idx + 1])
                proc.communicate = AsyncMock(return_value=(b"", b""))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=side_effect):
            result = await ensure_labels(config)

        assert "my-find" in created_labels
        assert "my-plan" in created_labels
        assert "my-ready" in created_labels
        assert "my-find" in result.created

    @pytest.mark.asyncio
    async def test_dry_run_skips_creation(self) -> None:
        """In dry-run mode, no gh commands should be called."""
        config = ConfigFactory.create(dry_run=True)
        mock = _make_subprocess_mock()

        with patch("asyncio.create_subprocess_exec", mock):
            result = await ensure_labels(config)

        # No subprocess calls at all
        mock.assert_not_called()
        # But result should list what would be created
        assert len(result.created) == len(HYDRA_LABELS)
        assert len(result.existed) == 0

    @pytest.mark.asyncio
    async def test_handles_individual_failures(self) -> None:
        """One label failure doesn't prevent others from being created."""
        config = ConfigFactory.create()
        fail_label = "hydra-find"

        async def side_effect(*args, **_kwargs):
            proc = AsyncMock()
            proc.wait = AsyncMock(return_value=0)
            if args[1] == "label" and args[2] == "list":
                proc.returncode = 0
                proc.communicate = AsyncMock(return_value=(b"[]", b""))
            elif args[1] == "label" and args[2] == "create":
                label_name = args[3]
                if label_name == fail_label:
                    proc.returncode = 1
                    proc.communicate = AsyncMock(
                        return_value=(b"", b"error creating label")
                    )
                    proc.wait = AsyncMock(return_value=1)
                else:
                    proc.returncode = 0
                    proc.communicate = AsyncMock(return_value=(b"", b""))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=side_effect):
            result = await ensure_labels(config)

        assert fail_label in result.failed
        assert len(result.created) == len(HYDRA_LABELS) - 1
        assert len(result.failed) == 1

    @pytest.mark.asyncio
    async def test_handles_list_failure(self) -> None:
        """If gh label list fails, all labels are treated as new."""
        config = ConfigFactory.create()

        async def side_effect(*args, **_kwargs):
            proc = AsyncMock()
            proc.wait = AsyncMock(return_value=0)
            if args[1] == "label" and args[2] == "list":
                proc.returncode = 1
                proc.communicate = AsyncMock(return_value=(b"", b"not found"))
                proc.wait = AsyncMock(return_value=1)
            else:
                proc.returncode = 0
                proc.communicate = AsyncMock(return_value=(b"", b""))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=side_effect):
            result = await ensure_labels(config)

        # All should be "created" since list failed (empty existing set)
        assert len(result.created) == len(HYDRA_LABELS)
        assert len(result.existed) == 0

    @pytest.mark.asyncio
    async def test_all_already_exist(self) -> None:
        """All labels already present are classified as 'existed'."""
        config = ConfigFactory.create()
        # Build the list of all default label names
        all_names = []
        for cfg_field, _, _ in HYDRA_LABELS:
            all_names.extend(getattr(config, cfg_field))
        existing_json = json.dumps([{"name": n} for n in all_names])

        async def side_effect(*args, **_kwargs):
            proc = AsyncMock()
            proc.returncode = 0
            proc.wait = AsyncMock(return_value=0)
            if args[1] == "label" and args[2] == "list":
                proc.communicate = AsyncMock(return_value=(existing_json.encode(), b""))
            else:
                proc.communicate = AsyncMock(return_value=(b"", b""))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=side_effect):
            result = await ensure_labels(config)

        assert len(result.created) == 0
        assert len(result.existed) == len(HYDRA_LABELS)
        assert len(result.failed) == 0
