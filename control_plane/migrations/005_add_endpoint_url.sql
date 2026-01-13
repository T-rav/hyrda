-- Migration: Add endpoint_url for generic agent invocation
-- Description: Adds endpoint_url column to support both embedded and cloud agents via unified HTTP interface
-- Date: 2025-12-12

ALTER TABLE agent_metadata
ADD COLUMN endpoint_url VARCHAR(512) DEFAULT NULL
AFTER langgraph_url;

CREATE INDEX idx_endpoint_url
ON agent_metadata(endpoint_url);

-- Update comment for clarity
ALTER TABLE agent_metadata
MODIFY COLUMN endpoint_url VARCHAR(512) DEFAULT NULL
COMMENT 'HTTP endpoint for agent invocation (embedded: http://agent-service:8000/api/agents/X/invoke, cloud: https://api.langraph.com/...)';
