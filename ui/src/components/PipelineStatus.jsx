import React from 'react'

const STAGES = [
  { key: 'plan',      label: 'Plan',      color: '#a371f7', role: 'planner' },
  { key: 'implement', label: 'Implement', color: '#d29922', role: 'implementer' },
  { key: 'review',    label: 'Review',    color: '#d18616', role: 'reviewer' },
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
              <div style={connectorStyles[stage.key][isActive ? 'active' : 'inactive']} />
            )}
            <div style={styles.stageWrapper}>
              <div style={stageStyles[stage.key][isActive ? 'active' : 'inactive']}>
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
    background: '#0d1117',
    borderBottom: '1px solid #30363d',
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
    background: 'rgba(0,0,0,0.3)',
    borderRadius: 8,
    padding: '1px 6px',
    fontSize: 10,
    fontWeight: 700,
  },
}

// Pre-computed per-stage active/inactive style variants (avoids object spread in .map())
export const connectorStyles = Object.fromEntries(
  STAGES.map(s => [s.key, {
    active: { ...styles.connector, background: s.color },
    inactive: { ...styles.connector, background: '#30363d' },
  }])
)

export const stageStyles = Object.fromEntries(
  STAGES.map(s => [s.key, {
    active: { ...styles.stage, background: s.color, color: '#0d1117', borderColor: s.color },
    inactive: { ...styles.stage, background: '#21262d', color: '#484f58', borderColor: '#30363d' },
  }])
)
