"""Goal Bot Scheduler - Checks for due goal bots and triggers execution."""

import logging
import os
from typing import Any

import httpx

from config.settings import TasksSettings

from .base_job import BaseJob

logger = logging.getLogger(__name__)


class GoalBotSchedulerJob(BaseJob):
    """Job that checks for due goal bots and triggers their execution.

    This job should run every 5 minutes to check for goal bots that are
    due to run based on their schedule configuration.
    """

    JOB_NAME = "Goal Bot Scheduler"
    JOB_DESCRIPTION = "Checks for due goal bots and triggers execution"
    REQUIRED_PARAMS: list[str] = []
    OPTIONAL_PARAMS: list[str] = []

    def __init__(self, settings: TasksSettings, **kwargs: Any):
        """Initialize the goal bot scheduler job."""
        super().__init__(settings, **kwargs)
        self.control_plane_url = os.getenv(
            "CONTROL_PLANE_URL", "http://control-plane:6001"
        )
        self.agent_service_url = os.getenv(
            "AGENT_SERVICE_URL", "http://agent-service:8000"
        )
        self.service_api_key = os.getenv("SERVICE_API_KEY", "")

    async def _execute_job(self) -> dict[str, Any]:
        """Check for due goal bots and trigger execution."""
        results = {
            "due_bots_found": 0,
            "runs_created": 0,
            "runs_started": 0,
            "errors": [],
            "records_processed": 0,
            "records_success": 0,
            "records_failed": 0,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Get due goal bots from control plane
            try:
                headers = {}
                if self.service_api_key:
                    headers["X-Service-API-Key"] = self.service_api_key

                response = await client.get(
                    f"{self.control_plane_url}/api/goal-bots/due",
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                due_bots = data.get("due_bots", [])
                results["due_bots_found"] = len(due_bots)
                results["records_processed"] = len(due_bots)

                logger.info(f"Found {len(due_bots)} due goal bots")

            except httpx.HTTPError as e:
                error_msg = f"Failed to fetch due goal bots: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                return results

            # Step 2: Create runs and trigger execution for each due bot
            for bot in due_bots:
                bot_id = bot.get("bot_id")
                bot_name = bot.get("name", bot_id)

                try:
                    # Create a scheduled run
                    response = await client.post(
                        f"{self.control_plane_url}/api/goal-bots/runs",
                        headers=headers,
                        json={"bot_id": bot_id},
                    )
                    response.raise_for_status()
                    run_data = response.json()

                    if not run_data.get("success"):
                        error = run_data.get("error", "Unknown error")
                        logger.warning(f"Could not create run for {bot_name}: {error}")
                        continue

                    run_id = run_data["run"]["run_id"]
                    results["runs_created"] += 1
                    logger.info(f"Created run {run_id} for goal bot '{bot_name}'")

                    # Start the run
                    response = await client.post(
                        f"{self.control_plane_url}/api/goal-bots/runs/{run_id}/start",
                        headers=headers,
                    )
                    response.raise_for_status()

                    # Trigger agent-service to execute the goal bot
                    # The agent-service will handle the actual execution
                    try:
                        agent_headers = {"X-Service-API-Key": self.service_api_key}
                        response = await client.post(
                            f"{self.agent_service_url}/api/goal-bots/{bot_id}/execute",
                            headers=agent_headers,
                            json={
                                "run_id": run_id,
                                "bot": bot,
                            },
                            timeout=10.0,  # Short timeout - just trigger, don't wait
                        )
                        # Don't raise for status - agent might take time to respond
                        if response.status_code < 400:
                            results["runs_started"] += 1
                            results["records_success"] += 1
                            logger.info(
                                f"Triggered execution for goal bot '{bot_name}' "
                                f"(run_id={run_id})"
                            )
                        else:
                            results["records_failed"] += 1
                            logger.warning(
                                f"Agent service returned {response.status_code} "
                                f"for goal bot '{bot_name}'"
                            )
                    except httpx.TimeoutException:
                        # Timeout is OK - agent might be processing
                        results["runs_started"] += 1
                        results["records_success"] += 1
                        logger.info(
                            f"Triggered execution for goal bot '{bot_name}' "
                            f"(run_id={run_id}, async)"
                        )
                    except httpx.HTTPError as e:
                        results["records_failed"] += 1
                        error_msg = f"Failed to trigger agent for '{bot_name}': {e}"
                        logger.error(error_msg)
                        results["errors"].append(error_msg)

                except httpx.HTTPError as e:
                    results["records_failed"] += 1
                    error_msg = f"Failed to create run for '{bot_name}': {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)

        logger.info(
            f"Goal bot scheduler completed: "
            f"{results['runs_created']} runs created, "
            f"{results['runs_started']} started"
        )

        return results
