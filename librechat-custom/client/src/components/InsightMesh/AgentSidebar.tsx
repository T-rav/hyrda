import { useEffect, useCallback } from 'react';
import { useRecoilState, useSetRecoilState } from 'recoil';
import { useNavigate } from 'react-router-dom';
import store from '~/store';
import AgentCard from './AgentCard';

interface AgentSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

/**
 * Agent Sidebar component
 * Displays available agents (excluding research agent)
 * Clicking an agent creates a new conversation with that agent selected
 */
export default function AgentSidebar({ isOpen, onClose }: AgentSidebarProps) {
  const navigate = useNavigate();
  const [agents, setAgents] = useRecoilState(store.availableAgents);
  const [loading, setLoading] = useRecoilState(store.agentsLoading);
  const setMetadata = useSetRecoilState(store.insightMeshMetadata);

  // Fetch agents on mount
  useEffect(() => {
    if (!isOpen || agents.length > 0) {
      return;
    }

    const fetchAgents = async () => {
      setLoading(true);
      try {
        const response = await fetch('/api/insightmesh/agents');
        if (!response.ok) {
          throw new Error('Failed to fetch agents');
        }
        const data = await response.json();
        setAgents(data.agents || []);
      } catch (error) {
        console.error('[InsightMesh] Failed to fetch agents:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchAgents();
  }, [isOpen, agents.length, setAgents, setLoading]);

  const handleSelectAgent = useCallback(
    async (agentName: string) => {
      try {
        // Update metadata for new conversation
        setMetadata({
          deepSearchEnabled: false,
          researchDepth: 'deep',
          selectedAgent: agentName,
        });

        // Navigate to new conversation
        // The metadata will be saved when the first message is sent
        navigate('/c/new');

        // Close sidebar
        onClose();
      } catch (error) {
        console.error('[InsightMesh] Failed to select agent:', error);
      }
    },
    [navigate, onClose, setMetadata],
  );

  if (!isOpen) {
    return null;
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/50 transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Sidebar */}
      <div className="fixed right-0 top-0 z-50 h-full w-80 bg-surface-primary shadow-xl transform transition-transform duration-300">
        {/* Header */}
        <div className="border-border-light flex items-center justify-between border-b p-4">
          <h2 className="text-text-primary text-lg font-semibold">Available Agents</h2>
          <button
            onClick={onClose}
            className="text-text-secondary hover:text-text-primary transition-colors"
            aria-label="Close agent sidebar"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-6 w-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="h-[calc(100%-4rem)] overflow-y-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <div className="text-text-secondary">Loading agents...</div>
            </div>
          ) : agents.length === 0 ? (
            <div className="text-text-secondary text-center">
              <p>No agents available</p>
            </div>
          ) : (
            <div className="space-y-3">
              {agents.map((agent) => (
                <AgentCard key={agent.name} agent={agent} onSelect={handleSelectAgent} />
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
