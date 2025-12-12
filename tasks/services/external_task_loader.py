"""Dynamic task loader for system and external tasks/jobs.

Loads tasks from two sources:
1. System tasks (jobs/system/) - Built into image, always available
2. External tasks (external_tasks/) - Client-provided, mounted at runtime

Allows clients to mount their own tasks directory and load jobs at runtime
without rebuilding the Docker image. Supports hot-reload for development.

Client Usage:
    1. Mount tasks directory in docker-compose.yml:
       volumes:
         - ./my_tasks:/app/external_tasks:ro

    2. Set environment variable:
       EXTERNAL_TASKS_PATH=/app/external_tasks

    3. Task directory structure:
       /app/external_tasks/
       ├── my_task/
       │   ├── job.py (must have Job class extending BaseJob)
       │   └── requirements.txt (optional, client must pre-install)
       └── another_task/
           └── job.py
"""

import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ExternalTaskLoader:
    """Loads tasks/jobs from system (built-in) and external (client-provided) directories."""

    def __init__(self, external_tasks_path: str | None = None):
        """Initialize task loader.

        Args:
            external_tasks_path: Path to external tasks directory.
                                 Defaults to EXTERNAL_TASKS_PATH env var.
        """
        # System tasks path (built into image)
        self.system_path = Path(__file__).parent.parent / "jobs" / "system"

        # External tasks path (client-provided)
        self.external_path = external_tasks_path or os.getenv("EXTERNAL_TASKS_PATH")

        self._loaded_tasks: dict[str, type] = {}
        self._task_modules: dict[str, Any] = {}  # Track modules for reload

        logger.info(f"System tasks path: {self.system_path}")
        if self.external_path:
            logger.info(f"External tasks path: {self.external_path}")
        else:
            logger.info("No external tasks path configured (EXTERNAL_TASKS_PATH not set)")

    def discover_tasks(self) -> dict[str, type]:
        """Discover and load all tasks from system and external directories.

        System tasks (jobs/system/) are loaded first, then external tasks.
        External tasks can override system tasks if they have the same name.

        Returns:
            Dict mapping task names to task/job classes
        """
        discovered = {}

        # 1. Load system tasks (built into image)
        if self.system_path.exists():
            logger.info(f"Scanning system tasks: {self.system_path}")
            discovered.update(self._scan_task_directory(self.system_path, "system"))
        else:
            logger.warning(f"System tasks directory not found: {self.system_path}")

        # 2. Load external tasks (client-provided, can override system)
        if self.external_path:
            external_dir = Path(self.external_path)
            if external_dir.exists():
                logger.info(f"Scanning external tasks: {self.external_path}")
                external_tasks = self._scan_task_directory(external_dir, "external")

                # Warn if external task overrides system task
                for task_name in external_tasks:
                    if task_name in discovered:
                        logger.warning(
                            f"⚠️ External task '{task_name}' overrides system task"
                        )

                discovered.update(external_tasks)
            else:
                logger.warning(f"External tasks directory not found: {self.external_path}")
        else:
            logger.info("No external tasks configured")

        self._loaded_tasks = discovered
        logger.info(
            f"✅ Loaded {len(discovered)} tasks "
            f"(system + external)"
        )
        return discovered

    def _scan_task_directory(
        self, directory: Path, source_type: str
    ) -> dict[str, type]:
        """Scan a directory for task modules.

        Args:
            directory: Directory to scan
            source_type: 'system' or 'external' (for logging)

        Returns:
            Dict mapping task names to job classes
        """
        discovered = {}

        # Scan for task directories
        for task_dir in directory.iterdir():
            if not task_dir.is_dir() or task_dir.name.startswith("_"):
                continue

            job_file = task_dir / "job.py"
            if not job_file.exists():
                logger.warning(f"Skipping {task_dir.name}: No job.py found")
                continue

            # Use cached version if already loaded (for performance)
            if task_dir.name in self._loaded_tasks:
                discovered[task_dir.name] = self._loaded_tasks[task_dir.name]
                continue

            try:
                job_class = self._load_task_module(
                    task_dir.name, job_file, source_type
                )
                if job_class:
                    discovered[task_dir.name] = job_class
                    logger.info(f"✅ Loaded {source_type} task: {task_dir.name}")
            except Exception as e:
                logger.error(
                    f"❌ Failed to load {source_type} task {task_dir.name}: {e}",
                    exc_info=True,
                )

        return discovered

    def _load_task_module(
        self, task_name: str, job_file: Path, source_type: str = "external"
    ) -> type | None:
        """Load job class from Python file.

        Args:
            task_name: Name of the task
            job_file: Path to job.py file
            source_type: 'system' or 'external' (for module naming)

        Returns:
            Job class if found, None otherwise
        """
        # Use appropriate module prefix based on source
        if source_type == "system":
            module_name = f"jobs.system.{task_name}"
        else:
            module_name = f"external_tasks.{task_name}"

        try:
            # Load module from file
            spec = importlib.util.spec_from_file_location(module_name, job_file)
            if not spec or not spec.loader:
                raise ImportError(f"Cannot load module spec from {job_file}")

            module = importlib.util.module_from_spec(spec)

            # Add parent directory to sys.path for relative imports
            parent_dir = str(job_file.parent)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)

            # Execute module
            spec.loader.exec_module(module)

            # Store module for hot-reload
            self._task_modules[task_name] = module

            # Find Job class (primary) or fall back to class with Job in name
            if hasattr(module, "Job"):
                job_class = getattr(module, "Job")
            else:
                # Try to find a class ending with "Job" (defined in this module, not imported)
                job_class = None
                candidates = []
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and attr_name.endswith("Job"):
                        # Only consider classes defined in this module (not imported)
                        if attr.__module__ == module_name:
                            candidates.append((attr_name, attr))

                # Prefer longer names (more specific, e.g., "MyCustomJob" over "Job")
                if candidates:
                    candidates.sort(key=lambda x: len(x[0]), reverse=True)
                    job_class = candidates[0][1]

                if not job_class:
                    raise AttributeError(
                        f"Module {job_file} must define a 'Job' class or a class ending with 'Job'"
                    )

            return job_class

        except Exception as e:
            logger.error(f"Error loading task module {task_name}: {e}", exc_info=True)
            return None

    def reload_task(self, task_name: str) -> type | None:
        """Reload an external task (hot-reload for development).

        Args:
            task_name: Name of the task to reload

        Returns:
            Reloaded job class if successful, None otherwise
        """
        if not self.external_path:
            logger.warning("Cannot reload: EXTERNAL_TASKS_PATH not set")
            return None

        task_dir = Path(self.external_path) / task_name
        job_file = task_dir / "job.py"

        if not job_file.exists():
            logger.warning(f"Cannot reload {task_name}: job.py not found")
            return None

        try:
            # Remove from cache
            if task_name in self._loaded_tasks:
                del self._loaded_tasks[task_name]

            # Remove module from sys.modules
            module_name = f"external_tasks.{task_name}"
            if module_name in sys.modules:
                del sys.modules[module_name]

            # Reload
            job_class = self._load_task_module(task_name, job_file)
            if job_class:
                self._loaded_tasks[task_name] = job_class
                logger.info(f"♻️ Reloaded external task: {task_name}")
                return job_class

        except Exception as e:
            logger.error(f"Failed to reload task {task_name}: {e}", exc_info=True)

        return None

    def get_task_class(self, task_name: str) -> type | None:
        """Get task/job class by name.

        Args:
            task_name: Name of the task

        Returns:
            Job class if found, None otherwise
        """
        return self._loaded_tasks.get(task_name)

    def list_external_tasks(self) -> list[str]:
        """List all loaded external task names.

        Returns:
            List of task names
        """
        return list(self._loaded_tasks.keys())


# Global loader instance
_external_loader: ExternalTaskLoader | None = None


def get_external_loader() -> ExternalTaskLoader:
    """Get or create global external task loader."""
    global _external_loader
    if _external_loader is None:
        _external_loader = ExternalTaskLoader()
        # Auto-discover on first access
        _external_loader.discover_tasks()
    return _external_loader


def reload_external_task(task_name: str) -> bool:
    """Reload an external task (hot-reload for development).

    Args:
        task_name: Name of the task to reload

    Returns:
        True if reload successful, False otherwise
    """
    loader = get_external_loader()
    return loader.reload_task(task_name) is not None
