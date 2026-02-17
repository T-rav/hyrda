"""create_goal_bot_tables

Create tables for Goal Bots feature:
- goal_bots: Bot definitions with schedules
- goal_bot_runs: Execution history
- goal_bot_logs: Milestone logs
- goal_bot_state: Persistent state between runs

Revision ID: create_goal_bot_tables
Revises: add_missing_agent_columns
Create Date: 2026-02-16 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "create_goal_bot_tables"
down_revision = "add_missing_agent_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Goal bot definitions
    op.create_table(
        "goal_bots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bot_id", sa.String(36), nullable=False, unique=True),  # UUID
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "agent_name", sa.String(50), nullable=False
        ),  # Agent to use for execution
        sa.Column("goal_prompt", sa.Text(), nullable=False),  # The goal/objective
        sa.Column(
            "schedule_type",
            sa.Enum("cron", "interval", name="schedule_type_enum"),
            nullable=False,
        ),
        sa.Column("schedule_config", sa.Text(), nullable=False),  # JSON config
        sa.Column(
            "max_runtime_seconds", sa.Integer(), nullable=False, server_default="3600"
        ),
        sa.Column("max_iterations", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_paused", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(50), nullable=True),  # User who created
        sa.Column(
            "notification_channel", sa.String(100), nullable=True
        ),  # Slack channel for notifications
        sa.Column("tools_config", sa.Text(), nullable=True),  # JSON array of tool names
    )
    op.create_index("ix_goal_bots_bot_id", "goal_bots", ["bot_id"], unique=True)
    op.create_index("ix_goal_bots_name", "goal_bots", ["name"])
    op.create_index("ix_goal_bots_next_run_at", "goal_bots", ["next_run_at"])
    op.create_index("ix_goal_bots_is_enabled", "goal_bots", ["is_enabled"])

    # Goal bot execution history
    op.create_table(
        "goal_bot_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), nullable=False, unique=True),  # UUID
        sa.Column("bot_id", sa.String(36), nullable=False),  # FK to goal_bots.bot_id
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "completed",
                "failed",
                "cancelled",
                "timeout",
                name="run_status_enum",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("iterations_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "final_outcome", sa.Text(), nullable=True
        ),  # Summary of what was accomplished
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_traceback", sa.Text(), nullable=True),
        sa.Column(
            "triggered_by",
            sa.Enum("scheduler", "manual", "api", name="triggered_by_enum"),
            nullable=False,
            server_default="scheduler",
        ),
        sa.Column("triggered_by_user", sa.String(50), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["bot_id"],
            ["goal_bots.bot_id"],
            name="fk_goal_bot_runs_bot_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_goal_bot_runs_run_id", "goal_bot_runs", ["run_id"], unique=True)
    op.create_index("ix_goal_bot_runs_bot_id", "goal_bot_runs", ["bot_id"])
    op.create_index("ix_goal_bot_runs_status", "goal_bot_runs", ["status"])
    op.create_index("ix_goal_bot_runs_started_at", "goal_bot_runs", ["started_at"])

    # Goal bot milestone logs
    op.create_table(
        "goal_bot_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id", sa.String(36), nullable=False
        ),  # FK to goal_bot_runs.run_id
        sa.Column(
            "milestone_type",
            sa.Enum(
                "plan_created",
                "plan_updated",
                "action_taken",
                "progress_check",
                "goal_achieved",
                "goal_blocked",
                "error",
                "info",
                name="milestone_type_enum",
            ),
            nullable=False,
        ),
        sa.Column("milestone_name", sa.String(200), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),  # JSON details
        sa.Column(
            "logged_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("iteration_number", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["goal_bot_runs.run_id"],
            name="fk_goal_bot_logs_run_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_goal_bot_logs_run_id", "goal_bot_logs", ["run_id"])
    op.create_index(
        "ix_goal_bot_logs_milestone_type", "goal_bot_logs", ["milestone_type"]
    )
    op.create_index("ix_goal_bot_logs_logged_at", "goal_bot_logs", ["logged_at"])

    # Goal bot persistent state
    op.create_table(
        "goal_bot_state",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "bot_id", sa.String(36), nullable=False, unique=True
        ),  # FK to goal_bots.bot_id
        sa.Column("state_data", sa.Text(), nullable=False),  # JSON state
        sa.Column("state_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "last_updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column(
            "last_run_id", sa.String(36), nullable=True
        ),  # Last run that updated state
        sa.ForeignKeyConstraint(
            ["bot_id"],
            ["goal_bots.bot_id"],
            name="fk_goal_bot_state_bot_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_goal_bot_state_bot_id", "goal_bot_state", ["bot_id"], unique=True
    )


def downgrade() -> None:
    # Drop in reverse order due to foreign keys
    op.drop_index("ix_goal_bot_state_bot_id", table_name="goal_bot_state")
    op.drop_table("goal_bot_state")

    op.drop_index("ix_goal_bot_logs_logged_at", table_name="goal_bot_logs")
    op.drop_index("ix_goal_bot_logs_milestone_type", table_name="goal_bot_logs")
    op.drop_index("ix_goal_bot_logs_run_id", table_name="goal_bot_logs")
    op.drop_table("goal_bot_logs")

    op.drop_index("ix_goal_bot_runs_started_at", table_name="goal_bot_runs")
    op.drop_index("ix_goal_bot_runs_status", table_name="goal_bot_runs")
    op.drop_index("ix_goal_bot_runs_bot_id", table_name="goal_bot_runs")
    op.drop_index("ix_goal_bot_runs_run_id", table_name="goal_bot_runs")
    op.drop_table("goal_bot_runs")

    op.drop_index("ix_goal_bots_is_enabled", table_name="goal_bots")
    op.drop_index("ix_goal_bots_next_run_at", table_name="goal_bots")
    op.drop_index("ix_goal_bots_name", table_name="goal_bots")
    op.drop_index("ix_goal_bots_bot_id", table_name="goal_bots")
    op.drop_table("goal_bots")

    # Drop enums (MySQL doesn't use separate enum types, but PostgreSQL does)
    op.execute("DROP TYPE IF EXISTS schedule_type_enum")
    op.execute("DROP TYPE IF EXISTS run_status_enum")
    op.execute("DROP TYPE IF EXISTS triggered_by_enum")
    op.execute("DROP TYPE IF EXISTS milestone_type_enum")
