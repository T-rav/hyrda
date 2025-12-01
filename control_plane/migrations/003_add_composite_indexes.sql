-- Migration: Add composite indexes for better query performance
-- Date: 2025-12-01
-- Description: Adds composite indexes to frequently joined tables

-- UserGroup composite indexes
-- Used when filtering by both user and group (common in permission checks)
CREATE INDEX IF NOT EXISTS idx_user_groups_user_group
ON user_groups(slack_user_id, group_name);

-- Ensure uniqueness of user-group pairs
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_groups_user_group
ON user_groups(slack_user_id, group_name);

-- AgentGroupPermission composite indexes
-- Used when filtering by both agent and group (common in access checks)
CREATE INDEX IF NOT EXISTS idx_agent_group_permissions_agent_group
ON agent_group_permissions(agent_name, group_name);

-- Ensure uniqueness of agent-group permission pairs
CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_group_permissions_agent_group
ON agent_group_permissions(agent_name, group_name);

-- AgentPermission composite indexes (if table exists)
-- Used when filtering by both agent and user
CREATE INDEX IF NOT EXISTS idx_agent_permissions_agent_user
ON agent_permissions(agent_name, slack_user_id);

-- Ensure uniqueness of agent-user permission pairs
CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_permissions_agent_user
ON agent_permissions(agent_name, slack_user_id);

-- Benefits:
-- - Faster JOIN operations on permission tables
-- - Prevents duplicate permission entries
-- - Improves query performance for common access check patterns
-- - Supports efficient lookups in both directions

-- Query patterns optimized:
-- SELECT * FROM user_groups WHERE slack_user_id = ? AND group_name = ?
-- SELECT * FROM agent_group_permissions WHERE agent_name = ? AND group_name = ?
-- JOIN user_groups ON (slack_user_id, group_name)

-- Rollback (if needed):
-- DROP INDEX IF EXISTS idx_user_groups_user_group;
-- DROP INDEX IF EXISTS uq_user_groups_user_group;
-- DROP INDEX IF EXISTS idx_agent_group_permissions_agent_group;
-- DROP INDEX IF EXISTS uq_agent_group_permissions_agent_group;
-- DROP INDEX IF EXISTS idx_agent_permissions_agent_user;
-- DROP INDEX IF EXISTS uq_agent_permissions_agent_user;
