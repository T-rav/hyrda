import React, { useState } from 'react'
import { theme } from '../theme'
import { BACKGROUND_WORKERS, PIPELINE_STAGES, ACTIVE_STATUSES } from '../constants'

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

export function SystemPanel({ workers, backgroundWorkers }) {
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

  return (
    <div style={styles.container}>
      <h3 style={styles.heading}>Pipeline Workers</h3>
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
          const status = state?.status || 'disabled'
          const lastRun = state?.last_run || null
          const details = state?.details || {}

          return (
            <div key={def.key} style={styles.card}>
              <div style={styles.cardHeader}>
                <span
                  style={{ ...styles.dot, background: statusColor(status) }}
                  data-testid={`dot-${def.key}`}
                />
                <span style={styles.label}>{def.label}</span>
                <span style={styles.status}>{status}</span>
              </div>
              <div style={styles.lastRun}>
                Last run: {relativeTime(lastRun)}
              </div>
              {Object.keys(details).length > 0 && (
                <div style={styles.details}>
                  {Object.entries(details).map(([k, v]) => (
                    <div key={k} style={styles.detailRow}>
                      <span style={styles.detailKey}>{k.replace(/_/g, ' ')}</span>
                      <span style={styles.detailValue}>{String(v)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
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
  detailRow: {
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
}
