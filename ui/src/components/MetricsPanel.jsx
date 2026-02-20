import React from 'react'
import { theme } from '../theme'

export function MetricsPanel({ metrics, lifetimeStats }) {
  const lifetime = metrics?.lifetime || lifetimeStats || {}
  const rates = metrics?.rates || {}

  const cards = [
    { label: 'Issues Completed', value: lifetime.issues_completed ?? 0 },
    { label: 'PRs Merged', value: lifetime.prs_merged ?? 0 },
    { label: 'Issues Created', value: lifetime.issues_created ?? 0 },
  ]

  const rateCards = Object.entries(rates).map(([key, value]) => ({
    label: key.replace(/_/g, ' '),
    value: `${(value * 100).toFixed(0)}%`,
  }))

  return (
    <div style={styles.container}>
      <h3 style={styles.heading}>Lifetime Stats</h3>
      <div style={styles.row}>
        {cards.map((card) => (
          <div key={card.label} style={styles.card}>
            <div style={styles.value}>{card.value}</div>
            <div style={styles.label}>{card.label}</div>
          </div>
        ))}
      </div>

      {rateCards.length > 0 && (
        <>
          <h3 style={styles.heading}>Rates</h3>
          <div style={styles.row}>
            {rateCards.map((card) => (
              <div key={card.label} style={styles.card}>
                <div style={styles.value}>{card.value}</div>
                <div style={styles.label}>{card.label}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {!metrics && !lifetimeStats && (
        <div style={styles.empty}>No metrics data available yet.</div>
      )}
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
  row: {
    display: 'flex',
    gap: 16,
    marginBottom: 24,
    flexWrap: 'wrap',
  },
  card: {
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    padding: 20,
    background: theme.surface,
    minWidth: 140,
    textAlign: 'center',
  },
  value: {
    fontSize: 32,
    fontWeight: 700,
    color: theme.textBright,
    marginBottom: 4,
  },
  label: {
    fontSize: 12,
    color: theme.textMuted,
    textTransform: 'capitalize',
  },
  empty: {
    fontSize: 13,
    color: theme.textMuted,
    padding: 20,
  },
}
