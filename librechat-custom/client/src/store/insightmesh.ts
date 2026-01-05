import { atom } from 'recoil';

export type ResearchDepth = 'quick' | 'standard' | 'deep' | 'exhaustive';

export interface InsightMeshMetadata {
  deepSearchEnabled: boolean;
  researchDepth: ResearchDepth;
  selectedAgent: string | null;
}

export interface Agent {
  name: string;
  description: string;
  aliases: string[];
  category?: string;
}

/**
 * Conversation-level InsightMesh metadata
 * - deepSearchEnabled: Routes all messages to research agent
 * - researchDepth: Level of research depth (quick, standard, deep, exhaustive)
 * - selectedAgent: Specific agent selected from sidebar
 */
const insightMeshMetadata = atom<InsightMeshMetadata>({
  key: 'insightMeshMetadata',
  default: {
    deepSearchEnabled: false,
    researchDepth: 'deep',
    selectedAgent: null,
  },
});

/**
 * List of available agents fetched from RAG service
 * Excludes research agent (accessed via deep search toggle)
 */
const availableAgents = atom<Agent[]>({
  key: 'availableAgents',
  default: [],
});

/**
 * Agent sidebar visibility state
 */
const agentSidebarOpen = atom<boolean>({
  key: 'agentSidebarOpen',
  default: false,
});

/**
 * Loading state for agent list fetch
 */
const agentsLoading = atom<boolean>({
  key: 'agentsLoading',
  default: false,
});

export default {
  insightMeshMetadata,
  availableAgents,
  agentSidebarOpen,
  agentsLoading,
};
