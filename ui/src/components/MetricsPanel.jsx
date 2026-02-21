import React from 'react'
import { theme } from '../theme'
import { PIPELINE_STAGES } from '../constants'

const BLOCK_LABELS = [
  { key: 'hydra-plan',   label: 'Plan',   stage: 'plan' },
  { key: 'hydra-ready',  label: 'Ready',  stage: 'implement' },
  { key: 'hydra-review', label: 'Review', stage: 'review' },
  { key: 'hydra-hitl',   label: 'HITL',   stage: 'review' },
  { key: 'hydra-fixed',  label: 'Fixed',  stage: 'merged' },
]

function stageColor(stageKey) {
  const stage = PIPELINE_STAGES.find(s => s.key === stageKey)
  return stage?.color || theme.textMuted
}

function StatCard({ label, value, subtle }) {
  return (
    <div style={subtle ? styles.cardSubtle : styles.card}>
      <div style={styles.value}>{value}</div>
      <div style={styles.label}>{label}</div>
    </div>
  )
}

function BlocksRow({ labelDef, count }) {
  const color = stageColor(labelDef.stage)
  const blocks = Array.from({ length: count }, (_, i) => i)

  return (
    <div style={styles.blocksRow}>
      <div style={styles.blocksLabel}>{labelDef.label}</div>
      <div style={styles.blocksContainer}>
        {blocks.length === 0 && (
          <span style={styles.blocksEmpty}>0</span>
        )}
        {blocks.map(i => (
          <div
            key={i}
            style={{ ...styles.block, background: color }}
            title={`${labelDef.label} issue`}
          />
        ))}
      </div>
      <span style={styles.blocksCount}>{count}</span>
    </div>
  )
}

export function MetricsPanel({ metrics, lifetimeStats, githubMetrics, sessionCounts }) {
  const session = sessionCounts || {}
  const github = githubMetrics || {}
  const openByLabel = github.open_by_label || {}
  const lifetime = metrics?.lifetime || lifetimeStats || {}

  const hasGithub = githubMetrics !== null && githubMetrics !== undefined
  const hasSession = session.triaged > 0 || session.planned > 0 ||
    session.implemented > 0 || session.reviewed > 0 || session.merged > 0
  const hasLifetime = hasGithub || lifetime.issues_completed > 0 ||
    lifetime.prs_merged > 0

  if (!hasGithub && !hasSession && !hasLifetime) {
    return (
      <div style={styles.container}>
        <div style={styles.empty}>No metrics data available yet.</div>
      </div>
    )
  }

  return (
    <div style={styles.container}>
      <h3 style={styles.heading}>Lifetime</h3>
      <div style={styles.row}>
        <StatCard
          label="Issues Completed"
          value={github.total_closed ?? lifetime.issues_completed ?? 0}
        />
        <StatCard
          label="PRs Merged"
          value={github.total_merged ?? lifetime.prs_merged ?? 0}
        />
        {hasGithub && (
          <StatCard
            label="Open Issues"
            value={Object.values(openByLabel).reduce((a, b) => a + b, 0)}
          />
        )}
      </div>

      {hasSession && (
        <>
          <h3 style={styles.heading}>Session</h3>
          <div style={styles.row}>
            <StatCard label="Triaged" value={session.triaged || 0} subtle />
            <StatCard label="Planned" value={session.planned || 0} subtle />
            <StatCard label="Implemented" value={session.implemented || 0} subtle />
            <StatCard label="Reviewed" value={session.reviewed || 0} subtle />
            <StatCard label="Merged" value={session.merged || 0} subtle />
          </div>
        </>
      )}

      {hasGithub && (
        <>
          <h3 style={styles.heading}>Pipeline</h3>
          <div style={styles.blocksSection}>
            {BLOCK_LABELS.map(def => (
              <BlocksRow
                key={def.key}
                labelDef={def}
                count={openByLabel[def.key] || 0}
              />
            ))}
          </div>
        </>
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
  cardSubtle: {
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    padding: 16,
    background: theme.surfaceInset,
    minWidth: 100,
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
  blocksSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    marginBottom: 24,
  },
  blocksRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
  },
  blocksLabel: {
    width: 60,
    fontSize: 12,
    fontWeight: 600,
    color: theme.textMuted,
    flexShrink: 0,
  },
  blocksContainer: {
    display: 'flex',
    gap: 4,
    flexWrap: 'wrap',
    flex: 1,
    minHeight: 16,
    alignItems: 'center',
  },
  block: {
    width: 16,
    height: 16,
    borderRadius: 3,
    transition: 'all 0.3s ease',
  },
  blocksCount: {
    fontSize: 12,
    fontWeight: 600,
    color: theme.textMuted,
    width: 24,
    textAlign: 'right',
    flexShrink: 0,
  },
  blocksEmpty: {
    fontSize: 11,
    color: theme.textInactive,
  },
}
