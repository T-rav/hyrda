import { useCallback } from 'react';
import { useRecoilState } from 'recoil';
import { useParams } from 'react-router-dom';
import type { ResearchDepth } from '~/store/insightmesh';
import store from '~/store';

const DEPTH_OPTIONS: { value: ResearchDepth; label: string; description: string }[] = [
  { value: 'quick', label: 'Quick', description: 'Fast, surface-level research' },
  { value: 'standard', label: 'Standard', description: 'Balanced speed and depth' },
  { value: 'deep', label: 'Deep', description: 'Thorough research with citations' },
  { value: 'exhaustive', label: 'Exhaustive', description: 'Maximum depth, slowest' },
];

/**
 * Research Depth Selector component
 * Appears when deep search is enabled
 * Allows users to configure research depth level
 */
export default function ResearchDepthSelector() {
  const { conversationId } = useParams();
  const [metadata, setMetadata] = useRecoilState(store.insightMeshMetadata);

  const handleDepthChange = useCallback(
    async (newDepth: ResearchDepth) => {
      if (!conversationId || newDepth === metadata.researchDepth) {
        return;
      }

      // Update local state immediately
      setMetadata((prev) => ({
        ...prev,
        researchDepth: newDepth,
      }));

      // Persist to backend
      try {
        const response = await fetch(`/api/insightmesh/conversations/${conversationId}/metadata`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            deepSearchEnabled: metadata.deepSearchEnabled,
            researchDepth: newDepth,
            selectedAgent: metadata.selectedAgent,
          }),
        });

        if (!response.ok) {
          throw new Error('Failed to update research depth');
        }
      } catch (error) {
        console.error('[InsightMesh] Failed to update research depth:', error);
        // Revert on error
        setMetadata((prev) => ({
          ...prev,
          researchDepth: metadata.researchDepth,
        }));
      }
    },
    [conversationId, metadata, setMetadata],
  );

  return (
    <div className="flex items-center gap-1">
      <span className="text-text-tertiary text-xs">Depth:</span>
      <select
        value={metadata.researchDepth}
        onChange={(e) => handleDepthChange(e.target.value as ResearchDepth)}
        className="bg-surface-secondary border-border-medium text-text-primary h-9 rounded-md border px-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        aria-label="Select research depth"
      >
        {DEPTH_OPTIONS.map((option) => (
          <option key={option.value} value={option.value} title={option.description}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
