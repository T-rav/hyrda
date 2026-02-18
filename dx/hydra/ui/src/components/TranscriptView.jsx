import React, { useEffect, useRef } from 'react'

export function TranscriptView({ workers, selectedWorker }) {
  const containerRef = useRef(null)

  // Auto-scroll to bottom when new lines arrive
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [workers, selectedWorker])

  if (selectedWorker === null || !workers[selectedWorker]) {
    return (
      <div style={styles.container}>
        <div style={styles.empty}>Select a worker to view its transcript</div>
      </div>
    )
  }

  const w = workers[selectedWorker]

  return (
    <div ref={containerRef} style={styles.container}>
      <div style={styles.header}>
        <span style={styles.label}>#{selectedWorker}</span>
        <span style={styles.branch}>{w.branch}</span>
        <span style={styles.lines}>{w.transcript.length} lines</span>
      </div>
      {w.transcript.map((line, i) => (
        <div key={i} style={styles.line}>{line}</div>
      ))}
    </div>
  )
}

const styles = {
  container: {
    flex: 1,
    overflowY: 'auto',
    padding: '12px 16px',
    fontSize: 12,
    lineHeight: 1.6,
  },
  empty: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    color: '#8b949e',
    fontSize: 14,
  },
  header: {
    display: 'flex',
    gap: 12,
    alignItems: 'center',
    padding: '8px 0',
    marginBottom: 8,
    borderBottom: '1px solid #30363d',
  },
  label: { fontWeight: 700, color: '#58a6ff', fontSize: 14 },
  branch: { color: '#8b949e', fontSize: 11 },
  lines: { color: '#8b949e', fontSize: 11, marginLeft: 'auto' },
  line: {
    padding: '1px 0',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
}
