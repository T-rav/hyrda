"""Google Drive document ingestion job."""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests

from config.settings import TasksSettings

from .base_job import BaseJob

logger = logging.getLogger(__name__)


class GoogleDriveIngestJob(BaseJob):
    """Job to ingest documents from Google Drive."""

    JOB_NAME = "Google Drive Ingest"
    JOB_DESCRIPTION = "Ingest and process documents from Google Drive folders"
    REQUIRED_PARAMS = ["folder_id"]
    OPTIONAL_PARAMS = ["metadata", "force_update", "file_types"]

    def __init__(self, settings: TasksSettings, **kwargs: Any):
        """Initialize the Google Drive ingest job."""
        super().__init__(settings, **kwargs)
        self.validate_params()

    def validate_params(self) -> bool:
        """Validate job parameters."""
        super().validate_params()

        folder_id = self.params.get("folder_id")
        if not folder_id:
            raise ValueError("folder_id parameter is required")

        # Check if Google credentials are configured
        if not self.settings.google_credentials_path:
            logger.warning("No Google credentials path configured")

        return True

    async def _execute_job(self) -> dict[str, Any]:
        """Execute the Google Drive ingest job."""
        folder_id = self.params["folder_id"]
        metadata = self.params.get("metadata", {})
        force_update = self.params.get("force_update", False)
        file_types = self.params.get("file_types", [])

        logger.info(f"Starting Google Drive ingest for folder: {folder_id}")

        try:
            # Run the ingestion process
            ingest_result = await self._run_ingest_process(
                folder_id, metadata, force_update, file_types
            )

            # Send results to main bot API if configured
            api_result = await self._send_results_to_bot_api(ingest_result)

            return {
                "folder_id": folder_id,
                "ingestion_result": ingest_result,
                "api_result": api_result,
                "job_parameters": {
                    "metadata": metadata,
                    "force_update": force_update,
                    "file_types": file_types,
                },
            }

        except Exception as e:
            logger.error(f"Error in Google Drive ingest: {str(e)}")
            raise

    async def _run_ingest_process(
        self,
        folder_id: str,
        metadata: dict[str, Any],
        force_update: bool,
        file_types: list[str],
    ) -> dict[str, Any]:
        """Run the actual document ingestion process."""
        try:
            # Get the project root directory (assuming tasks is a subdirectory)
            project_root = Path(__file__).parent.parent.parent
            ingest_path = project_root / "ingest"

            # Check if ingest directory exists
            if not ingest_path.exists():
                raise RuntimeError(f"Ingest directory not found: {ingest_path}")

            # Build command
            cmd = [
                sys.executable,
                str(ingest_path / "main.py"),
                "--folder-id",
                folder_id,
            ]

            # Add metadata if provided
            if metadata:
                cmd.extend(["--metadata", str(metadata)])

            # Add force update flag
            if force_update:
                cmd.append("--force-update")

            # Add file types filter
            if file_types:
                cmd.extend(["--file-types", ",".join(file_types)])

            logger.info(f"Running ingest command: {' '.join(cmd)}")

            # Run the ingestion process
            result = subprocess.run(
                cmd,
                check=False, cwd=str(ingest_path),
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )

            if result.returncode == 0:
                logger.info("Ingestion process completed successfully")
                return {
                    "status": "success",
                    "return_code": result.returncode,
                    "stdout": result.stdout[-1000:],  # Last 1000 chars
                    "stderr": result.stderr[-1000:] if result.stderr else "",
                }
            else:
                logger.error(
                    f"Ingestion process failed with return code: {result.returncode}"
                )
                return {
                    "status": "error",
                    "return_code": result.returncode,
                    "stdout": result.stdout[-1000:],
                    "stderr": result.stderr[-1000:] if result.stderr else "",
                }

        except subprocess.TimeoutExpired:
            logger.error("Ingestion process timed out")
            return {
                "status": "error",
                "error": "Process timed out after 1 hour",
            }
        except Exception as e:
            logger.error(f"Error running ingestion process: {str(e)}")
            raise

    async def _send_results_to_bot_api(
        self, ingest_result: dict[str, Any]
    ) -> dict[str, Any]:
        """Send ingestion results to the main bot API."""
        if not self.settings.slack_bot_api_url:
            logger.warning(
                "No bot API URL configured, results will not be sent to main bot"
            )
            return {"message": "No API endpoint configured"}

        try:
            # Prepare API request
            api_url = f"{self.settings.slack_bot_api_url}/api/ingest/completed"
            headers = {"Content-Type": "application/json"}

            if self.settings.slack_bot_api_key:
                headers["Authorization"] = f"Bearer {self.settings.slack_bot_api_key}"

            payload = {
                "job_id": self.job_id,
                "job_type": "google_drive_ingest",
                "folder_id": self.params["folder_id"],
                "result": ingest_result,
                "metadata": self.params.get("metadata", {}),
            }

            response = requests.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                logger.info("Successfully sent ingestion results to bot API")
                return {
                    "status": "success",
                    "api_response": response.json(),
                }
            else:
                logger.error(
                    f"API request failed: {response.status_code} - {response.text}"
                )
                return {
                    "status": "error",
                    "api_status_code": response.status_code,
                    "api_response": response.text,
                }

        except requests.RequestException as e:
            logger.error(f"Error sending results to bot API: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Unexpected error in API communication: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
            }
