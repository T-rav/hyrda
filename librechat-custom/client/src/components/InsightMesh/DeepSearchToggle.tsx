import { useCallback } from 'react';
import { useRecoilState } from 'recoil';
import { useParams } from 'react-router-dom';
import { Tooltip, TooltipContent, TooltipTrigger } from '~/components/ui';
import store from '~/store';
import ResearchDepthSelector from './ResearchDepthSelector';

/**
 * Deep Search Toggle component
 * Enables/disables deep research mode for the conversation
 * When enabled, routes all messages to research agent with configurable depth
 */
export default function DeepSearchToggle() {
  const { conversationId } = useParams();
  const [metadata, setMetadata] = useRecoilState(store.insightMeshMetadata);

  const handleToggle = useCallback(async () => {
    if (!conversationId) {
      return;
    }

    const newValue = !metadata.deepSearchEnabled;

    // Update local state immediately for responsive UI
    setMetadata((prev) => ({
      ...prev,
      deepSearchEnabled: newValue,
    }));

    // Persist to backend
    try {
      const response = await fetch(`/api/insightmesh/conversations/${conversationId}/metadata`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          deepSearchEnabled: newValue,
          researchDepth: metadata.researchDepth,
          selectedAgent: metadata.selectedAgent,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to update metadata');
      }
    } catch (error) {
      console.error('[InsightMesh] Failed to update deep search state:', error);
      // Revert local state on error
      setMetadata((prev) => ({
        ...prev,
        deepSearchEnabled: !newValue,
      }));
    }
  }, [conversationId, metadata, setMetadata]);

  // Don't show on landing page (new conversation)
  if (!conversationId || conversationId === 'new') {
    return null;
  }

  return (
    <div className="flex items-center gap-2">
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            onClick={handleToggle}
            className={`flex h-9 items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
              metadata.deepSearchEnabled
                ? 'border-blue-500 bg-blue-500/10 text-blue-600 hover:bg-blue-500/20'
                : 'border-border-medium text-text-secondary hover:bg-surface-hover'
            }`}
            aria-label="Toggle deep research mode"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <span>Deep Research</span>
          </button>
        </TooltipTrigger>
        <TooltipContent side="bottom">
          {metadata.deepSearchEnabled
            ? 'Disable deep research mode'
            : 'Enable deep research mode - routes messages through research agent'}
        </TooltipContent>
      </Tooltip>

      {metadata.deepSearchEnabled && <ResearchDepthSelector />}
    </div>
  );
}
