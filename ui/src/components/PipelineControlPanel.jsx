import React, { useState } from 'react'
import { theme } from '../theme'
import { PIPELINE_LOOPS, PIPELINE_STAGES, ACTIVE_STATUSES } from '../constants'
import { useHydra } from '../context/HydraContext'

function formatDuration(startTime) {
  if (!startTime) return ''
  const diff = Date.now() - new Date(startTime).getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  if (minutes < 60) return `${minutes}m ${secs}s`
  const hours = Math.floor(minutes / 60)
  const remainMinutes = minutes % 60
  return remainMinutes > 0 ? `${hours}h ${remainMinutes}m` : `${hours}h`
}

// Pre-computed worker card dot style variants — avoids object spread in render loops
const workerDotActive = { width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: theme.accent }
const workerDotDone = { width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: theme.green }
const workerDotFailed = { width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: theme.red }
const workerDotInactive = { width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: theme.textInactive }

function pipelineWorkerDot(status) {
  if (ACTIVE_STATUSES.includes(status)) return workerDotActive
  if (status === 'done') return workerDotDone
  if (status === 'failed' || status === 'escalated') return workerDotFailed
  return workerDotInactive
}

function TranscriptPreview({ lines }) {
  const [expanded, setExpanded] = useState(false)
  if (!lines || lines.length === 0) return null

  const shown = expanded ? lines : lines.slice(-3)

  return (
    <div style={styles.transcriptSection}>
      <div
        style={styles.transcriptToggle}
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? 'Hide' : 'Show'} transcript ({lines.length} lines)
      </div>
      <div style={expanded ? styles.transcriptLinesExpanded : undefined}>
        {shown.map((line, i) => (
          <div key={i} style={styles.transcriptLine}>{line}</div>
        ))}
      </div>
    </div>
  )
}

function PipelineWorkerCard({ workerKey, worker }) {
  const issueMatch = workerKey.toString().match(/\d+$/)
  const issueNum = issueMatch ? issueMatch[0] : workerKey

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <span
          style={pipelineWorkerDot(worker.status)}
          data-testid={`pipeline-dot-${workerKey}`}
        />
        <span style={styles.label}>#{issueNum}</span>
        <span style={roleBadgeByRole[worker.role] ?? roleBadgeFallback}>
          {worker.role}
        </span>
        <span style={styles.status}>{worker.status}</span>
      </div>
      <div style={styles.workerMeta}>
        {worker.title && <div style={styles.workerTitle}>{worker.title}</div>}
        <div style={styles.lastRun}>
          Duration: {formatDuration(worker.startTime)}
        </div>
      </div>
      <TranscriptPreview lines={worker.transcript} />
    </div>
  )
}

export function PipelineControlPanel({ collapsed, onToggleCollapse, onToggleBgWorker }) {
  const { workers, stageStatus, hitlItems } = useHydra()

  const pipelineWorkers = Object.entries(workers || {}).filter(
    ([, w]) => w.role && ACTIVE_STATUSES.includes(w.status)
  )
  const hasPipelineWorkers = pipelineWorkers.length > 0
  const hitlCount = hitlItems?.length || 0

  if (collapsed) {
    return (
      <div style={styles.collapsedPanel}>
        <div
          style={styles.collapseBtn}
          onClick={onToggleCollapse}
          data-testid="pipeline-panel-expand"
        >
          &#9664;
        </div>
        {PIPELINE_LOOPS.map((loop) => {
          const status = stageStatus[loop.key] || {}
          const enabled = status.enabled !== false
          return (
            <span
              key={loop.key}
              style={enabled ? collapsedDotLit[loop.key] : collapsedDotDim[loop.key]}
              data-testid={`collapsed-dot-${loop.key}`}
            />
          )
        })}
      </div>
    )
  }

  return (
    <div style={styles.panel}>
      <div style={styles.headingRow}>
        <h3 style={styles.heading}>Pipeline</h3>
        <div
          style={styles.collapseBtn}
          onClick={onToggleCollapse}
          data-testid="pipeline-panel-collapse"
        >
          &#9654;
        </div>
      </div>

      <div style={styles.loopStack}>
        {PIPELINE_LOOPS.map((loop) => {
          const status = stageStatus[loop.key] || {}
          const enabled = status.enabled !== false
          const activeCount = status.workerCount || 0
          return (
            <div key={loop.key} style={styles.loopChip}>
              <span style={enabled ? loopDotLit[loop.key] : loopDotDim[loop.key]} />
              <span style={enabled ? styles.loopLabel : styles.loopLabelDim}>{loop.label}</span>
              <span
                style={enabled && activeCount > 0 ? loopCountActive[loop.key] : loopCountDim}
                data-testid={`loop-count-${loop.key}`}
              >
                {activeCount}
              </span>
              <span style={styles.loopCountLabel}>
                {activeCount === 1 ? 'worker' : 'workers'}
              </span>
              {onToggleBgWorker && (
                <button
                  style={enabled ? styles.toggleOn : styles.toggleOff}
                  onClick={() => onToggleBgWorker(loop.key, !enabled)}
                >
                  {enabled ? 'On' : 'Off'}
                </button>
              )}
            </div>
          )
        })}
      </div>

      {(pipelineWorkers.length > 0 || hitlCount > 0) && (
        <div style={styles.statusRow}>
          {pipelineWorkers.length > 0 && (
            <div style={styles.activeBadge}>
              {pipelineWorkers.length} active
            </div>
          )}
          {hitlCount > 0 && (
            <div style={styles.hitlBadge}>
              {hitlCount} HITL {hitlCount === 1 ? 'issue' : 'issues'}
            </div>
          )}
        </div>
      )}

      {!hasPipelineWorkers && (
        <div style={styles.empty}>No active pipeline workers</div>
      )}
      {hasPipelineWorkers && (
        <div style={styles.workerList}>
          {pipelineWorkers.map(([key, worker]) => (
            <PipelineWorkerCard key={key} workerKey={key} worker={worker} />
          ))}
        </div>
      )}
    </div>
  )
}

const styles = {
  panel: {
    width: 240,
    flexShrink: 0,
    borderLeft: `1px solid ${theme.border}`,
    background: theme.surface,
    overflowY: 'auto',
    padding: 16,
  },
  collapsedPanel: {
    width: 44,
    flexShrink: 0,
    borderLeft: `1px solid ${theme.border}`,
    background: theme.surface,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    paddingTop: 12,
    gap: 12,
  },
  headingRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  heading: {
    fontSize: 14,
    fontWeight: 600,
    color: theme.textBright,
    margin: 0,
  },
  collapseBtn: {
    fontSize: 10,
    color: theme.textMuted,
    cursor: 'pointer',
    padding: '4px 6px',
    borderRadius: 4,
    transition: 'color 0.15s',
  },
  collapsedDot: {
    width: 10,
    height: 10,
    borderRadius: '50%',
    flexShrink: 0,
  },
  loopStack: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    marginBottom: 16,
  },
  loopChip: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '4px 8px',
    border: `1px solid ${theme.border}`,
    borderRadius: 12,
    background: theme.bg,
  },
  loopLabel: {
    fontSize: 11,
    fontWeight: 600,
    color: theme.text,
    flex: 1,
  },
  loopLabelDim: {
    fontSize: 11,
    fontWeight: 600,
    color: theme.textMuted,
    flex: 1,
  },
  loopCount: {
    fontSize: 10,
    fontWeight: 700,
    minWidth: 14,
    textAlign: 'center',
  },
  loopCountLabel: {
    fontSize: 9,
    fontWeight: 600,
    color: theme.textMuted,
    textTransform: 'uppercase',
  },
  toggleOn: {
    padding: '2px 8px',
    fontSize: 10,
    fontWeight: 600,
    border: `1px solid ${theme.green}`,
    borderRadius: 10,
    background: theme.greenSubtle,
    color: theme.green,
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  toggleOff: {
    padding: '2px 8px',
    fontSize: 10,
    fontWeight: 600,
    border: `1px solid ${theme.border}`,
    borderRadius: 10,
    background: theme.surface,
    color: theme.textMuted,
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  statusRow: {
    display: 'flex',
    gap: 8,
    flexWrap: 'wrap',
    marginBottom: 12,
  },
  activeBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    fontSize: 11,
    fontWeight: 600,
    color: theme.accent,
    background: theme.accentSubtle,
    border: `1px solid ${theme.accent}`,
    borderRadius: 10,
    padding: '2px 10px',
  },
  hitlBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    fontSize: 11,
    fontWeight: 600,
    color: theme.orange,
    background: theme.orangeSubtle,
    border: `1px solid ${theme.orange}`,
    borderRadius: 10,
    padding: '2px 10px',
  },
  empty: {
    fontSize: 12,
    color: theme.textMuted,
    padding: '8px 0',
  },
  workerList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  card: {
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    padding: 12,
    background: theme.bg,
    overflow: 'hidden',
    minWidth: 0,
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    marginBottom: 6,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    flexShrink: 0,
  },
  label: {
    fontSize: 12,
    fontWeight: 600,
    color: theme.text,
    flex: 1,
  },
  roleBadge: {
    fontSize: 9,
    fontWeight: 600,
    color: theme.white,
    padding: '1px 5px',
    borderRadius: 4,
    textTransform: 'uppercase',
  },
  status: {
    fontSize: 10,
    fontWeight: 600,
    color: theme.textMuted,
    textTransform: 'uppercase',
  },
  workerMeta: {
    marginBottom: 4,
  },
  workerTitle: {
    fontSize: 11,
    color: theme.text,
    marginBottom: 4,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  lastRun: {
    fontSize: 11,
    color: theme.textMuted,
    marginBottom: 4,
  },
  transcriptSection: {
    borderTop: `1px solid ${theme.border}`,
    paddingTop: 6,
    marginTop: 4,
  },
  transcriptToggle: {
    fontSize: 10,
    color: theme.accent,
    cursor: 'pointer',
    marginBottom: 4,
  },
  transcriptLine: {
    fontSize: 10,
    color: theme.textMuted,
    fontFamily: 'monospace',
    lineHeight: '16px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  transcriptLinesExpanded: {
    maxHeight: 200,
    overflowY: 'auto',
  },
}

// Pre-computed role badge style variants — keyed by role string (avoids object spread in render loops)
const roleBadgeByRole = Object.fromEntries(
  PIPELINE_STAGES.filter(s => s.role).map(s => [s.role, { ...styles.roleBadge, background: s.color }])
)
const roleBadgeFallback = { ...styles.roleBadge, background: theme.textMuted }

// Pre-computed per-loop style variants (avoids object spread in render loops)
const loopDotLit = Object.fromEntries(PIPELINE_LOOPS.map(l => [l.key, { ...styles.dot, background: l.color }]))
const loopDotDim = Object.fromEntries(PIPELINE_LOOPS.map(l => [l.key, { ...styles.dot, background: l.dimColor }]))
const collapsedDotLit = Object.fromEntries(PIPELINE_LOOPS.map(l => [l.key, { ...styles.collapsedDot, background: l.color }]))
const collapsedDotDim = Object.fromEntries(PIPELINE_LOOPS.map(l => [l.key, { ...styles.collapsedDot, background: l.dimColor }]))
const loopCountActive = Object.fromEntries(PIPELINE_LOOPS.map(l => [l.key, { ...styles.loopCount, color: l.color }]))
const loopCountDim = { ...styles.loopCount, color: theme.textMuted }
