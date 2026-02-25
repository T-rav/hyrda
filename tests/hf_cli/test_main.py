from __future__ import annotations

from unittest.mock import Mock

from hf_cli import __main__ as hf_main


def test_entrypoint_prep_dispatches_to_scaffold_flag(monkeypatch) -> None:
    mock = Mock()
    monkeypatch.setattr(hf_main, "hydraflow_main", mock)

    hf_main.entrypoint(["prep"])

    mock.assert_called_once_with(["--scaffold"])


def test_entrypoint_scaffold_dispatches_to_scaffold_flag(monkeypatch) -> None:
    mock = Mock()
    monkeypatch.setattr(hf_main, "hydraflow_main", mock)

    hf_main.entrypoint(["scaffold"])

    mock.assert_called_once_with(["--scaffold"])


def test_entrypoint_ensure_labels_dispatches_to_prep_flag(monkeypatch) -> None:
    mock = Mock()
    monkeypatch.setattr(hf_main, "hydraflow_main", mock)

    hf_main.entrypoint(["ensure-labels"])

    mock.assert_called_once_with(["--prep"])
