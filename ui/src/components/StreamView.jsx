import React, { useMemo } from 'react'
import { theme } from '../theme'
import { useTimeline } from '../hooks/useTimeline'
import { StreamCard } from './StreamCard'

function PendingIntentCard({ intent }) {
  return (
    <div style={styles.pendingCard}>
      <span style={styles.pendingDot} />
      <span style={styles.pendingText}>{intent.text}</span>
      <span style={styles.pendingStatus}>
        {intent.status === 'pending' ? 'Creating issue...' : 'Failed'}
      </span>
    </div>
  )
}

export function StreamView({ events, workers, prs, intents, onViewTranscript, onRequestChanges }) {
  const { issues } = useTimeline(events, workers, prs)

  // Match intents to issues by issueNumber
  const intentMap = useMemo(() => {
    const map = new Map()
    for (const intent of (intents || [])) {
      if (intent.issueNumber != null) {
        map.set(intent.issueNumber, intent)
      }
    }
    return map
  }, [intents])

  // Pending intents (not yet matched to an issue)
  const pendingIntents = useMemo(
    () => (intents || []).filter(i => i.status === 'pending' || (i.status === 'failed' && i.issueNumber == null)),
    [intents]
  )

  // Sort: active first, then by recency
  const sorted = useMemo(() => {
    return [...issues].sort((a, b) => {
      const aActive = a.overallStatus === 'active' ? 1 : 0
      const bActive = b.overallStatus === 'active' ? 1 : 0
      if (aActive !== bActive) return bActive - aActive
      const aTime = a.endTime || a.startTime || ''
      const bTime = b.endTime || b.startTime || ''
      return bTime.localeCompare(aTime)
    })
  }, [issues])

  const isEmpty = sorted.length === 0 && pendingIntents.length === 0

  return (
    <div style={styles.container}>
      {isEmpty && (
        <div style={styles.empty}>
          No active work. Type an intent above to get started.
        </div>
      )}

      {pendingIntents.map((intent, i) => (
        <PendingIntentCard key={`pending-${i}`} intent={intent} />
      ))}

      {sorted.map(issue => (
        <StreamCard
          key={issue.issueNumber}
          issue={issue}
          intent={intentMap.get(issue.issueNumber)}
          defaultExpanded={issue.overallStatus === 'active'}
          onViewTranscript={onViewTranscript}
          onRequestChanges={onRequestChanges}
        />
      ))}
    </div>
  )
}

const styles = {
  container: {
    flex: 1,
    overflowY: 'auto',
    padding: 8,
  },
  empty: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: 200,
    color: theme.textMuted,
    fontSize: 13,
  },
  pendingCard: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '10px 12px',
    background: theme.intentBg,
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    marginBottom: 8,
  },
  pendingDot: {
    display: 'inline-block',
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: theme.accent,
    animation: 'stream-pulse 1.5s ease-in-out infinite',
    flexShrink: 0,
  },
  pendingText: {
    flex: 1,
    fontSize: 12,
    color: theme.text,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  pendingStatus: {
    fontSize: 10,
    color: theme.textMuted,
    flexShrink: 0,
  },
}
