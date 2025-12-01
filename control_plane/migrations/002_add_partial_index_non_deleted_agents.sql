-- Migration: Add partial index for non-deleted agents
-- Date: 2025-12-01
-- Description: Optimizes queries that filter for active (non-deleted) agents

-- Drop the full index on is_deleted (covers all rows)
-- We'll replace it with a more efficient partial index
DROP INDEX IF EXISTS idx_agent_metadata_is_deleted;

-- Create partial index for non-deleted agents
-- This indexes only agent_name for rows where is_deleted = FALSE
-- Much more efficient for queries like: SELECT * FROM agent_metadata WHERE is_deleted = FALSE
-- Partial indexes are smaller and faster because they only index the rows we actually query
CREATE INDEX IF NOT EXISTS idx_agent_metadata_active_agents
ON agent_metadata(agent_name)
WHERE is_deleted = FALSE;

-- Note: PostgreSQL, MySQL 8.0.13+, and SQLite 3.8.0+ support partial indexes
-- For MySQL < 8.0.13, you may need to use a filtered index alternative or keep the full index

-- Benefits:
-- - Faster queries for list_agents() which filters by is_deleted = FALSE
-- - Smaller index size (only indexes active agents, not all rows)
-- - Better query planning for agent lookups

-- Rollback (if needed):
-- DROP INDEX IF EXISTS idx_agent_metadata_active_agents;
-- CREATE INDEX IF NOT EXISTS idx_agent_metadata_is_deleted ON agent_metadata(is_deleted);
