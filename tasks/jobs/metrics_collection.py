"""Metrics collection job for gathering system and usage metrics."""

import logging
from datetime import datetime
from typing import Any

import requests

from config.settings import TasksSettings

from .base_job import BaseJob

logger = logging.getLogger(__name__)


class MetricsCollectionJob(BaseJob):
    """Job to collect and aggregate system metrics."""

    JOB_NAME = "Metrics Collection"
    JOB_DESCRIPTION = "Collect system metrics from various sources and aggregate them"
    REQUIRED_PARAMS = []
    OPTIONAL_PARAMS = ["metric_types", "time_range_hours", "aggregate_level"]

    def __init__(self, settings: TasksSettings, **kwargs: Any):
        """Initialize the metrics collection job."""
        super().__init__(settings, **kwargs)
        self.validate_params()

    def validate_params(self) -> bool:
        """Validate job parameters."""
        super().validate_params()
        return True

    async def _execute_job(self) -> dict[str, Any]:
        """Execute the metrics collection job."""
        metric_types = self.params.get(
            "metric_types", ["usage", "performance", "errors"]
        )
        time_range_hours = self.params.get("time_range_hours", 24)
        aggregate_level = self.params.get("aggregate_level", "hourly")

        logger.info(f"Starting metrics collection for types: {metric_types}")

        try:
            metrics_data = {}

            # Collect different types of metrics
            if "usage" in metric_types:
                metrics_data["usage"] = await self._collect_usage_metrics(
                    time_range_hours
                )

            if "performance" in metric_types:
                metrics_data["performance"] = await self._collect_performance_metrics(
                    time_range_hours
                )

            if "errors" in metric_types:
                metrics_data["errors"] = await self._collect_error_metrics(
                    time_range_hours
                )

            if "slack" in metric_types:
                metrics_data["slack"] = await self._collect_slack_metrics(
                    time_range_hours
                )

            # Aggregate metrics
            aggregated_metrics = self._aggregate_metrics(metrics_data, aggregate_level)

            # Send metrics to external API if configured
            external_result = await self._send_metrics_to_external_api(
                aggregated_metrics
            )

            # Send metrics to main bot API
            bot_result = await self._send_metrics_to_bot_api(aggregated_metrics)

            # Calculate standardized metrics
            total_data_points = sum(
                len(data) if isinstance(data, list) else 1
                for data in metrics_data.values()
            )

            # Determine success based on whether we collected any data
            success_count = len(
                [t for t in metric_types if t in metrics_data and metrics_data[t]]
            )
            failed_count = len(metric_types) - success_count

            return {
                # Standardized fields for task run tracking
                "records_processed": len(
                    metric_types
                ),  # Number of metric types requested
                "records_success": success_count,  # Number of metric types successfully collected
                "records_failed": failed_count,  # Number of metric types that failed
                # Job-specific details for debugging/logging
                "collected_metrics": metrics_data,
                "aggregated_metrics": aggregated_metrics,
                "external_api_result": external_result,
                "bot_api_result": bot_result,
                "collection_summary": {
                    "metric_types": metric_types,
                    "time_range_hours": time_range_hours,
                    "aggregate_level": aggregate_level,
                    "total_data_points": total_data_points,
                },
            }

        except Exception as e:
            logger.error(f"Error in metrics collection: {str(e)}")
            raise

    async def _collect_usage_metrics(self, time_range_hours: int) -> dict[str, Any]:
        """Collect usage metrics from the main bot API."""
        try:
            if not self.settings.slack_bot_api_url:
                return {"error": "No bot API URL configured"}

            api_url = f"{self.settings.slack_bot_api_url}/api/metrics/usage"
            headers = {"Content-Type": "application/json"}

            if self.settings.slack_bot_api_key:
                headers["Authorization"] = f"Bearer {self.settings.slack_bot_api_key}"

            params = {
                "hours": time_range_hours,
                "include_details": True,
            }

            response = requests.get(
                api_url,
                headers=headers,
                params=params,
                timeout=30,
            )

            if response.status_code == 200:
                usage_data = response.json()
                logger.info(
                    f"Collected usage metrics: {len(usage_data.get('data', []))} data points"
                )
                return usage_data
            else:
                logger.warning(
                    f"Failed to collect usage metrics: {response.status_code}"
                )
                return {"error": f"API returned {response.status_code}"}

        except requests.RequestException as e:
            logger.error(f"Error collecting usage metrics: {str(e)}")
            return {"error": str(e)}

    async def _collect_performance_metrics(
        self, time_range_hours: int
    ) -> dict[str, Any]:
        """Collect performance metrics from the main bot API."""
        try:
            if not self.settings.slack_bot_api_url:
                return {"error": "No bot API URL configured"}

            api_url = f"{self.settings.slack_bot_api_url}/api/metrics/performance"
            headers = {"Content-Type": "application/json"}

            if self.settings.slack_bot_api_key:
                headers["Authorization"] = f"Bearer {self.settings.slack_bot_api_key}"

            params = {
                "hours": time_range_hours,
                "include_system": True,
            }

            response = requests.get(
                api_url,
                headers=headers,
                params=params,
                timeout=30,
            )

            if response.status_code == 200:
                perf_data = response.json()
                logger.info(
                    f"Collected performance metrics: {len(perf_data.get('data', []))} data points"
                )
                return perf_data
            else:
                logger.warning(
                    f"Failed to collect performance metrics: {response.status_code}"
                )
                return {"error": f"API returned {response.status_code}"}

        except requests.RequestException as e:
            logger.error(f"Error collecting performance metrics: {str(e)}")
            return {"error": str(e)}

    async def _collect_error_metrics(self, time_range_hours: int) -> dict[str, Any]:
        """Collect error metrics from the main bot API."""
        try:
            if not self.settings.slack_bot_api_url:
                return {"error": "No bot API URL configured"}

            api_url = f"{self.settings.slack_bot_api_url}/api/metrics/errors"
            headers = {"Content-Type": "application/json"}

            if self.settings.slack_bot_api_key:
                headers["Authorization"] = f"Bearer {self.settings.slack_bot_api_key}"

            params = {
                "hours": time_range_hours,
                "severity": "warning,error,critical",
            }

            response = requests.get(
                api_url,
                headers=headers,
                params=params,
                timeout=30,
            )

            if response.status_code == 200:
                error_data = response.json()
                logger.info(
                    f"Collected error metrics: {len(error_data.get('data', []))} data points"
                )
                return error_data
            else:
                logger.warning(
                    f"Failed to collect error metrics: {response.status_code}"
                )
                return {"error": f"API returned {response.status_code}"}

        except requests.RequestException as e:
            logger.error(f"Error collecting error metrics: {str(e)}")
            return {"error": str(e)}

    async def _collect_slack_metrics(self, time_range_hours: int) -> dict[str, Any]:
        """Collect Slack-specific metrics."""
        try:
            # This would collect metrics like message counts, user activity, etc.
            # For now, return mock data structure
            return {
                "message_count": 150,
                "active_users": 25,
                "channels_active": 8,
                "response_time_avg_seconds": 2.3,
                "success_rate_percent": 98.5,
                "time_range_hours": time_range_hours,
            }

        except Exception as e:
            logger.error(f"Error collecting Slack metrics: {str(e)}")
            return {"error": str(e)}

    def _aggregate_metrics(
        self, metrics_data: dict[str, Any], level: str
    ) -> dict[str, Any]:
        """Aggregate collected metrics based on the specified level."""
        aggregated = {
            "aggregation_level": level,
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {},
        }

        for metric_type, data in metrics_data.items():
            if isinstance(data, dict) and "error" not in data:
                # Simple aggregation - in a real implementation, this would be more sophisticated
                aggregated["summary"][metric_type] = {
                    "status": "success",
                    "data_points": len(data.get("data", [])) if "data" in data else 1,
                    "latest_value": data,
                }
            else:
                aggregated["summary"][metric_type] = {
                    "status": "error",
                    "error": data.get("error", "Unknown error"),
                }

        return aggregated

    async def _send_metrics_to_external_api(
        self, metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """Send metrics to external metrics API (e.g., metrics.ai)."""
        if not self.settings.metrics_api_url:
            return {"message": "No external metrics API configured"}

        try:
            headers = {"Content-Type": "application/json"}

            if self.settings.metrics_api_key:
                headers["Authorization"] = f"Bearer {self.settings.metrics_api_key}"

            payload = {
                "job_id": self.job_id,
                "source": "ai-slack-bot-tasks",
                "timestamp": datetime.utcnow().isoformat(),
                "metrics": metrics,
            }

            response = requests.post(
                self.settings.metrics_api_url,
                json=payload,
                headers=headers,
                timeout=30,
            )

            if response.status_code in [200, 201, 202]:
                logger.info("Successfully sent metrics to external API")
                return {
                    "status": "success",
                    "api_response": response.json() if response.text else {},
                }
            else:
                logger.error(f"External API request failed: {response.status_code}")
                return {
                    "status": "error",
                    "api_status_code": response.status_code,
                    "api_response": response.text,
                }

        except requests.RequestException as e:
            logger.error(f"Error sending metrics to external API: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def _send_metrics_to_bot_api(self, metrics: dict[str, Any]) -> dict[str, Any]:
        """Send aggregated metrics to the main bot API for storage."""
        if not self.settings.slack_bot_api_url:
            return {"message": "No bot API URL configured"}

        try:
            api_url = f"{self.settings.slack_bot_api_url}/api/metrics/store"
            headers = {"Content-Type": "application/json"}

            if self.settings.slack_bot_api_key:
                headers["Authorization"] = f"Bearer {self.settings.slack_bot_api_key}"

            payload = {
                "job_id": self.job_id,
                "job_type": "metrics_collection",
                "metrics": metrics,
                "collection_time": datetime.utcnow().isoformat(),
            }

            response = requests.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                logger.info("Successfully sent metrics to bot API")
                return {
                    "status": "success",
                    "api_response": response.json(),
                }
            else:
                logger.error(f"Bot API request failed: {response.status_code}")
                return {
                    "status": "error",
                    "api_status_code": response.status_code,
                    "api_response": response.text,
                }

        except requests.RequestException as e:
            logger.error(f"Error sending metrics to bot API: {str(e)}")
            return {"status": "error", "error": str(e)}
