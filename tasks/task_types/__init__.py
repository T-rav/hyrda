"""Type definitions for InsightMesh tasks service.

This module provides TypedDict classes to replace dict[str, Any] types
throughout the tasks codebase, improving type safety and IDE support.
"""

from typing import Any, TypedDict


class JobTypeInfo(TypedDict):
    """Information about a registered job type.

    Used by job registry to describe available job types.
    """

    type: str  # Job type identifier (e.g., "google_drive_ingestion")
    name: str  # Human-readable job name
    description: str  # Job description
    required_params: list[str]  # Required parameter names
    optional_params: list[str]  # Optional parameter names
    param_groups: list[dict[str, Any]]  # Parameter groupings for UI


class JobSchedule(TypedDict, total=False):
    """Job schedule configuration.

    Used for scheduled/recurring jobs.
    """

    trigger: str  # Trigger type: "cron", "interval", "date"
    hour: int  # Hour (0-23) for cron trigger
    minute: int  # Minute (0-59) for cron trigger
    day_of_week: str  # Day of week for cron trigger
    seconds: int  # Seconds for interval trigger
    minutes: int  # Minutes for interval trigger
    hours: int  # Hours for interval trigger
    run_date: str  # ISO datetime for date trigger
    timezone: str  # Timezone for schedule


class JobExecutionResult(TypedDict, total=False):
    """Result from job execution.

    Returned by job execute() methods.
    """

    # Standard fields returned by BaseJob.run()
    status: str  # Job status: "success" or "error"
    job_id: str  # Job ID
    job_name: str  # Job name
    start_time: str  # ISO datetime when job started
    execution_time_seconds: float  # Execution duration in seconds
    result: Any  # Result from job execute() method
    error_type: str  # Error type (e.g., "ValueError")
    error_context: dict[str, Any]  # Error context details

    # Fields from job execute() implementations
    success: bool  # Whether job succeeded
    message: str  # Success/error message
    records_processed: int  # Number of records processed
    records_success: int  # Number of successful records
    records_failed: int  # Number of failed records
    error: str  # Error message if failed
    details: dict[str, Any]  # Additional result details

    # Job-specific fields (examples from various jobs)
    total_users_fetched: int  # From slack_user_import
    filtered_users_count: int  # From slack_user_import
    new_users_count: int  # From slack_user_import
    updated_users_count: int  # From slack_user_import
    users_sample: list[Any]  # From slack_user_import
    processed_count: int  # From slack_user_import


class EmployeeProfile(TypedDict, total=False):
    """Employee profile from Portal API.

    Contains employee information from Metric.ai system.
    """

    metric_id: str  # Employee's Metric.ai ID
    name: str  # Full name
    email: str  # Email address
    title: str  # Job title
    department: str  # Department
    skills: list[str]  # List of skills
    allocations: list[dict[str, Any]]  # Project allocations
    blog_posts: list[dict[str, Any]]  # Blog posts
    profile_data: dict[str, Any]  # Additional profile data


class APIResponse(TypedDict, total=False):
    """Generic API response structure.

    Used for external API calls.
    """

    success: bool  # Whether API call succeeded
    data: dict[str, Any] | list[dict[str, Any]]  # Response data
    error: str  # Error message if failed
    status_code: int  # HTTP status code


class SlackUser(TypedDict, total=False):
    """Slack user data from Slack API.

    Contains user profile information from Slack.
    """

    id: str  # Slack user ID
    name: str  # Username
    real_name: str  # Full name
    email: str  # Email address
    profile: dict[str, Any]  # Full profile object
    is_bot: bool  # Whether user is a bot
    is_app_user: bool  # Whether user is an app
    deleted: bool  # Whether user is deleted
    is_restricted: bool  # Whether user is restricted
    is_ultra_restricted: bool  # Whether user is ultra restricted


# Export all types
__all__ = [
    "JobTypeInfo",
    "JobSchedule",
    "JobExecutionResult",
    "EmployeeProfile",
    "APIResponse",
    "SlackUser",
]
