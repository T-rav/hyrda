import { useCallback } from 'react';
import type { Agent } from '~/store/insightmesh';

interface AgentCardProps {
  agent: Agent;
  onSelect: (agentName: string) => void;
}

/**
 * Agent Card component
 * Displays individual agent in sidebar with name, description, and aliases
 */
export default function AgentCard({ agent, onSelect }: AgentCardProps) {
  const handleClick = useCallback(() => {
    onSelect(agent.name);
  }, [agent.name, onSelect]);

  return (
    <button
      onClick={handleClick}
      className="text-left w-full rounded-lg border border-border-medium bg-surface-primary p-4 transition-all hover:border-blue-500 hover:bg-surface-hover hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <h3 className="text-text-primary mb-1 font-semibold capitalize">{agent.name}</h3>
          <p className="text-text-secondary mb-2 text-sm">{agent.description}</p>
          {agent.aliases && agent.aliases.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {agent.aliases.map((alias) => (
                <span
                  key={alias}
                  className="bg-surface-tertiary text-text-tertiary rounded px-2 py-0.5 text-xs"
                >
                  {alias}
                </span>
              ))}
            </div>
          )}
        </div>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="text-text-tertiary h-5 w-5 flex-shrink-0"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5l7 7-7 7"
          />
        </svg>
      </div>
    </button>
  );
}
