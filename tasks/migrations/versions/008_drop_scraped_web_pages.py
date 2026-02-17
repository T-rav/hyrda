"""Drop scraped_web_pages table if it exists in task database

Revision ID: 008_drop_scraped_web_pages
Revises: 007_add_task_group
Create Date: 2026-02-17

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "008_drop_scraped_web_pages"
down_revision = "007_add_task_group"
branch_labels = None
depends_on = None


def upgrade():
    """Drop scraped_web_pages table if it exists (idempotent)."""
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    if "scraped_web_pages" in tables:
        op.drop_table("scraped_web_pages")


def downgrade():
    """No-op - table shouldn't have been in this database."""
    pass
