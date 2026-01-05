/**
 * InsightMesh routes for agent list and conversation metadata.
 *
 * Provides:
 * - GET /agents - List available agents from agent-service (respects permissions)
 * - PATCH /conversations/:id/metadata - Update conversation metadata
 *
 * Services:
 * - Agent list: agent-service (discovery with permissions)
 * - Message routing: RAG service (receives X-Conversation-Metadata header)
 */

const express = require('express');
const router = express.Router();
const axios = require('axios');
const { logger } = require('@librechat/data-schemas');
const { getConversation, updateConversation } = require('~/models/Conversation');

// Service URLs from environment - fail fast if not configured
const AGENT_SERVICE_URL = process.env.AGENT_SERVICE_URL;
const LIBRECHAT_SERVICE_TOKEN = process.env.LIBRECHAT_SERVICE_TOKEN;

if (!AGENT_SERVICE_URL) {
  throw new Error('AGENT_SERVICE_URL environment variable is required');
}
if (!LIBRECHAT_SERVICE_TOKEN) {
  throw new Error('LIBRECHAT_SERVICE_TOKEN environment variable is required');
}

/**
 * GET /insightmesh/agents
 *
 * Fetch available agents from agent-service for sidebar display.
 * Agent service respects permissions and visibility rules.
 * Research agent is filtered out (accessed via deep search toggle).
 */
router.get('/agents', async (req, res) => {
  try {
    logger.info('[InsightMesh] Fetching agent list from agent-service');

    const response = await axios.get(`${AGENT_SERVICE_URL}/api/agents`, {
      headers: {
        'Authorization': `Bearer ${LIBRECHAT_SERVICE_TOKEN}`,
      },
      timeout: 5000,
    });

    // Filter out research agent (accessed via deep search toggle)
    const allAgents = response.data.agents || response.data || [];
    const agents = allAgents.filter(agent => agent.name !== 'research');

    logger.info(`[InsightMesh] Retrieved ${agents.length} agents (excluded research)`);

    res.json({ agents });
  } catch (error) {
    logger.error('[InsightMesh] Failed to fetch agents:', error.message);
    res.status(500).json({
      error: 'Failed to fetch agents',
      message: error.message,
    });
  }
});

/**
 * PATCH /insightmesh/conversations/:id/metadata
 *
 * Update conversation metadata for deep search and agent selection.
 *
 * Body: {
 *   deepSearchEnabled: boolean,
 *   researchDepth: "quick" | "standard" | "deep" | "exhaustive",
 *   selectedAgent: string | null
 * }
 */
router.patch('/conversations/:id/metadata', async (req, res) => {
  try {
    const { id } = req.params;
    const { deepSearchEnabled, researchDepth, selectedAgent } = req.body;

    logger.info(
      `[InsightMesh] Updating metadata for conversation ${id}: ` +
      `deepSearch=${deepSearchEnabled}, depth=${researchDepth}, agent=${selectedAgent}`
    );

    // Validate conversation exists
    const conversation = await getConversation({ conversationId: id });
    if (!conversation) {
      logger.warn(`[InsightMesh] Conversation not found: ${id}`);
      return res.status(404).json({ error: 'Conversation not found' });
    }

    // Build metadata update
    const metadata = conversation.metadata || {};
    metadata.insightmesh = {
      deepSearchEnabled: deepSearchEnabled !== undefined ? deepSearchEnabled : false,
      researchDepth: researchDepth || 'deep',
      selectedAgent: selectedAgent || null,
    };

    // Update conversation
    await updateConversation(
      { conversationId: id },
      { metadata }
    );

    logger.info(`[InsightMesh] Updated conversation ${id} metadata successfully`);

    res.json({
      success: true,
      metadata: metadata.insightmesh,
    });
  } catch (error) {
    logger.error('[InsightMesh] Failed to update conversation metadata:', error);
    res.status(500).json({
      error: 'Failed to update metadata',
      message: error.message,
    });
  }
});

module.exports = router;
