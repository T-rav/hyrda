"""Docker container runner with resource limits and security hardening."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from config import HydraConfig

logger = logging.getLogger("hydra.docker")


class DockerRunner:
    """Runs agent commands inside Docker containers with resource constraints.

    Translates ``HydraConfig`` Docker settings into Docker SDK kwargs for
    ``containers.create()`` / ``containers.run()``.
    """

    def __init__(self, config: HydraConfig) -> None:
        self._config = config

    def _build_container_kwargs(self) -> dict[str, Any]:
        """Build Docker SDK kwargs for container resource limits and security.

        Returns a dict suitable for unpacking into ``client.containers.create()``
        or ``client.containers.run()``.
        """
        cfg = self._config
        kwargs: dict[str, Any] = {}

        # Resource limits
        kwargs["nano_cpus"] = int(cfg.docker_cpu_limit * 1e9)
        kwargs["mem_limit"] = cfg.docker_memory_limit
        kwargs["memswap_limit"] = cfg.docker_memory_limit  # No swap
        kwargs["pids_limit"] = cfg.docker_pids_limit

        # Network
        kwargs["network_mode"] = cfg.docker_network_mode

        # Security
        kwargs["read_only"] = cfg.docker_read_only_root
        security_opt: list[str] = []
        if cfg.docker_no_new_privileges:
            security_opt.append("no-new-privileges:true")
        if security_opt:
            kwargs["security_opt"] = security_opt
        kwargs["cap_drop"] = ["ALL"]

        # Writable tmpfs for /tmp
        kwargs["tmpfs"] = {"/tmp": f"size={cfg.docker_tmp_size}"}

        logger.info(
            "Container constraints: cpu=%.1f mem=%s pids=%d net=%s readonly=%s",
            cfg.docker_cpu_limit,
            cfg.docker_memory_limit,
            cfg.docker_pids_limit,
            cfg.docker_network_mode,
            cfg.docker_read_only_root,
        )

        return kwargs
