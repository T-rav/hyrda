import React from 'react'

const phaseColors = {
  idle: '#8b949e',
  fetch: '#58a6ff',
  implement: '#d29922',
  push_prs: '#d18616',
  review: '#d18616',
  merge: '#3fb950',
  cleanup: '#8b949e',
  done: '#3fb950',
}

export function Header({ batchNum, workers, prsCount, mergedCount, phase, connected }) {
  const workerList = Object.values(workers)
  const active = workerList.filter(w => w.status === 'running' || w.status === 'testing').length

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
        <Stat label="Workers" value={`${active}/${workerList.length}`} />
        <Stat label="PRs" value={prsCount} />
        <Stat label="Merged" value={mergedCount} />
      </div>
      <span style={{
        ...styles.badge,
        background: phaseColors[phase] || '#8b949e',
      }}>
        {phase}
      </span>
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
  badge: {
    padding: '4px 12px',
    borderRadius: 12,
    fontSize: 11,
    fontWeight: 600,
    textTransform: 'uppercase',
    color: '#0d1117',
  },
}
