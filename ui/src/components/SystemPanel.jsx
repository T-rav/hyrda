import React, { useState } from 'react'
import { theme } from '../theme'
import { BACKGROUND_WORKERS, PIPELINE_LOOPS, PIPELINE_STAGES, ACTIVE_STATUSES } from '../constants'
import { useHydra } from '../context/HydraContext'

function relativeTime(isoString) {
  if (!isoString) return 'never'
  const diff = Date.now() - new Date(isoString).getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ago`
}

function formatDuration(startTime) {
  if (!startTime) return ''
  const diff = Date.now() - new Date(startTime).getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${minutes}m ${secs}s`
}

function statusColor(status) {
  if (status === 'ok') return theme.green
  if (status === 'error') return theme.red
  return theme.textInactive
}

function pipelineStatusColor(status) {
  if (ACTIVE_STATUSES.includes(status)) return theme.accent
  if (status === 'done') return theme.green
  if (status === 'failed' || status === 'escalated') return theme.red
  return theme.textInactive
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
      {shown.map((line, i) => (
        <div key={i} style={styles.transcriptLine}>{line}</div>
      ))}
    </div>
  )
}

function PipelineWorkerCard({ workerKey, worker }) {
  const stage = PIPELINE_STAGES.find(s => s.role === worker.role)
  const stageColor = stage?.color || theme.textMuted
  const issueMatch = workerKey.toString().match(/\d+$/)
  const issueNum = issueMatch ? issueMatch[0] : workerKey

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <span
          style={{ ...styles.dot, background: pipelineStatusColor(worker.status) }}
          data-testid={`pipeline-dot-${workerKey}`}
        />
        <span style={styles.label}>#{issueNum}</span>
        <span style={{ ...styles.roleBadge, background: stageColor }}>
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

function BackgroundWorkerCard({ def, state, pipelinePollerLastRun, orchestratorStatus, onToggleBgWorker, onViewLog }) {
  const isPipelinePoller = def.key === 'pipeline_poller'
  const isSystem = def.system === true
  const orchRunning = orchestratorStatus === 'running'

  let dotColor, statusText, lastRun, details

  if (!orchRunning) {
    // Orchestrator not running — system workers stopped, non-system show toggle state
    lastRun = isPipelinePoller ? (pipelinePollerLastRun || null) : (state?.last_run || null)
    details = state?.details || {}
    if (isSystem) {
      dotColor = theme.red
      statusText = 'stopped'
    } else if (state?.enabled === false) {
      dotColor = theme.red
      statusText = 'off'
    } else {
      dotColor = theme.yellow
      statusText = 'idle'
    }
  } else if (isPipelinePoller) {
    // Pipeline poller is frontend-only
    lastRun = pipelinePollerLastRun || null
    details = {}
    dotColor = lastRun ? theme.green : theme.textInactive
    statusText = lastRun ? 'ok' : 'idle'
  } else if (isSystem) {
    // System workers: ok/error based on backend state
    if (!state || !state.status || state.status === 'disabled') {
      dotColor = theme.green
      statusText = 'ok'
    } else {
      dotColor = statusColor(state.status)
      statusText = state.status
    }
    lastRun = state?.last_run || null
    details = state?.details || {}
  } else if (!state) {
    dotColor = theme.yellow
    statusText = 'idle'
    lastRun = null
    details = {}
  } else if (state.enabled === false) {
    dotColor = theme.red
    statusText = 'off'
    lastRun = state.last_run || null
    details = state.details || {}
  } else {
    dotColor = statusColor(state.status || 'ok')
    statusText = state.status || 'ok'
    lastRun = state.last_run || null
    details = state.details || {}
  }

  const enabled = !isSystem && (state ? state.enabled !== false : true)
  const showToggle = onToggleBgWorker && !isSystem
  const isError = statusText === 'error' || statusText === 'stopped'
  const hasDetails = Object.keys(details).length > 0

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <span
          style={{ ...styles.dot, background: dotColor }}
          data-testid={`dot-${def.key}`}
        />
        <span style={styles.label}>{def.label}</span>
        {isSystem && <span style={styles.systemBadge}>system</span>}
        {isSystem ? (
          <span
            style={statusText === 'ok'
              ? styles.statusPillOk
              : styles.statusPillError}
            data-testid={`status-pill-${def.key}`}
          >
            {statusText}
          </span>
        ) : (
          <span style={styles.status}>{statusText}</span>
        )}
        {showToggle && (
          <button
            style={enabled ? styles.toggleOn : styles.toggleOff}
            onClick={() => onToggleBgWorker(def.key, !enabled)}
          >
            {enabled ? 'On' : 'Off'}
          </button>
        )}
      </div>
      <div style={styles.lastRun}>
        Last run: {relativeTime(lastRun)}
      </div>
      {hasDetails && (
        <div style={isError ? (onViewLog ? styles.detailsErrorCompact : styles.detailsError) : styles.details}>
          {Object.entries(details).map(([k, v]) => (
            <div key={k} style={k === 'error' ? styles.errorRow : styles.detailRow}>
              <span style={isError ? styles.detailKeyError : styles.detailKey}>{k.replace(/_/g, ' ')}</span>
              <span style={isError ? styles.detailValueError : styles.detailValue}>{String(v)}</span>
            </div>
          ))}
        </div>
      )}
      {onViewLog && (
        <div style={styles.cardActions}>
          <span
            style={styles.viewLogLink}
            onClick={() => onViewLog(`bg-${def.key}`)}
            data-testid={`view-log-${def.key}`}
          >
            View Log
          </span>
        </div>
      )}
    </div>
  )
}

export function SystemPanel({ workers, backgroundWorkers, onToggleBgWorker, onViewLog }) {
  const { pipelinePollerLastRun, hitlItems, pipelineIssues, orchestratorStatus } = useHydra()
  const pipelineWorkers = Object.entries(workers || {}).filter(
    ([, w]) => w.role && w.status !== 'queued'
  )

  // Group by role
  const grouped = {}
  for (const stage of PIPELINE_STAGES) {
    if (!stage.role) continue
    grouped[stage.role] = pipelineWorkers.filter(([, w]) => w.role === stage.role)
  }

  const hasPipelineWorkers = pipelineWorkers.length > 0
  const bgMap = Object.fromEntries((backgroundWorkers || []).map(w => [w.name, w]))
  const hitlCount = hitlItems?.length || 0
  const issues = pipelineIssues || {}

  return (
    <div style={styles.container}>
      <h3 style={styles.heading}>Pipeline</h3>
      <div style={styles.loopRow}>
        {PIPELINE_LOOPS.map((loop) => {
          const state = bgMap[loop.key]
          const enabled = state?.enabled !== false
          const stage = PIPELINE_STAGES.find(s => s.key === loop.key)
          const activeCount = stage?.role ? (grouped[stage.role] || []).length : 0
          const issueCount = (issues[loop.key] || []).length
          return (
            <div key={loop.key} style={styles.loopChip}>
              <span style={{ ...styles.loopDot, background: enabled ? loop.color : loop.dimColor }} />
              <span style={enabled ? styles.loopLabel : styles.loopLabelDim}>{loop.label}</span>
              <span
                style={{ ...styles.loopCount, color: enabled && issueCount > 0 ? loop.color : theme.textMuted }}
                data-testid={`loop-count-${loop.key}`}
              >
                {issueCount}
              </span>
              {activeCount > 0 && (
                <span style={{ ...styles.loopActiveCount, color: loop.color }}>
                  {activeCount} active
                </span>
              )}
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
      {hitlCount > 0 && (
        <div style={styles.hitlBadge}>
          {hitlCount} HITL {hitlCount === 1 ? 'issue' : 'issues'}
        </div>
      )}
      {!hasPipelineWorkers && (
        <div style={styles.empty}>No active pipeline workers</div>
      )}
      {hasPipelineWorkers && (
        <div style={styles.grid}>
          {pipelineWorkers.map(([key, worker]) => (
            <PipelineWorkerCard key={key} workerKey={key} worker={worker} />
          ))}
        </div>
      )}

      <h3 style={{ ...styles.heading, marginTop: 24 }}>Background Workers</h3>
      <div style={styles.grid}>
        {BACKGROUND_WORKERS.map((def) => {
          const state = backgroundWorkers.find(w => w.name === def.key)
          return (
            <BackgroundWorkerCard
              key={def.key}
              def={def}
              state={state}
              pipelinePollerLastRun={pipelinePollerLastRun}
              orchestratorStatus={orchestratorStatus}
              onToggleBgWorker={onToggleBgWorker}
              onViewLog={onViewLog}
            />
          )
        })}
      </div>
    </div>
  )
}

const styles = {
  container: {
    flex: 1,
    overflowY: 'auto',
    padding: 20,
  },
  heading: {
    fontSize: 16,
    fontWeight: 600,
    color: theme.textBright,
    marginBottom: 16,
    marginTop: 0,
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: 16,
  },
  card: {
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    padding: 16,
    background: theme.surface,
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    flexShrink: 0,
  },
  label: {
    fontSize: 14,
    fontWeight: 600,
    color: theme.text,
    flex: 1,
  },
  roleBadge: {
    fontSize: 10,
    fontWeight: 600,
    color: theme.white,
    padding: '1px 6px',
    borderRadius: 4,
    textTransform: 'uppercase',
  },
  status: {
    fontSize: 11,
    fontWeight: 600,
    color: theme.textMuted,
    textTransform: 'uppercase',
  },
  lastRun: {
    fontSize: 12,
    color: theme.textMuted,
    marginBottom: 8,
  },
  workerMeta: {
    marginBottom: 4,
  },
  workerTitle: {
    fontSize: 12,
    color: theme.text,
    marginBottom: 4,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  details: {
    borderTop: `1px solid ${theme.border}`,
    paddingTop: 8,
  },
  detailsError: {
    borderTop: `1px solid ${theme.red}`,
    paddingTop: 8,
    background: theme.redSubtle,
    margin: '0 -16px -16px',
    padding: '8px 16px 16px',
    borderRadius: '0 0 8px 8px',
  },
  detailsErrorCompact: {
    borderTop: `1px solid ${theme.red}`,
    paddingTop: 8,
    background: theme.redSubtle,
    margin: '0 -16px 0',
    padding: '8px 16px',
  },
  detailRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 11,
    padding: '2px 0',
  },
  errorRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 11,
    padding: '2px 0',
  },
  detailKey: {
    color: theme.textMuted,
    textTransform: 'capitalize',
  },
  detailValue: {
    color: theme.text,
    fontWeight: 600,
  },
  detailKeyError: {
    color: theme.red,
    textTransform: 'capitalize',
  },
  detailValueError: {
    color: theme.red,
    fontWeight: 600,
  },
  empty: {
    fontSize: 13,
    color: theme.textMuted,
    padding: '8px 0 16px',
  },
  transcriptSection: {
    borderTop: `1px solid ${theme.border}`,
    paddingTop: 8,
    marginTop: 4,
  },
  transcriptToggle: {
    fontSize: 11,
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
  loopRow: {
    display: 'flex',
    gap: 8,
    flexWrap: 'wrap',
    marginBottom: 16,
  },
  loopChip: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '4px 12px',
    border: `1px solid ${theme.border}`,
    borderRadius: 16,
    background: theme.surface,
  },
  loopDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    flexShrink: 0,
  },
  loopLabel: {
    fontSize: 12,
    fontWeight: 600,
    color: theme.text,
  },
  loopLabelDim: {
    fontSize: 12,
    fontWeight: 600,
    color: theme.textMuted,
  },
  loopCount: {
    fontSize: 10,
    fontWeight: 700,
    minWidth: 16,
    textAlign: 'center',
  },
  loopActiveCount: {
    fontSize: 9,
    fontWeight: 600,
    textTransform: 'uppercase',
  },
  toggleOn: {
    padding: '2px 10px',
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
    padding: '2px 10px',
    fontSize: 10,
    fontWeight: 600,
    border: `1px solid ${theme.border}`,
    borderRadius: 10,
    background: theme.surface,
    color: theme.textMuted,
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  statusPillOk: {
    fontSize: 10,
    fontWeight: 600,
    color: theme.green,
    background: theme.greenSubtle,
    border: `1px solid ${theme.green}`,
    borderRadius: 10,
    padding: '1px 8px',
    textTransform: 'uppercase',
  },
  statusPillError: {
    fontSize: 10,
    fontWeight: 600,
    color: theme.red,
    background: theme.redSubtle,
    border: `1px solid ${theme.red}`,
    borderRadius: 10,
    padding: '1px 8px',
    textTransform: 'uppercase',
  },
  systemBadge: {
    fontSize: 10,
    fontWeight: 600,
    color: theme.textMuted,
    border: `1px solid ${theme.border}`,
    borderRadius: 10,
    padding: '1px 8px',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
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
    marginBottom: 12,
  },
  cardActions: {
    display: 'flex',
    gap: 8,
    paddingTop: 8,
    borderTop: `1px solid ${theme.border}`,
    marginTop: 8,
  },
  viewLogLink: {
    fontSize: 10,
    fontWeight: 600,
    color: theme.accent,
    cursor: 'pointer',
    padding: '3px 8px',
    borderRadius: 4,
    border: `1px solid ${theme.border}`,
    background: 'transparent',
    transition: 'background 0.15s',
  },
}
