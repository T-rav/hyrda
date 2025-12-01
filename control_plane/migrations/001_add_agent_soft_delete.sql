-- Migration: Add soft delete support for agents
-- Date: 2025-12-01
-- Description: Adds is_deleted column to agent_metadata table to support soft deletion

-- Add is_deleted column (default FALSE for existing agents)
ALTER TABLE agent_metadata
ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE;

-- Add index for common query (list non-deleted agents)
CREATE INDEX IF NOT EXISTS idx_agent_metadata_is_deleted
ON agent_metadata(is_deleted);

-- Remove unique constraint on agent_name if it exists
-- This allows reusing agent names after soft deletion
-- Note: Uniqueness is now enforced in application layer for non-deleted agents

-- For PostgreSQL:
-- DROP INDEX IF EXISTS agent_metadata_agent_name_key;

-- For MySQL:
-- ALTER TABLE agent_metadata DROP INDEX agent_name;

-- For SQLite (if used in development):
-- SQLite doesn't support DROP CONSTRAINT, would need to recreate table
-- Not needed if starting fresh

-- Migration rollback (if needed):
-- ALTER TABLE agent_metadata DROP COLUMN is_deleted;
