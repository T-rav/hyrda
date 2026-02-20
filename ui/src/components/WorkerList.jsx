import React, { useState } from 'react'

const statusColors = {
  queued:     { bg: 'rgba(139,148,158,0.15)', fg: '#8b949e' },
  running:    { bg: 'rgba(88,166,255,0.15)',  fg: '#58a6ff' },
  planning:   { bg: 'rgba(163,113,247,0.15)', fg: '#a371f7' },
  testing:    { bg: 'rgba(210,153,34,0.15)',  fg: '#d29922' },
  committing: { bg: 'rgba(210,134,22,0.15)',  fg: '#d18616' },
  done:       { bg: 'rgba(63,185,80,0.15)',   fg: '#3fb950' },
  failed:     { bg: 'rgba(248,81,73,0.15)',   fg: '#f85149' },
}

const ACTIVE_STATUSES = ['running', 'testing', 'committing', 'reviewing', 'planning']

export function WorkerList({ workers, selectedWorker, onSelect, humanInputRequests = {} }) {
  const allEntries = Object.entries(workers)
  const triagers = allEntries.filter(([, w]) => w.role === 'triage')
  const planners = allEntries.filter(([, w]) => w.role === 'planner')
  const implementers = allEntries.filter(([, w]) => w.role !== 'reviewer' && w.role !== 'planner' && w.role !== 'triage')
  const reviewers = allEntries.filter(([, w]) => w.role === 'reviewer')

  return (
    <div style={styles.sidebar}>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
      <RoleSection
        label="Triage"
        entries={triagers}
        selectedWorker={selectedWorker}
        onSelect={onSelect}
        humanInputRequests={humanInputRequests}
      />
      <RoleSection
        label="Planners"
        entries={planners}
        selectedWorker={selectedWorker}
        onSelect={onSelect}
        humanInputRequests={humanInputRequests}
      />
      <RoleSection
        label="Implementers"
        entries={implementers}
        selectedWorker={selectedWorker}
        onSelect={onSelect}
        humanInputRequests={humanInputRequests}
      />
      <RoleSection
        label="Reviewers"
        entries={reviewers}
        selectedWorker={selectedWorker}
        onSelect={onSelect}
        humanInputRequests={humanInputRequests}
      />
    </div>
  )
}

function RoleSection({ label, entries, selectedWorker, onSelect, humanInputRequests }) {
  const [collapsed, setCollapsed] = useState(false)
  const sorted = [...entries].sort((a, b) => {
    // Sort numerically where possible, string keys (review-*) at end
    const na = parseInt(a[0], 10)
    const nb = parseInt(b[0], 10)
    if (isNaN(na) && isNaN(nb)) return a[0].localeCompare(b[0])
    if (isNaN(na)) return 1
    if (isNaN(nb)) return -1
    return na - nb
  })

  const active = entries.filter(([, w]) => ACTIVE_STATUSES.includes(w.status)).length
  const total = entries.length

  return (
    <>
      <div
        style={styles.sectionHeader}
        onClick={() => setCollapsed(!collapsed)}
      >
        <span style={styles.chevron}>{collapsed ? '\u25b6' : '\u25bc'}</span>
        <span style={styles.sectionLabel}>{label}</span>
        <span style={styles.sectionCount}>{active}/{total}</span>
      </div>
      {!collapsed && sorted.map(([num, w]) => {
        const isActive = selectedWorker === num || selectedWorker === Number(num)
        const sc = statusColors[w.status] || statusColors.queued
        // Check if this worker has a pending human input request
        const issueNum = typeof num === 'string' && num.startsWith('review-') ? null : Number(num)
        const hasPendingInput = issueNum != null && humanInputRequests[issueNum]

        return (
          <div
            key={num}
            onClick={() => onSelect(isNaN(Number(num)) ? num : Number(num))}
            style={isActive ? cardActiveStyle : cardStyle}
          >
            <div style={styles.cardHeader}>
              <span style={styles.issue}>
                {hasPendingInput && <span style={styles.inputDot} />}
                #{num}
              </span>
              <span style={statusBadgeStyles[w.status] || statusBadgeStyles.queued}>
                {w.status}
              </span>
            </div>
            <div style={styles.cardTitle}>{w.title}</div>
            <div style={styles.meta}>
              {w.branch ? `${w.branch} \u00b7 ` : ''}W{w.worker}
            </div>
          </div>
        )
      })}
    </>
  )
}

const styles = {
  sidebar: {
    borderRight: '1px solid #30363d',
    overflowY: 'auto',
    background: '#161b22',
  },
  sectionHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '10px 16px 6px',
    cursor: 'pointer',
    userSelect: 'none',
  },
  chevron: {
    fontSize: 9,
    color: '#8b949e',
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: 'uppercase',
    color: '#8b949e',
    letterSpacing: 0.5,
  },
  sectionCount: {
    fontSize: 11,
    color: '#58a6ff',
    fontWeight: 600,
    marginLeft: 'auto',
  },
  card: {
    padding: '10px 16px',
    borderBottom: '1px solid #30363d',
    borderLeft: '3px solid #484f58',
    paddingLeft: 13,
    cursor: 'pointer',
    transition: 'background 0.15s, border-left-color 0.15s',
  },
  active: {
    background: 'rgba(88,166,255,0.08)',
    borderLeft: '3px solid #58a6ff',
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  issue: {
    fontWeight: 600,
    color: '#c9d1d9',
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  },
  inputDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: '#d29922',
    display: 'inline-block',
    animation: 'pulse 1.5s ease-in-out infinite',
  },
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

// Pre-computed card style variants (avoids object spread in .map())
export const cardStyle = styles.card
export const cardActiveStyle = { ...styles.card, ...styles.active }

// Pre-computed status badge styles for each known status
export const statusBadgeStyles = Object.fromEntries(
  Object.entries(statusColors).map(([k, v]) => [
    k, { ...styles.status, background: v.bg, color: v.fg }
  ])
)
