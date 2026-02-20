import React from 'react'
import { theme } from '../theme'
import { BACKGROUND_WORKERS } from '../constants'

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

function statusColor(status) {
  if (status === 'ok') return theme.green
  if (status === 'error') return theme.red
  return theme.textInactive
}

export function SystemPanel({ backgroundWorkers }) {
  return (
    <div style={styles.container}>
      <h3 style={styles.heading}>Background Workers</h3>
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
}
