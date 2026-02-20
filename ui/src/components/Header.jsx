import React from 'react'

const STAGES = [
  { key: 'triage',    label: 'TRIAGE',    color: '#39d353', role: 'triage',      configKey: null },
  { key: 'plan',      label: 'PLAN',      color: '#a371f7', role: 'planner',     configKey: 'max_planners' },
  { key: 'implement', label: 'IMPLEMENT', color: '#58a6ff', role: 'implementer', configKey: 'max_workers' },
  { key: 'review',    label: 'REVIEW',    color: '#d18616', role: 'reviewer',    configKey: 'max_reviewers' },
]

const SESSION_STAGES = [
  ...STAGES,
  { key: 'merged', label: 'MERGED', color: '#3fb950' },
]

const ACTIVE_STATUSES = ['running', 'testing', 'committing', 'reviewing', 'planning']

export function Header({
  sessionCounts, connected, orchestratorStatus,
  onStart, onStop, phase, workers, config,
}) {
  const canStart = orchestratorStatus === 'idle' || orchestratorStatus === 'done'
  const isStopping = orchestratorStatus === 'stopping'
  const isRunning = orchestratorStatus === 'running'

  const workerList = Object.values(workers || {})
  const workload = {
    total: workerList.length,
    active: workerList.filter(w => ACTIVE_STATUSES.includes(w.status)).length,
    done: workerList.filter(w => w.status === 'done').length,
    failed: workerList.filter(w => w.status === 'failed').length,
  }

  return (
    <header style={styles.header}>
      <div style={styles.left}>
        <img src="/hydra-logo-small.png" alt="Hydra" style={styles.logoImg} />
        <span style={styles.logo}>
          HYDRA
          <span style={styles.subtitle}>Parallel Issue Processor</span>
        </span>
        <span style={connected ? dotConnected : dotDisconnected} />
      </div>
      <div style={styles.center}>
        <div style={styles.sessionBox}>
          <span style={styles.sessionLabel}>Session</span>
          <div style={styles.sessionPills}>
            {SESSION_STAGES.map((stage, i) => (
              <React.Fragment key={stage.key}>
                {i > 0 && <span style={styles.sessionArrow}>{'\u2192'}</span>}
                <span style={sessionPillStyles[stage.key]}>
                  {stage.label}
                  <span style={styles.sessionCount}>{sessionCounts[stage.key] || 0}</span>
                </span>
              </React.Fragment>
            ))}
          </div>
          <div style={styles.workload}>
            <span>{workload.total} total</span>
            <span style={styles.workloadSep}>|</span>
            <span style={styles.workloadActive}>{workload.active} active</span>
            <span style={styles.workloadSep}>|</span>
            <span style={styles.workloadDone}>{workload.done} done</span>
            <span style={styles.workloadSep}>|</span>
            <span style={styles.workloadFailed}>{workload.failed} failed</span>
          </div>
        </div>
        <div style={styles.pills}>
          {STAGES.map((stage, i) => {
            const maxCount = stage.configKey && config ? config[stage.configKey] : 1
            const lit = isRunning
            return (
              <React.Fragment key={stage.key}>
                {i > 0 && (
                  <div style={headerConnectorStyles[stage.key][lit ? 'lit' : 'dim']} />
                )}
                <div style={pillStyles[stage.key][lit ? 'lit' : 'dim']}>
                  {stage.label}
                  <span style={lit ? countLit : countDim}>{maxCount}</span>
                </div>
              </React.Fragment>
            )
          })}
        </div>
      </div>
      <div style={styles.controls}>
        {canStart && (
          <button
            style={connected ? startBtnEnabled : startBtnDisabled}
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
  left: { display: 'flex', alignItems: 'center', gap: 8 },
  logoImg: { width: 56, height: 56 },
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
    flexWrap: 'wrap',
  },
  sessionLabel: {
    color: '#8b949e',
    fontSize: 11,
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  sessionPills: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    flexWrap: 'wrap',
  },
  sessionPill: {
    padding: '2px 8px',
    borderRadius: 10,
    fontSize: 10,
    fontWeight: 600,
    textTransform: 'uppercase',
    border: '1px solid',
    whiteSpace: 'nowrap',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
  },
  sessionCount: {
    background: 'rgba(0,0,0,0.3)',
    borderRadius: 6,
    padding: '0px 5px',
    fontSize: 9,
    fontWeight: 700,
  },
  sessionArrow: {
    color: '#484f58',
    fontSize: 10,
    margin: '0 1px',
  },
  workload: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 10,
    color: '#8b949e',
  },
  workloadSep: { color: '#30363d' },
  workloadActive: { color: '#58a6ff' },
  workloadDone: { color: '#3fb950' },
  workloadFailed: { color: '#f85149' },
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

// Pre-computed connection dot variants
export const dotConnected = { ...styles.dot, background: '#3fb950' }
export const dotDisconnected = { ...styles.dot, background: '#f85149' }

// Pre-computed per-stage pill/connector variants (avoids object spread in .map())
export const pillStyles = Object.fromEntries(
  STAGES.map(s => [s.key, {
    lit: { ...styles.pill, background: s.color, color: '#0d1117', borderColor: s.color },
    dim: { ...styles.pill, background: s.color + '20', color: s.color + '99', borderColor: s.color + '55' },
  }])
)

export const headerConnectorStyles = Object.fromEntries(
  STAGES.map(s => [s.key, {
    lit: { ...styles.connector, background: s.color },
    dim: { ...styles.connector, background: s.color + '55' },
  }])
)

// Pre-computed session pill styles per stage
export const sessionPillStyles = Object.fromEntries(
  SESSION_STAGES.map(s => [s.key, {
    ...styles.sessionPill,
    background: s.color + '20',
    color: s.color,
    borderColor: s.color + '44',
  }])
)

// Pre-computed count style variants
export const countLit = { ...styles.count, opacity: 1 }
export const countDim = { ...styles.count, opacity: 0.6 }

// Pre-computed start button variants
export const startBtnEnabled = { ...styles.startBtn, opacity: 1, cursor: 'pointer' }
export const startBtnDisabled = { ...styles.startBtn, opacity: 0.4, cursor: 'not-allowed' }
