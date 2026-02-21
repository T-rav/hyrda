import React, { useMemo, useState } from 'react'
import { theme } from '../theme'
import { useTimeline } from '../hooks/useTimeline'
import { StreamCard } from './StreamCard'
import { PIPELINE_STAGES } from '../constants'

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

function StageSection({ stage, issues, intentMap, onViewTranscript, onRequestChanges, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen)
  const activeCount = issues.filter(i => i.overallStatus === 'active').length

  return (
    <div style={styles.section}>
      <div
        style={sectionHeaderStyles[stage.key]}
        onClick={() => setOpen(!open)}
      >
        <span style={{ fontSize: 10 }}>{open ? '▾' : '▸'}</span>
        <span style={sectionLabelStyles[stage.key]}>{stage.label}</span>
        <span style={sectionCountStyles[stage.key]}>
          {activeCount > 0 && <span style={styles.activeBadge}>{activeCount} active · </span>}
          {issues.length}
        </span>
      </div>
      {open && issues.map(issue => (
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

  // Group issues by currentStage, sorted active-first within each group
  const stageGroups = useMemo(() => {
    const groups = []
    for (const stage of PIPELINE_STAGES) {
      const stageIssues = issues
        .filter(i => i.currentStage === stage.key)
        .sort((a, b) => {
          const aActive = a.overallStatus === 'active' ? 1 : 0
          const bActive = b.overallStatus === 'active' ? 1 : 0
          if (aActive !== bActive) return bActive - aActive
          const aTime = a.endTime || a.startTime || ''
          const bTime = b.endTime || b.startTime || ''
          return bTime.localeCompare(aTime)
        })
      if (stageIssues.length > 0) {
        groups.push({ stage, issues: stageIssues })
      }
    }
    return groups
  }, [issues])

  const isEmpty = stageGroups.length === 0 && pendingIntents.length === 0

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

      {stageGroups.map(({ stage, issues: stageIssues }) => (
        <StageSection
          key={stage.key}
          stage={stage}
          issues={stageIssues}
          intentMap={intentMap}
          onViewTranscript={onViewTranscript}
          onRequestChanges={onRequestChanges}
          defaultOpen={stageIssues.some(i => i.overallStatus === 'active')}
        />
      ))}
    </div>
  )
}

// Pre-computed per-stage section header styles (avoids object spread in .map())
const sectionHeaderBase = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  padding: '8px 12px',
  margin: '8px 8px 4px',
  cursor: 'pointer',
  userSelect: 'none',
  borderRadius: 6,
  transition: 'background 0.15s',
}

const sectionLabelBase = {
  fontSize: 11,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
}

const sectionCountBase = {
  fontSize: 11,
  fontWeight: 600,
  marginLeft: 'auto',
}

const sectionHeaderStyles = Object.fromEntries(
  PIPELINE_STAGES.map(s => [s.key, {
    ...sectionHeaderBase,
    background: s.subtleColor,
    border: `1px solid ${s.color}33`,
    borderLeft: `3px solid ${s.color}`,
  }])
)

const sectionLabelStyles = Object.fromEntries(
  PIPELINE_STAGES.map(s => [s.key, {
    ...sectionLabelBase,
    color: s.color,
  }])
)

const sectionCountStyles = Object.fromEntries(
  PIPELINE_STAGES.map(s => [s.key, {
    ...sectionCountBase,
    color: s.color,
  }])
)

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
  section: {
    marginBottom: 4,
  },
  activeBadge: {
    fontWeight: 700,
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
