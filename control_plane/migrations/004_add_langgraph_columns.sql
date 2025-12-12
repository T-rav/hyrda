-- Migration: Add LangGraph Cloud columns to agent_metadata
-- Description: Adds langgraph_assistant_id and langgraph_url columns for cloud mode deployment
-- Date: 2025-12-12

-- Add langgraph_assistant_id column (LangGraph Cloud assistant ID)
ALTER TABLE agent_metadata
ADD COLUMN langgraph_assistant_id VARCHAR(255) DEFAULT NULL
AFTER aliases;

-- Add langgraph_url column (LangGraph Cloud deployment URL)
ALTER TABLE agent_metadata
ADD COLUMN langgraph_url VARCHAR(512) DEFAULT NULL
AFTER langgraph_assistant_id;

-- Add index for faster lookups by assistant_id
CREATE INDEX idx_langgraph_assistant_id
ON agent_metadata(langgraph_assistant_id);
