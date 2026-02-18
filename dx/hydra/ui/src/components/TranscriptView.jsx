import React, { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const ACTIVE_STATUSES = ['running', 'testing', 'committing', 'reviewing', 'planning']

export function TranscriptView({ workers, selectedWorker }) {
  const containerRef = useRef(null)

  // Auto-scroll to bottom when new lines arrive
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [workers, selectedWorker])

  // Single worker selected — show its transcript
  if (selectedWorker !== null && workers[selectedWorker]) {
    const w = workers[selectedWorker]
    return (
      <div ref={containerRef} style={styles.container}>
        <div style={styles.header}>
          <span style={styles.label}>#{selectedWorker}</span>
          <span style={styles.role}>{w.role}</span>
          <span style={styles.branch}>{w.branch}</span>
          <span style={styles.lines}>{w.transcript.length} lines</span>
        </div>
        {w.transcript.length === 0 ? (
          <div style={styles.waiting}>Waiting for output...</div>
        ) : (
          w.transcript.map((line, i) => (
            <div key={i} style={styles.line}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>{line}</ReactMarkdown>
            </div>
          ))
        )}
      </div>
    )
  }

  // No worker selected — show combined feed from all active workers
  const allLines = []
  for (const [key, w] of Object.entries(workers)) {
    for (const line of w.transcript) {
      allLines.push({ key, role: w.role, line })
    }
  }

  if (allLines.length === 0) {
    return (
      <div style={styles.container}>
        <div style={styles.empty}>Waiting for transcript output...</div>
      </div>
    )
  }

  return (
    <div ref={containerRef} style={styles.container}>
      <div style={styles.header}>
        <span style={styles.label}>All Workers</span>
        <span style={styles.lines}>{allLines.length} lines</span>
      </div>
      {allLines.map((item, i) => (
        <div key={i} style={styles.line}>
          <span style={styles.linePrefix}>[{item.role} #{item.key}]</span>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>{item.line}</ReactMarkdown>
        </div>
      ))}
    </div>
  )
}

const mdComponents = {
  h1: ({ children }) => <h1 style={{ fontSize: 16, fontWeight: 700, color: '#e6edf3', margin: '8px 0 4px' }}>{children}</h1>,
  h2: ({ children }) => <h2 style={{ fontSize: 14, fontWeight: 700, color: '#e6edf3', margin: '6px 0 3px' }}>{children}</h2>,
  h3: ({ children }) => <h3 style={{ fontSize: 13, fontWeight: 600, color: '#e6edf3', margin: '4px 0 2px' }}>{children}</h3>,
  code: ({ inline, children }) =>
    inline
      ? <code style={{ background: '#161b22', padding: '2px 5px', borderRadius: 4, fontSize: 11, color: '#79c0ff' }}>{children}</code>
      : <pre style={{ background: '#161b22', padding: 8, borderRadius: 6, overflowX: 'auto', fontSize: 11, lineHeight: 1.5, margin: '4px 0' }}><code style={{ color: '#e6edf3' }}>{children}</code></pre>,
  ul: ({ children }) => <ul style={{ margin: '2px 0', paddingLeft: 20 }}>{children}</ul>,
  ol: ({ children }) => <ol style={{ margin: '2px 0', paddingLeft: 20 }}>{children}</ol>,
  li: ({ children }) => <li style={{ margin: '1px 0' }}>{children}</li>,
  strong: ({ children }) => <strong style={{ color: '#e6edf3' }}>{children}</strong>,
  p: ({ children }) => <p style={{ margin: '2px 0' }}>{children}</p>,
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
  waiting: {
    color: '#8b949e',
    padding: '20px 0',
    fontStyle: 'italic',
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
  role: { color: '#a371f7', fontSize: 11, fontWeight: 600 },
  branch: { color: '#8b949e', fontSize: 11 },
  lines: { color: '#8b949e', fontSize: 11, marginLeft: 'auto' },
  line: {
    padding: '1px 0',
    wordBreak: 'break-word',
  },
  linePrefix: {
    color: '#58a6ff',
    fontWeight: 600,
    fontSize: 11,
  },
}
