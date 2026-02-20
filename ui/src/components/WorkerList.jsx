import React, { useState } from 'react'
import { theme } from '../theme'
import { ACTIVE_STATUSES } from '../constants'

const statusColors = {
  queued:     { bg: theme.mutedSubtle,  fg: theme.textMuted },
  running:    { bg: theme.accentSubtle, fg: theme.accent },
  planning:   { bg: theme.purpleSubtle, fg: theme.purple },
  testing:    { bg: theme.yellowSubtle, fg: theme.yellow },
  committing:  { bg: theme.orangeSubtle, fg: theme.orange },
  quality_fix: { bg: theme.yellowSubtle, fg: theme.yellow },
  reviewing:   { bg: theme.orangeSubtle, fg: theme.orange },
  start:       { bg: theme.orangeSubtle, fg: theme.orange },
  done:        { bg: theme.greenSubtle,  fg: theme.green },
  failed:     { bg: theme.redSubtle,    fg: theme.red },
}

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
    borderRight: `1px solid ${theme.border}`,
    overflowY: 'auto',
    background: theme.surface,
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
    color: theme.textMuted,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: 'uppercase',
    color: theme.textMuted,
    letterSpacing: 0.5,
  },
  sectionCount: {
    fontSize: 11,
    color: theme.accent,
    fontWeight: 600,
    marginLeft: 'auto',
  },
  card: {
    padding: '10px 16px',
    borderBottom: `1px solid ${theme.border}`,
    borderLeft: `3px solid ${theme.textInactive}`,
    paddingLeft: 13,
    cursor: 'pointer',
    transition: 'background 0.15s, border-left-color 0.15s',
  },
  active: {
    background: theme.accentHover,
    borderLeft: `3px solid ${theme.accent}`,
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  issue: {
    fontWeight: 600,
    color: theme.text,
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  },
  inputDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: theme.yellow,
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
    color: theme.textMuted,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  meta: { fontSize: 11, color: theme.textMuted, marginTop: 4 },
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
