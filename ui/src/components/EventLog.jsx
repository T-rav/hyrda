import React from 'react'

const typeColors = {
  worker_update: '#58a6ff',
  phase_change: '#d29922',
  pr_created: '#3fb950',
  review_update: '#d18616',
  merge_update: '#3fb950',
  error: '#f85149',
  batch_start: '#58a6ff',
  batch_complete: '#3fb950',
  transcript_line: '#8b949e',
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
            <span style={{ ...styles.type, color: typeColors[e.type] || '#8b949e' }}>
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
    borderLeft: '1px solid #30363d',
    overflowY: 'auto',
    background: '#161b22',
    display: 'flex',
    flexDirection: 'column',
  },
  title: {
    padding: '12px 16px 8px',
    fontSize: 11,
    fontWeight: 600,
    textTransform: 'uppercase',
    color: '#8b949e',
    letterSpacing: 0.5,
  },
  log: { padding: 8, flex: 1, overflowY: 'auto' },
  empty: {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    height: 200, color: '#8b949e', fontSize: 13,
  },
  item: {
    padding: '6px 8px',
    borderBottom: '1px solid #30363d',
    fontSize: 11,
  },
  time: { color: '#8b949e', marginRight: 8 },
  type: { fontWeight: 600, marginRight: 6 },
}
