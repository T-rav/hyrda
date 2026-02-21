import React, { useState, useCallback } from 'react'
import { theme } from '../theme'
import { PIPELINE_STAGES } from '../constants'
import { useTimeline, STAGE_KEYS, STAGE_META, formatDuration } from '../hooks/useTimeline'

/** Status filter options. */
const STATUS_OPTIONS = ['all', 'active', 'done', 'failed', 'hitl']

/** Stage filter options (all + each pipeline stage). */
const STAGE_OPTIONS = ['all', ...STAGE_KEYS]

// ── FilterBar ────────────────────────────────────────────────────────

function FilterBar({ filterStage, setFilterStage, filterStatus, setFilterStatus, sortBy, setSortBy, issueCount }) {
  return (
    <div style={styles.filterBar}>
      <div style={styles.filterGroup}>
        <span style={styles.filterLabel}>Stage:</span>
        {STAGE_OPTIONS.map(key => (
          <span
            key={key}
            onClick={() => setFilterStage(key)}
            style={filterStage === key ? stageFilterStyles[key]?.active || filterPillActiveStyle : stageFilterStyles[key]?.inactive || filterPillStyle}
          >
            {key === 'all' ? 'All' : STAGE_META[key]?.label || key}
          </span>
        ))}
      </div>
      <div style={styles.filterGroup}>
        <span style={styles.filterLabel}>Status:</span>
        {STATUS_OPTIONS.map(key => (
          <span
            key={key}
            onClick={() => setFilterStatus(key)}
            style={filterStatus === key ? statusFilterStyles[key]?.active || filterPillActiveStyle : filterPillStyle}
          >
            {key.charAt(0).toUpperCase() + key.slice(1)}
          </span>
        ))}
      </div>
      <div style={styles.filterGroup}>
        <span style={styles.filterLabel}>Sort:</span>
        <span
          onClick={() => setSortBy('recency')}
          style={sortBy === 'recency' ? filterPillActiveStyle : filterPillStyle}
        >
          Recent
        </span>
        <span
          onClick={() => setSortBy('issue')}
          style={sortBy === 'issue' ? filterPillActiveStyle : filterPillStyle}
        >
          Issue #
        </span>
      </div>
      <span style={styles.issueCount}>{issueCount} issue{issueCount !== 1 ? 's' : ''}</span>
    </div>
  )
}

// ── Status indicator symbols ─────────────────────────────────────────

function StatusIndicator({ status }) {
  if (status === 'active') {
    return (
      <>
        <style>{pulseKeyframes}</style>
        <span style={statusIndicatorStyles.active} data-testid="status-active" />
      </>
    )
  }
  if (status === 'done') return <span style={statusIndicatorStyles.done}>✓</span>
  if (status === 'failed') return <span style={statusIndicatorStyles.failed}>✗</span>
  if (status === 'hitl') return <span style={statusIndicatorStyles.hitl}>⚠</span>
  return <span style={statusIndicatorStyles.pending} data-testid="status-pending" />
}

// ── TranscriptPreview ────────────────────────────────────────────────

function TranscriptPreview({ lines }) {
  const [expanded, setExpanded] = useState(false)
  const toggle = useCallback(() => setExpanded(v => !v), [])

  if (!lines || lines.length === 0) return null

  const visible = expanded ? lines : lines.slice(-5)

  return (
    <div style={styles.transcriptSection}>
      <div style={styles.transcriptLines}>
        {visible.map((line, i) => (
          <div key={i} style={styles.transcriptLine}>{line}</div>
        ))}
      </div>
      {lines.length > 5 && (
        <span style={styles.transcriptToggle} onClick={toggle}>
          {expanded ? 'Show less' : `Show all ${lines.length} lines`}
        </span>
      )}
    </div>
  )
}

// ── StageNode ────────────────────────────────────────────────────────

function StageNode({ stageKey, stageData, isLast, pr, branch }) {
  const meta = STAGE_META[stageKey]
  const nodeStyle = stageNodeStyles[stageKey]?.[stageData.status] || stageNodeStyles[stageKey]?.pending || stageNodeDotBase
  const connectorStyle = stageData.status !== 'pending'
    ? stageConnectorStyles[stageKey]?.active || connectorActiveBase
    : stageConnectorStyles[stageKey]?.pending || connectorPendingBase

  const duration = stageData.startTime && stageData.endTime
    ? formatDuration(new Date(stageData.endTime) - new Date(stageData.startTime))
    : stageData.startTime && stageData.status === 'active'
      ? 'running...'
      : null

  return (
    <div style={styles.stageNodeContainer}>
      <div style={styles.stageRow}>
        <div style={nodeStyle}>
          {stageData.status === 'active' && <style>{pulseKeyframes}</style>}
        </div>
        <div style={styles.stageInfo}>
          <span style={styles.stageLabel}>{meta?.label || stageKey}</span>
          <span style={stageBadgeStyles[stageData.status] || stageBadgeStyles.pending}>
            {stageData.status}
          </span>
          {duration && <span style={styles.stageDuration}>{duration}</span>}
        </div>
        <div style={styles.stageLinks}>
          {stageKey === 'review' && pr && (
            <span style={styles.stageLink}>PR #{pr.number}</span>
          )}
          {stageKey === 'implement' && branch && (
            <span style={styles.stageLink}>{branch}</span>
          )}
        </div>
      </div>
      <TranscriptPreview lines={stageData.transcript} />
      {!isLast && <div style={connectorStyle} />}
    </div>
  )
}

// ── VerticalTimeline (expanded issue) ────────────────────────────────

function VerticalTimeline({ issue }) {
  return (
    <div style={styles.verticalTimeline} data-testid={`timeline-${issue.issueNumber}`}>
      {STAGE_KEYS.map((key, idx) => (
        <StageNode
          key={key}
          stageKey={key}
          stageData={issue.stages[key]}
          isLast={idx === STAGE_KEYS.length - 1}
          pr={issue.pr}
          branch={issue.branch}
        />
      ))}
    </div>
  )
}

// ── IssueCard ────────────────────────────────────────────────────────

function IssueCard({ issue }) {
  const [expanded, setExpanded] = useState(false)
  const toggle = useCallback(() => setExpanded(v => !v), [])

  const meta = STAGE_META[issue.currentStage]
  const badgeStyle = issueCardBadgeStyles[issue.currentStage] || issueCardBadgeStyles.triage

  const duration = issue.startTime
    ? formatDuration(
        (issue.endTime ? new Date(issue.endTime) : new Date()) - new Date(issue.startTime)
      )
    : null

  return (
    <div style={styles.issueCard}>
      <div style={styles.issueCardHeader} onClick={toggle}>
        <div style={styles.issueCardLeft}>
          <span style={styles.issueNumber}>#{issue.issueNumber}</span>
          <span style={styles.issueTitle}>{issue.title}</span>
        </div>
        <div style={styles.issueCardRight}>
          <span style={badgeStyle}>{meta?.label || issue.currentStage}</span>
          {duration && <span style={styles.issueDuration}>{duration}</span>}
          <StatusIndicator status={issue.overallStatus} />
          <span style={styles.expandArrow}>{expanded ? '▾' : '▸'}</span>
        </div>
      </div>
      {expanded && <VerticalTimeline issue={issue} />}
    </div>
  )
}

// ── Timeline (main export) ───────────────────────────────────────────

export function Timeline({ events, workers, prs }) {
  const {
    issues, filterStage, setFilterStage, filterStatus, setFilterStatus, sortBy, setSortBy,
  } = useTimeline(events, workers, prs)

  return (
    <div style={styles.container}>
      <FilterBar
        filterStage={filterStage}
        setFilterStage={setFilterStage}
        filterStatus={filterStatus}
        setFilterStatus={setFilterStatus}
        sortBy={sortBy}
        setSortBy={setSortBy}
        issueCount={issues.length}
      />
      <div style={styles.issueList}>
        {issues.length === 0 && (
          <div style={styles.empty}>No issues processed yet</div>
        )}
        {issues.map(issue => (
          <IssueCard key={issue.issueNumber} issue={issue} />
        ))}
      </div>
    </div>
  )
}

// ── CSS keyframes ────────────────────────────────────────────────────

const pulseKeyframes = `
  @keyframes timeline-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }
`

// ── Styles ───────────────────────────────────────────────────────────

const styles = {
  container: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  filterBar: {
    display: 'flex',
    alignItems: 'center',
    gap: 16,
    padding: '8px 12px',
    borderBottom: `1px solid ${theme.border}`,
    background: theme.surface,
    flexWrap: 'wrap',
  },
  filterGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  },
  filterLabel: {
    fontSize: 10,
    fontWeight: 600,
    color: theme.textMuted,
    textTransform: 'uppercase',
    marginRight: 4,
  },
  filterPill: {
    padding: '2px 8px',
    borderRadius: 10,
    fontSize: 10,
    fontWeight: 600,
    cursor: 'pointer',
    borderWidth: 1,
    borderStyle: 'solid',
    borderColor: theme.border,
    color: theme.textMuted,
    background: 'transparent',
    transition: 'all 0.15s',
  },
  filterPillActive: {
    padding: '2px 8px',
    borderRadius: 10,
    fontSize: 10,
    fontWeight: 600,
    cursor: 'pointer',
    borderWidth: 1,
    borderStyle: 'solid',
    borderColor: theme.accent,
    color: theme.accent,
    background: theme.accentSubtle,
    transition: 'all 0.15s',
  },
  issueCount: {
    marginLeft: 'auto',
    fontSize: 11,
    color: theme.textMuted,
  },
  issueList: {
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
  issueCard: {
    background: theme.surface,
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    marginBottom: 8,
    overflow: 'hidden',
  },
  issueCardHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 12px',
    cursor: 'pointer',
    transition: 'background 0.15s',
  },
  issueCardLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    minWidth: 0,
    flex: 1,
  },
  issueNumber: {
    fontSize: 12,
    fontWeight: 700,
    color: theme.textBright,
    flexShrink: 0,
  },
  issueTitle: {
    fontSize: 12,
    color: theme.text,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  issueCardRight: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexShrink: 0,
  },
  issueBadge: {
    padding: '2px 8px',
    borderRadius: 10,
    fontSize: 10,
    fontWeight: 600,
    textTransform: 'uppercase',
    border: '1px solid',
    whiteSpace: 'nowrap',
  },
  issueDuration: {
    fontSize: 11,
    color: theme.textMuted,
    whiteSpace: 'nowrap',
  },
  expandArrow: {
    fontSize: 10,
    color: theme.textMuted,
    width: 12,
    textAlign: 'center',
  },
  verticalTimeline: {
    padding: '4px 12px 12px 12px',
    borderTop: `1px solid ${theme.border}`,
  },
  stageNodeContainer: {
    position: 'relative',
  },
  stageRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '6px 0',
  },
  stageNodeDot: {
    width: 12,
    height: 12,
    borderRadius: '50%',
    flexShrink: 0,
    border: '2px solid',
  },
  stageInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flex: 1,
  },
  stageLabel: {
    fontSize: 11,
    fontWeight: 600,
    color: theme.text,
    width: 72,
  },
  stageBadge: {
    padding: '1px 6px',
    borderRadius: 8,
    fontSize: 9,
    fontWeight: 600,
    textTransform: 'uppercase',
  },
  stageDuration: {
    fontSize: 10,
    color: theme.textMuted,
  },
  stageLinks: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  },
  stageLink: {
    fontSize: 10,
    color: theme.accent,
    fontFamily: 'monospace',
  },
  connector: {
    width: 2,
    height: 16,
    marginLeft: 5,
  },
  transcriptSection: {
    marginLeft: 20,
    marginBottom: 4,
  },
  transcriptLines: {
    background: theme.surfaceInset,
    borderRadius: 4,
    padding: '4px 8px',
    fontFamily: 'monospace',
    fontSize: 10,
    lineHeight: 1.5,
    overflowX: 'auto',
  },
  transcriptLine: {
    color: theme.codeText,
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all',
  },
  transcriptToggle: {
    fontSize: 10,
    color: theme.accent,
    cursor: 'pointer',
    marginTop: 2,
    display: 'inline-block',
  },
}

// ── Pre-computed style variants ──────────────────────────────────────

// Base for filter pills
const filterPillStyle = styles.filterPill
const filterPillActiveStyle = styles.filterPillActive

// Stage-colored filter pills
export const stageFilterStyles = Object.fromEntries(
  STAGE_KEYS.map(key => {
    const meta = STAGE_META[key]
    return [key, {
      active: {
        ...styles.filterPill,
        borderColor: meta.color,
        color: meta.color,
        background: meta.subtleColor,
      },
      inactive: styles.filterPill,
    }]
  })
)

// Status-colored filter pills
export const statusFilterStyles = {
  all: { active: filterPillActiveStyle },
  active: { active: { ...styles.filterPill, borderColor: theme.accent, color: theme.accent, background: theme.accentSubtle } },
  done: { active: { ...styles.filterPill, borderColor: theme.green, color: theme.green, background: theme.greenSubtle } },
  failed: { active: { ...styles.filterPill, borderColor: theme.red, color: theme.red, background: theme.redSubtle } },
  hitl: { active: { ...styles.filterPill, borderColor: theme.yellow, color: theme.yellow, background: theme.yellowSubtle } },
}

// Status indicator styles
export const statusIndicatorStyles = {
  active: {
    display: 'inline-block',
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: theme.accent,
    animation: 'timeline-pulse 1.5s ease-in-out infinite',
  },
  done: { fontSize: 12, fontWeight: 700, color: theme.green },
  failed: { fontSize: 12, fontWeight: 700, color: theme.red },
  hitl: { fontSize: 12, fontWeight: 700, color: theme.yellow },
  pending: {
    display: 'inline-block',
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: theme.border,
  },
}

// Stage badge styles (in expanded timeline)
export const stageBadgeStyles = {
  active: { ...styles.stageBadge, background: theme.accentSubtle, color: theme.accent },
  done: { ...styles.stageBadge, background: theme.greenSubtle, color: theme.green },
  failed: { ...styles.stageBadge, background: theme.redSubtle, color: theme.red },
  hitl: { ...styles.stageBadge, background: theme.yellowSubtle, color: theme.yellow },
  pending: { ...styles.stageBadge, background: theme.mutedSubtle, color: theme.textMuted },
}

// Stage node dot base
const stageNodeDotBase = styles.stageNodeDot

// Stage node dot styles — per stage, per status
export const stageNodeStyles = Object.fromEntries(
  STAGE_KEYS.map(key => {
    const meta = STAGE_META[key]
    return [key, {
      active: {
        ...stageNodeDotBase,
        background: meta.color,
        borderColor: meta.color,
        animation: 'timeline-pulse 1.5s ease-in-out infinite',
      },
      done: {
        ...stageNodeDotBase,
        background: meta.color,
        borderColor: meta.color,
      },
      failed: {
        ...stageNodeDotBase,
        background: theme.red,
        borderColor: theme.red,
      },
      hitl: {
        ...stageNodeDotBase,
        background: theme.yellow,
        borderColor: theme.yellow,
      },
      pending: {
        ...stageNodeDotBase,
        background: 'transparent',
        borderColor: theme.border,
      },
    }]
  })
)

// Connector styles — per stage
const connectorActiveBase = { ...styles.connector, background: theme.accent }
const connectorPendingBase = { ...styles.connector, background: theme.border, borderStyle: 'dashed' }

export const stageConnectorStyles = Object.fromEntries(
  STAGE_KEYS.map(key => {
    const meta = STAGE_META[key]
    return [key, {
      active: { ...styles.connector, background: meta.color },
      pending: connectorPendingBase,
    }]
  })
)

// Issue card stage badge styles
export const issueCardBadgeStyles = Object.fromEntries(
  PIPELINE_STAGES.map(s => [s.key, {
    ...styles.issueBadge,
    background: s.subtleColor,
    color: s.color,
    borderColor: s.color + '44',
  }])
)
