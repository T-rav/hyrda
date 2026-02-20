import React from 'react'
import { theme } from '../theme'

const typeColors = {
  worker_update: theme.accent,
  phase_change: theme.yellow,
  pr_created: theme.green,
  review_update: theme.orange,
  merge_update: theme.green,
  error: theme.red,
  batch_start: theme.accent,
  batch_complete: theme.green,
  transcript_line: theme.textMuted,
}

function eventSummary(type, data) {
  switch (type) {
    case 'batch_start': return `Batch ${data.batch} started`
    case 'phase_change': return data.phase
    case 'worker_update': return `#${data.issue} \u2192 ${data.status}`
    case 'transcript_line': return `#${data.issue || data.pr}`
    case 'pr_created': return `PR #${data.pr} for #${data.issue}${data.draft ? ' (draft)' : ''}`
    case 'review_update': return `PR #${data.pr} \u2192 ${data.verdict || data.status}`
    case 'merge_update': return `PR #${data.pr} ${data.status}`
    case 'batch_complete': return `${data.merged} merged, ${data.implemented} implemented`
    case 'error': return data.message || 'Error'
    default: return JSON.stringify(data).slice(0, 80)
  }
}

export function EventLog({ events }) {
  // Filter out noisy transcript_line events from the log
  const filtered = events.filter(e => e.type !== 'transcript_line')

  return (
    <div style={styles.panel}>
      <div style={styles.title}>Event Log</div>
      <div style={styles.log}>
        {filtered.length === 0 && (
          <div style={styles.empty}>Waiting for events...</div>
        )}
        {filtered.map((e, i) => (
          <div key={i} style={styles.item}>
            <span style={styles.time}>
              {new Date(e.timestamp).toLocaleTimeString()}
            </span>
            <span style={{ ...styles.type, color: typeColors[e.type] || theme.textMuted }}>
              {e.type.replace(/_/g, ' ')}
            </span>
            <span>{eventSummary(e.type, e.data)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

const styles = {
  panel: {
    borderLeft: `1px solid ${theme.border}`,
    overflowY: 'auto',
    background: theme.surface,
    display: 'flex',
    flexDirection: 'column',
  },
  title: {
    padding: '12px 16px 8px',
    fontSize: 11,
    fontWeight: 600,
    textTransform: 'uppercase',
    color: theme.textMuted,
    letterSpacing: 0.5,
  },
  log: { padding: 8, flex: 1, overflowY: 'auto' },
  empty: {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    height: 200, color: theme.textMuted, fontSize: 13,
  },
  item: {
    padding: '6px 8px',
    borderBottom: `1px solid ${theme.border}`,
    fontSize: 11,
  },
  time: { color: theme.textMuted, marginRight: 8 },
  type: { fontWeight: 600, marginRight: 6 },
}
