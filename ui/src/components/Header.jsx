import React from 'react'

const STAGES = [
  { key: 'triage',    label: 'TRIAGE',    color: '#39d353', role: 'triage',      configKey: null },
  { key: 'plan',      label: 'PLAN',      color: '#a371f7', role: 'planner',     configKey: 'max_planners' },
  { key: 'implement', label: 'IMPLEMENT', color: '#58a6ff', role: 'implementer', configKey: 'max_workers' },
  { key: 'review',    label: 'REVIEW',    color: '#d18616', role: 'reviewer',    configKey: 'max_reviewers' },
]

const ACTIVE_STATUSES = ['running', 'testing', 'committing', 'reviewing', 'planning']

function countByRole(workers) {
  const list = Object.values(workers)
  return {
    triage: list.filter(w => w.role === 'triage').length,
    planner: list.filter(w => w.role === 'planner').length,
    implementer: list.filter(w => w.role !== 'reviewer' && w.role !== 'planner' && w.role !== 'triage').length,
    reviewer: list.filter(w => w.role === 'reviewer').length,
  }
}

export function Header({
  prsCount, mergedCount, issuesFound,
  connected, orchestratorStatus,
  onStart, onStop,
  phase, workers, config,
}) {
  const canStart = orchestratorStatus === 'idle' || orchestratorStatus === 'done'
  const isStopping = orchestratorStatus === 'stopping'
  const isRunning = orchestratorStatus === 'running'
  const counts = countByRole(workers || {})

  return (
    <header style={styles.header}>
      <div style={styles.left}>
        <span style={styles.logo}>
          HYDRA
          <span style={styles.subtitle}>Parallel Issue Processor</span>
        </span>
        <span style={{
          ...styles.dot,
          background: connected ? '#3fb950' : '#f85149',
        }} />
      </div>
      <div style={styles.center}>
        <div style={styles.sessionBox}>
          <span style={styles.sessionLabel}>Session</span>
          <div style={styles.stats}>
            <Stat label="Triage" value={Object.values(workers || {}).filter(w => w.role === 'triage').length} />
            <Stat label="New Issues" value={issuesFound} />
            <Stat label="PRs" value={prsCount} />
            <Stat label="Merged" value={mergedCount} />
          </div>
        </div>
        <div style={styles.pills}>
          {STAGES.map((stage, i) => {
            const agentCount = counts[stage.role] || 0
            const maxCount = stage.configKey && config ? config[stage.configKey] : 1
            const lit = isRunning || agentCount > 0
            return (
              <React.Fragment key={stage.key}>
                {i > 0 && (
                  <div style={{
                    ...styles.connector,
                    background: lit ? stage.color : '#30363d',
                  }} />
                )}
                <div style={{
                  ...styles.pill,
                  background: lit ? stage.color : '#21262d',
                  color: lit ? '#0d1117' : '#484f58',
                  borderColor: lit ? stage.color : '#30363d',
                }}>
                  {stage.label}
                  {lit && (
                    <span style={styles.count}>{agentCount}/{maxCount}</span>
                  )}
                </div>
              </React.Fragment>
            )
          })}
        </div>
      </div>
      <div style={styles.controls}>
        {canStart && (
          <button
            style={{
              ...styles.startBtn,
              opacity: connected ? 1 : 0.4,
              cursor: connected ? 'pointer' : 'not-allowed',
            }}
            onClick={onStart}
            disabled={!connected}
          >
            Start
          </button>
        )}
        {isRunning && (
          <button style={styles.stopBtn} onClick={onStop}>
            Stop
          </button>
        )}
        {isStopping && (
          <span style={styles.stoppingBadge}>
            Stopping…
          </span>
        )}
      </div>
    </header>
  )
}

function Stat({ label, value }) {
  return (
    <span style={styles.stat}>
      {label} <b style={styles.statVal}>{value}</b>
    </span>
  )
}

const styles = {
  header: {
    gridColumn: '1 / -1',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 20px',
    background: '#161b22',
    borderBottom: '1px solid #30363d',
  },
  left: { display: 'flex', alignItems: 'center', gap: 10 },
  logo: { fontSize: 18, fontWeight: 700, color: '#58a6ff' },
  subtitle: { color: '#8b949e', fontWeight: 400, fontSize: 12, marginLeft: 8 },
  dot: { width: 8, height: 8, borderRadius: '50%', display: 'inline-block' },
  center: {
    display: 'flex',
    alignItems: 'center',
    gap: 14,
  },
  sessionBox: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    border: '1px solid #30363d',
    borderRadius: 8,
    padding: '6px 14px',
    background: '#0d1117',
  },
  sessionLabel: {
    color: '#8b949e',
    fontSize: 11,
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  stats: { display: 'flex', gap: 16, fontSize: 12 },
  stat: { color: '#8b949e' },
  statVal: { color: '#c9d1d9' },
  pills: { display: 'flex', alignItems: 'center', gap: 0 },
  pill: {
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
    width: 24,
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
  controls: { display: 'flex', alignItems: 'center', gap: 10 },
  startBtn: {
    padding: '4px 14px',
    borderRadius: 6,
    border: 'none',
    background: '#238636',
    color: '#ffffff',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  },
  stopBtn: {
    padding: '4px 14px',
    borderRadius: 6,
    border: 'none',
    background: '#da3633',
    color: '#ffffff',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  },
  stoppingBadge: {
    padding: '4px 12px',
    borderRadius: 6,
    background: '#d29922',
    color: '#0d1117',
    fontSize: 12,
    fontWeight: 600,
  },
}
