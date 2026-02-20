import React from 'react'
import { theme } from '../theme'

const STAGES = [
  { key: 'triage',    label: 'TRIAGE',    color: theme.triageGreen, role: 'triage',      configKey: null },
  { key: 'plan',      label: 'PLAN',      color: theme.purple,      role: 'planner',     configKey: 'max_planners' },
  { key: 'implement', label: 'IMPLEMENT', color: theme.accent,      role: 'implementer', configKey: 'max_workers' },
  { key: 'review',    label: 'REVIEW',    color: theme.orange,      role: 'reviewer',    configKey: 'max_reviewers' },
]

const ACTIVE_STATUSES = ['running', 'testing', 'committing', 'reviewing', 'planning']

function countByRole(workers, activeOnly) {
  const list = Object.values(workers)
  const f = activeOnly
    ? (role) => list.filter(w => w.role === role && ACTIVE_STATUSES.includes(w.status)).length
    : (role) => list.filter(w => w.role === role).length
  const implFilter = activeOnly
    ? list.filter(w => w.role !== 'reviewer' && w.role !== 'planner' && w.role !== 'triage' && ACTIVE_STATUSES.includes(w.status)).length
    : list.filter(w => w.role !== 'reviewer' && w.role !== 'planner' && w.role !== 'triage').length
  return {
    triage: f('triage'),
    planner: f('planner'),
    implementer: implFilter,
    reviewer: f('reviewer'),
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
  const activeCounts = countByRole(workers || {}, true)
  const totalCounts = countByRole(workers || {}, false)

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
          <div style={styles.stats}>
            <Stat label="Triage" value={Object.values(workers || {}).filter(w => w.role === 'triage').length} />
            <Stat label="New Issues" value={issuesFound} />
            <Stat label="PRs" value={prsCount} />
            <Stat label="Merged" value={mergedCount} />
          </div>
        </div>
        <div style={styles.pills}>
          {STAGES.map((stage, i) => {
            const activeCount = activeCounts[stage.role] || 0
            const totalCount = totalCounts[stage.role] || 0
            const maxCount = stage.configKey && config ? config[stage.configKey] : 1
            const lit = isRunning
            const dimmed = !isRunning
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
    background: theme.surface,
    borderBottom: `1px solid ${theme.border}`,
  },
  left: { display: 'flex', alignItems: 'center', gap: 8 },
  logoImg: { width: 56, height: 56 },
  logo: { fontSize: 18, fontWeight: 700, color: theme.accent },
  subtitle: { color: theme.textMuted, fontWeight: 400, fontSize: 12, marginLeft: 8 },
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
    border: `1px solid ${theme.border}`,
    borderRadius: 8,
    padding: '6px 14px',
    background: theme.bg,
  },
  sessionLabel: {
    color: theme.textMuted,
    fontSize: 11,
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  stats: { display: 'flex', gap: 16, fontSize: 12 },
  stat: { color: theme.textMuted },
  statVal: { color: theme.text },
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
    background: theme.overlay,
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
    background: theme.btnGreen,
    color: theme.white,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  },
  stopBtn: {
    padding: '4px 14px',
    borderRadius: 6,
    border: 'none',
    background: theme.btnRed,
    color: theme.white,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  },
  stoppingBadge: {
    padding: '4px 12px',
    borderRadius: 6,
    background: theme.yellow,
    color: theme.bg,
    fontSize: 12,
    fontWeight: 600,
  },
}

// Pre-computed connection dot variants
export const dotConnected = { ...styles.dot, background: theme.green }
export const dotDisconnected = { ...styles.dot, background: theme.red }

// Pre-computed per-stage pill/connector variants (avoids object spread in .map())
export const pillStyles = Object.fromEntries(
  STAGES.map(s => [s.key, {
    lit: { ...styles.pill, background: s.color, color: theme.bg, borderColor: s.color },
    dim: { ...styles.pill, background: s.color + '20', color: s.color + '99', borderColor: s.color + '55' },
  }])
)

export const headerConnectorStyles = Object.fromEntries(
  STAGES.map(s => [s.key, {
    lit: { ...styles.connector, background: s.color },
    dim: { ...styles.connector, background: s.color + '55' },
  }])
)

// Pre-computed count style variants
export const countLit = { ...styles.count, opacity: 1 }
export const countDim = { ...styles.count, opacity: 0.6 }

// Pre-computed start button variants
export const startBtnEnabled = { ...styles.startBtn, opacity: 1, cursor: 'pointer' }
export const startBtnDisabled = { ...styles.startBtn, opacity: 0.4, cursor: 'not-allowed' }
