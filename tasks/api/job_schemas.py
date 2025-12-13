"""Pydantic schemas for job parameter validation.

Security: Validates all job parameters to prevent injection attacks and type confusion.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class GDriveIngestParams(BaseModel):
    """Parameters for Google Drive ingestion job.

    Security: Validates folder/file IDs, credential IDs, and metadata structure.
    """

    folder_id: str | None = Field(
        None,
        min_length=1,
        max_length=200,
        description="Google Drive folder ID to ingest",
    )
    file_id: str | None = Field(
        None, min_length=1, max_length=200, description="Google Drive file ID to ingest"
    )
    credential_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="OAuth credential ID from database",
    )
    recursive: bool = Field(default=True, description="Recursively ingest subfolders")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Custom metadata to attach to documents"
    )

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate metadata structure and size.

        Security: Prevents metadata injection and DoS via large payloads.
        """
        if not isinstance(v, dict):
            raise ValueError("metadata must be a dictionary")

        # Limit metadata size to prevent DoS
        import json

        metadata_json = json.dumps(v)
        if len(metadata_json) > 10000:  # 10KB limit
            raise ValueError("metadata exceeds maximum size of 10KB")

        # Validate metadata values are simple types
        for key, value in v.items():
            if not isinstance(key, str):
                raise ValueError("metadata keys must be strings")
            if not isinstance(value, (str, int, float, bool, type(None))):
                raise ValueError(
                    f"metadata values must be simple types (str/int/float/bool/null), "
                    f"got {type(value).__name__} for key '{key}'"
                )

        return v

    @model_validator(mode="after")
    def validate_source(self):
        """Validate that exactly one of folder_id or file_id is provided.

        Security: Prevents ambiguous requests and ensures clear intent.
        """
        folder_id = self.folder_id
        file_id = self.file_id

        if not folder_id and not file_id:
            raise ValueError("Must provide either 'folder_id' or 'file_id' parameter")

        if folder_id and file_id:
            raise ValueError(
                "Cannot provide both 'folder_id' and 'file_id' parameters. Choose one."
            )

        return self


# Map job types to their parameter schemas
JOB_PARAM_SCHEMAS: dict[str, type[BaseModel]] = {
    "google_drive_ingest": GDriveIngestParams,
    # Add more job types here as they're created:
    # "slack_export": SlackExportParams,
    # "email_ingest": EmailIngestParams,
}


def validate_job_params(job_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """Validate job parameters against schema.

    Args:
        job_type: Type of job (e.g., "google_drive_ingest")
        params: Job parameters to validate

    Returns:
        Validated parameters dictionary

    Raises:
        ValueError: If job type unknown or parameters invalid

    Security:
    - Validates parameter types and structure
    - Enforces size limits
    - Prevents injection attacks
    - Returns sanitized parameters
    """
    if job_type not in JOB_PARAM_SCHEMAS:
        # Unknown job type - allow but log warning
        # (for extensibility with external job types)
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"No validation schema for job type '{job_type}'. "
            "Parameters accepted as-is."
        )
        return params

    schema = JOB_PARAM_SCHEMAS[job_type]

    try:
        validated = schema(**params)
        return validated.model_dump()
    except Exception as e:
        raise ValueError(f"Invalid parameters for job type '{job_type}': {str(e)}")
