import React from 'react'

export function Header({
  batchNum, prsCount, mergedCount,
  connected, orchestratorStatus,
  onStart, onStop, lifetimeStats,
}) {
  const canStart = orchestratorStatus === 'idle' || orchestratorStatus === 'done'
  const isStopping = orchestratorStatus === 'stopping'
  const isRunning = orchestratorStatus === 'running'

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
      <div style={styles.stats}>
        <Stat label="Batch" value={batchNum} />
        <Stat label="PRs" value={prsCount} />
        <Stat label="Merged" value={mergedCount} />
        {lifetimeStats && (<>
          <Stat label="Fixed" value={lifetimeStats.issues_completed} />
          <Stat label="Filed" value={lifetimeStats.issues_created} />
        </>)}
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
  stats: { display: 'flex', gap: 20, fontSize: 12 },
  stat: { color: '#8b949e' },
  statVal: { color: '#c9d1d9' },
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
