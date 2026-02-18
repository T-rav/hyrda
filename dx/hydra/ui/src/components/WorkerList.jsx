import React from 'react'

const statusColors = {
  queued:     { bg: 'rgba(139,148,158,0.15)', fg: '#8b949e' },
  running:    { bg: 'rgba(88,166,255,0.15)',  fg: '#58a6ff' },
  testing:    { bg: 'rgba(210,153,34,0.15)',  fg: '#d29922' },
  committing: { bg: 'rgba(210,134,22,0.15)',  fg: '#d18616' },
  done:       { bg: 'rgba(63,185,80,0.15)',   fg: '#3fb950' },
  failed:     { bg: 'rgba(248,81,73,0.15)',   fg: '#f85149' },
}

export function WorkerList({ workers, selectedWorker, onSelect }) {
  const sorted = Object.entries(workers).sort((a, b) => Number(a[0]) - Number(b[0]))

  if (sorted.length === 0) {
    return (
      <div style={styles.sidebar}>
        <div style={styles.title}>Workers</div>
        <div style={styles.empty}>Waiting for issues...</div>
      </div>
    )
  }

  return (
    <div style={styles.sidebar}>
      <div style={styles.title}>Workers</div>
      {sorted.map(([num, w]) => {
        const isActive = selectedWorker === Number(num)
        const sc = statusColors[w.status] || statusColors.queued
        return (
          <div
            key={num}
            onClick={() => onSelect(Number(num))}
            style={{
              ...styles.card,
              ...(isActive ? styles.active : {}),
            }}
          >
            <div style={styles.cardHeader}>
              <span style={styles.issue}>#{num}</span>
              <span style={{ ...styles.status, background: sc.bg, color: sc.fg }}>
                {w.status}
              </span>
            </div>
            <div style={styles.cardTitle}>{w.title}</div>
            <div style={styles.meta}>{w.branch} &middot; W{w.worker}</div>
          </div>
        )
      })}
    </div>
  )
}

const styles = {
  sidebar: {
    borderRight: '1px solid #30363d',
    overflowY: 'auto',
    background: '#161b22',
  },
  title: {
    padding: '12px 16px 8px',
    fontSize: 11,
    fontWeight: 600,
    textTransform: 'uppercase',
    color: '#8b949e',
    letterSpacing: 0.5,
  },
  empty: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: 200,
    color: '#8b949e',
    fontSize: 13,
  },
  card: {
    padding: '10px 16px',
    borderBottom: '1px solid #30363d',
    cursor: 'pointer',
    transition: 'background 0.15s',
  },
  active: {
    background: 'rgba(88,166,255,0.08)',
    borderLeft: '3px solid #58a6ff',
    paddingLeft: 13,
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  issue: { fontWeight: 600, color: '#c9d1d9' },
  status: {
    fontSize: 11,
    padding: '2px 8px',
    borderRadius: 8,
    fontWeight: 600,
  },
  cardTitle: {
    fontSize: 12,
    color: '#8b949e',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  meta: { fontSize: 11, color: '#8b949e', marginTop: 4 },
}
