import React, { useMemo, useCallback } from 'react'
import { theme } from '../theme'
import { useHydra } from '../context/HydraContext'
import { StreamCard } from './StreamCard'
import { PIPELINE_STAGES } from '../constants'
import { STAGE_KEYS } from '../hooks/useTimeline'

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

function StageSection({ stage, issues, workerCount, intentMap, onViewTranscript, onRequestChanges, open, onToggle, enabled, dotColor }) {
  const activeCount = issues.filter(i => i.overallStatus === 'active').length
  const failedCount = issues.filter(i => i.overallStatus === 'failed').length
  const hitlCount = issues.filter(i => i.overallStatus === 'hitl').length
  const queuedCount = issues.filter(i => i.overallStatus === 'queued').length
  const hasRole = !!stage.role

  return (
    <div
      style={hasRole ? (enabled ? sectionEnabledStyle : sectionDisabledStyle) : styles.section}
      data-testid={`stage-section-${stage.key}`}
    >
      <div
        style={sectionHeaderStyles[stage.key]}
        onClick={onToggle}
      >
        <span style={{ fontSize: 10 }}>{open ? '▾' : '▸'}</span>
        <span style={sectionLabelStyles[stage.key]}>{stage.label}</span>
        {hasRole && !enabled && (
          <span style={styles.disabledBadge} data-testid={`stage-disabled-${stage.key}`}>Disabled</span>
        )}
        <span style={sectionCountStyles[stage.key]}>
          <span style={activeCount > 0 ? styles.activeBadge : undefined}>{activeCount} active</span>
          <span> · {queuedCount} queued</span>
          {failedCount > 0 && <span style={styles.failedBadge}> · {failedCount} failed</span>}
          {hitlCount > 0 && <span style={styles.hitlBadge}> · {hitlCount} hitl</span>}
          <span> · {workerCount} {workerCount === 1 ? 'worker' : 'workers'}</span>
        </span>
        {hasRole && (
          <span
            style={{ ...styles.statusDot, background: dotColor }}
            data-testid={`stage-dot-${stage.key}`}
          />
        )}
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

/** Map pipeline stage key to its index in STAGE_KEYS for building synthetic stages. */
const STAGE_INDEX = Object.fromEntries(STAGE_KEYS.map((k, i) => [k, i]))

/**
 * Convert a PipelineIssue from the server into a StreamCard-compatible shape.
 * Builds a synthetic `stages` object based on current pipeline position.
 */
export function toStreamIssue(pipeIssue, stageKey, prs) {
  const currentIdx = STAGE_INDEX[stageKey] ?? 0
  const isActive = pipeIssue.status === 'active'
  const isDone = pipeIssue.status === 'done'
  const stages = {}
  for (let i = 0; i < STAGE_KEYS.length; i++) {
    const k = STAGE_KEYS[i]
    if (i < currentIdx) {
      stages[k] = { status: 'done', startTime: null, endTime: null, transcript: [] }
    } else if (i === currentIdx) {
      const currentStageStatus = isDone ? 'done'
        : isActive ? 'active'
        : pipeIssue.status === 'failed' ? 'failed'
        : pipeIssue.status === 'hitl' ? 'hitl'
        : 'queued'
      stages[k] = { status: currentStageStatus, startTime: null, endTime: null, transcript: [] }
    } else {
      stages[k] = { status: 'pending', startTime: null, endTime: null, transcript: [] }
    }
  }

  // Match PR from prs array
  const matchedPr = (prs || []).find(p => p.issue === pipeIssue.issue_number)
  const pr = matchedPr ? { number: matchedPr.pr, url: matchedPr.url || null } : null

  return {
    issueNumber: pipeIssue.issue_number,
    title: pipeIssue.title || `Issue #${pipeIssue.issue_number}`,
    currentStage: stageKey,
    overallStatus: pipeIssue.status === 'hitl' ? 'hitl'
      : pipeIssue.status === 'failed' || pipeIssue.status === 'error' ? 'failed'
      : isDone ? 'done'
      : pipeIssue.status === 'active' ? 'active'
      : 'queued',
    startTime: null,
    endTime: null,
    pr,
    branch: `agent/issue-${pipeIssue.issue_number}`,
    stages,
  }
}

export function StreamView({ intents, expandedStages, onToggleStage, onViewTranscript, onRequestChanges }) {
  const { pipelineIssues, prs, stageStatus } = useHydra()

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

  // Build stage groups from pipelineIssues
  const stageGroups = useMemo(() => {
    // Build merged issues from PRs that are merged
    const mergedFromPrs = (prs || [])
      .filter(p => p.merged && p.issue)
      .map(p => toStreamIssue(
        { issue_number: p.issue, title: p.title || `Issue #${p.issue}`, url: p.url || '', status: 'done' },
        'merged',
        prs,
      ))
    return PIPELINE_STAGES.map(stage => {
      let stageIssues
      if (stage.key === 'merged') {
        // Combine pipelineIssues.merged (if any) + merged PRs
        const pipelineMerged = (pipelineIssues.merged || []).map(pi => toStreamIssue(pi, 'merged', prs))
        const combined = [...pipelineMerged]
        for (const m of mergedFromPrs) {
          if (!combined.some(i => i.issueNumber === m.issueNumber)) {
            combined.push(m)
          }
        }
        stageIssues = combined
      } else {
        stageIssues = (pipelineIssues[stage.key] || []).map(pi => toStreamIssue(pi, stage.key, prs))
      }
      // Sort active-first
      stageIssues.sort((a, b) => {
        const aActive = a.overallStatus === 'active' ? 1 : 0
        const bActive = b.overallStatus === 'active' ? 1 : 0
        return bActive - aActive
      })
      return { stage, issues: stageIssues }
    })
  }, [pipelineIssues, prs])

  const handleToggleStage = useCallback((key) => {
    onToggleStage(prev => ({ ...prev, [key]: !prev[key] }))
  }, [onToggleStage])

  const totalIssues = stageGroups.reduce((sum, g) => sum + g.issues.length, 0)
  const hasAnyIssues = totalIssues > 0 || pendingIntents.length > 0

  return (
    <div style={styles.container}>
      {pendingIntents.map((intent, i) => (
        <PendingIntentCard key={`pending-${i}`} intent={intent} />
      ))}

      {stageGroups.map(({ stage, issues: stageIssues }) => {
        const status = stageStatus[stage.key] || {}
        const enabled = status.enabled !== false
        const workerCount = status.workerCount || 0
        let dotColor
        if (!enabled) {
          dotColor = theme.red
        } else if (workerCount > 0) {
          dotColor = theme.green
        } else {
          dotColor = theme.yellow
        }
        return (
          <StageSection
            key={stage.key}
            stage={stage}
            issues={stageIssues}
            workerCount={workerCount}
            intentMap={intentMap}
            onViewTranscript={onViewTranscript}
            onRequestChanges={onRequestChanges}
            open={!!expandedStages[stage.key]}
            onToggle={() => handleToggleStage(stage.key)}
            enabled={enabled}
            dotColor={dotColor}
          />
        )
      })}

      {!hasAnyIssues && (
        <div style={styles.empty}>
          No active work.
        </div>
      )}
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
  failedBadge: {
    fontWeight: 700,
    color: theme.red,
  },
  hitlBadge: {
    fontWeight: 700,
    color: theme.yellow,
  },
  statusDot: {
    display: 'inline-block',
    width: 8,
    height: 8,
    borderRadius: '50%',
    flexShrink: 0,
  },
  disabledBadge: {
    fontSize: 9,
    fontWeight: 600,
    color: theme.red,
    background: theme.redSubtle,
    border: `1px solid ${theme.red}`,
    borderRadius: 10,
    padding: '1px 6px',
    textTransform: 'uppercase',
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

// Pre-computed section opacity variants (avoids object spread in StageSection render)
const sectionEnabledStyle = { ...styles.section, opacity: 1, transition: 'opacity 0.2s' }
const sectionDisabledStyle = { ...styles.section, opacity: 0.5, transition: 'opacity 0.2s' }
