"""Tests for docker_image config field in HydraConfig."""

from __future__ import annotations

from pathlib import Path

import pytest

from config import HydraConfig

DEFAULT_DOCKER_IMAGE = "ghcr.io/t-rav/hydra-agent:latest"


# ---------------------------------------------------------------------------
# HydraConfig – docker_image field
# ---------------------------------------------------------------------------


class TestDockerImageConfig:
    """Tests for the docker_image config field and env var override."""

    def test_docker_image_default_value(self, tmp_path: Path) -> None:
        """Default docker_image should be the GHCR image tag."""
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.docker_image == DEFAULT_DOCKER_IMAGE

    def test_docker_image_explicit_value_preserved(self, tmp_path: Path) -> None:
        """Explicit docker_image value should be preserved as-is."""
        cfg = HydraConfig(
            docker_image="my-registry/custom-image:v2",
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.docker_image == "my-registry/custom-image:v2"

    def test_docker_image_env_var_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """HYDRA_DOCKER_IMAGE env var should override the default."""
        monkeypatch.setenv("HYDRA_DOCKER_IMAGE", "custom/agent:dev")
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.docker_image == "custom/agent:dev"

    def test_docker_image_explicit_not_overridden_by_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicit docker_image should NOT be overridden by env var."""
        monkeypatch.setenv("HYDRA_DOCKER_IMAGE", "env/override:latest")
        cfg = HydraConfig(
            docker_image="explicit/image:v1",
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.docker_image == "explicit/image:v1"

    def test_docker_image_env_var_not_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without env var, default should be used."""
        monkeypatch.delenv("HYDRA_DOCKER_IMAGE", raising=False)
        cfg = HydraConfig(
            repo_root=tmp_path,
            worktree_base=tmp_path / "wt",
            state_file=tmp_path / "s.json",
        )
        assert cfg.docker_image == DEFAULT_DOCKER_IMAGE
