"""
Initial migration: Create user_prompts table

This migration creates the user_prompts table for storing user-specific system prompts
with history tracking and current prompt identification.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from migrations.migration_manager import Migration


class CreateUserPromptsTable(Migration):
    """Migration to create the user_prompts table"""

    def __init__(self):
        super().__init__(version="001", name="Create user_prompts table")

    async def up(self, session: AsyncSession) -> None:
        """Create the user_prompts table"""
        await session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS user_prompts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(50) NOT NULL,
                prompt TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_current BOOLEAN NOT NULL DEFAULT true
            );
        """
            )
        )

        # Create index on user_id for performance
        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_user_prompts_user_id ON user_prompts(user_id);
        """
            )
        )

        # Create index on user_id + is_current for finding current prompt
        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_user_prompts_current ON user_prompts(user_id, is_current)
            WHERE is_current = true;
        """
            )
        )

    async def down(self, session: AsyncSession) -> None:
        """Drop the user_prompts table"""
        await session.execute(text("DROP TABLE IF EXISTS user_prompts CASCADE;"))
