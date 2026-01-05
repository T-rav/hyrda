/**
 * InsightMesh middleware for injecting conversation metadata into RAG service requests.
 *
 * This middleware:
 * 1. Extracts conversation metadata (deep search, agent selection) from MongoDB
 * 2. Adds X-Conversation-Metadata header for RAG service routing
 * 3. Enables deep research mode and agent selection features in LibreChat UI
 */

const { logger } = require('@librechat/data-schemas');
const { getConversation } = require('~/models/Conversation');

/**
 * Middleware to inject InsightMesh conversation metadata into RAG requests.
 *
 * Adds X-Conversation-Metadata header with:
 * - deepSearchEnabled: boolean
 * - researchDepth: "quick" | "standard" | "deep" | "exhaustive"
 * - selectedAgent: string | null
 *
 * @param {Object} req - Express request
 * @param {Object} res - Express response
 * @param {Function} next - Next middleware
 */
async function insightMeshMiddleware(req, res, next) {
  try {
    // Only process chat completion requests going to RAG service
    if (!req.path.includes('/chat/completions')) {
      return next();
    }

    // Extract conversation ID from request body
    const conversationId = req.body?.conversationId || req.body?.conversation_id;

    if (!conversationId) {
      // No conversation ID - this is likely a new conversation
      logger.debug('[InsightMesh] No conversation ID - skipping metadata injection');
      return next();
    }

    // Load conversation from MongoDB
    const conversation = await getConversation({ conversationId });

    if (!conversation) {
      logger.debug(`[InsightMesh] Conversation not found: ${conversationId}`);
      return next();
    }

    // Extract InsightMesh metadata
    const insightMeshMetadata = conversation.metadata?.insightmesh;

    if (!insightMeshMetadata) {
      // No InsightMesh metadata - conversation created before feature was added
      logger.debug(`[InsightMesh] No metadata for conversation: ${conversationId}`);
      return next();
    }

    // Build metadata header for RAG service
    const metadata = {
      deepSearchEnabled: insightMeshMetadata.deepSearchEnabled || false,
      researchDepth: insightMeshMetadata.researchDepth || 'deep',
      selectedAgent: insightMeshMetadata.selectedAgent || null,
    };

    // Add header for RAG service to consume
    req.headers['x-conversation-metadata'] = JSON.stringify(metadata);

    logger.info(
      `[InsightMesh] Injected metadata for conversation ${conversationId}: ` +
      `deepSearch=${metadata.deepSearchEnabled}, agent=${metadata.selectedAgent}, depth=${metadata.researchDepth}`
    );

    next();
  } catch (error) {
    // Log error but don't block request - graceful degradation
    logger.error('[InsightMesh] Middleware error:', error);
    next();
  }
}

module.exports = insightMeshMiddleware;
