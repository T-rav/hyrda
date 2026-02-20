import React from 'react'
import { theme } from '../theme'

const STAGES = [
  { key: 'plan',      label: 'Plan',      color: theme.purple, role: 'planner' },
  { key: 'implement', label: 'Implement', color: theme.yellow, role: 'implementer' },
  { key: 'review',    label: 'Review',    color: theme.orange, role: 'reviewer' },
]

const ACTIVE_STATUSES = ['running', 'testing', 'committing', 'reviewing', 'planning']

function countByRole(workers) {
  const list = Object.values(workers)
  const active = list.filter(w => ACTIVE_STATUSES.includes(w.status))
  return {
    planner: active.filter(w => w.role === 'planner').length,
    implementer: active.filter(w => w.role !== 'reviewer' && w.role !== 'planner').length,
    reviewer: active.filter(w => w.role === 'reviewer').length,
  }
}

export function PipelineStatus({ phase, workers }) {
  const workerList = Object.values(workers)
  const counts = countByRole(workers)
  // Don't render when idle with no history
  if (phase === 'idle' && workerList.length === 0) return null

  return (
    <div style={styles.container}>
      {STAGES.map((stage, i) => {
        const agentCount = stage.role ? (counts[stage.role] || 0) : 0
        const isActive = agentCount > 0

        return (
          <React.Fragment key={stage.key}>
            {i > 0 && (
              <div style={{
                ...styles.connector,
                background: isActive ? stage.color : theme.border,
              }} />
            )}
            <div style={styles.stageWrapper}>
              <div style={{
                ...styles.stage,
                background: isActive ? stage.color : theme.surfaceInset,
                color: isActive ? theme.bg : theme.textInactive,
                borderColor: isActive ? stage.color : theme.border,
              }}>
                {stage.label}
                {agentCount > 0 && (
                  <span style={styles.count}>{agentCount}</span>
                )}
              </div>
            </div>
          </React.Fragment>
        )
      })}
    </div>
  )
}

const styles = {
  container: {
    gridColumn: '1 / -1',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '10px 20px',
    background: theme.bg,
    borderBottom: `1px solid ${theme.border}`,
    gap: 0,
  },
  stageWrapper: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 4,
  },
  stage: {
    padding: '4px 14px',
    borderRadius: 12,
    fontSize: 11,
    fontWeight: 600,
    textTransform: 'uppercase',
    border: '1px solid',
    whiteSpace: 'nowrap',
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  },
  connector: {
    width: 32,
    height: 2,
    flexShrink: 0,
  },
  count: {
    background: theme.overlay,
    borderRadius: 8,
    padding: '1px 6px',
    fontSize: 10,
    fontWeight: 700,
  },
}
