"""Rename oauth_credentials to task_credentials

Revision ID: 006_rename_to_task_creds
Revises: 005_add_oauth_credentials
Create Date: 2026-02-12

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "006_rename_to_task_creds"
down_revision = "005_add_oauth_credentials"
branch_labels = None
depends_on = None


def upgrade():
    """Rename oauth_credentials table to task_credentials (idempotent)."""
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    # Only rename if oauth_credentials exists and task_credentials doesn't
    if "oauth_credentials" in tables and "task_credentials" not in tables:
        op.rename_table("oauth_credentials", "task_credentials")
        op.drop_index("idx_oauth_provider", table_name="task_credentials")
        op.create_index(
            "idx_task_credentials_provider", "task_credentials", ["provider"]
        )
    elif "task_credentials" in tables:
        # Table already renamed, ensure index is correct
        indexes = [idx["name"] for idx in inspector.get_indexes("task_credentials")]
        if "idx_oauth_provider" in indexes:
            op.drop_index("idx_oauth_provider", table_name="task_credentials")
        if "idx_task_credentials_provider" not in indexes:
            op.create_index(
                "idx_task_credentials_provider", "task_credentials", ["provider"]
            )


def downgrade():
    """Rename task_credentials back to oauth_credentials."""
    op.drop_index("idx_task_credentials_provider", table_name="task_credentials")
    op.create_index("idx_oauth_provider", "task_credentials", ["provider"])
    op.rename_table("task_credentials", "oauth_credentials")
