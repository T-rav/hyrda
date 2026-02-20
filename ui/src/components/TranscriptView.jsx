import React, { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { theme } from '../theme'

const ACTIVE_STATUSES = ['running', 'testing', 'committing', 'reviewing', 'planning', 'evaluating', 'quality_fix']

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

const mdStyles = {
  h1: { fontSize: 16, fontWeight: 700, color: theme.textBright, margin: '8px 0 4px' },
  h2: { fontSize: 14, fontWeight: 700, color: theme.textBright, margin: '6px 0 3px' },
  h3: { fontSize: 13, fontWeight: 600, color: theme.textBright, margin: '4px 0 2px' },
  inlineCode: { background: theme.surface, padding: '2px 5px', borderRadius: 4, fontSize: 11, color: theme.codeText },
  pre: { background: theme.surface, padding: 8, borderRadius: 6, overflowX: 'auto', fontSize: 11, lineHeight: 1.5, margin: '4px 0' },
  codeBlock: { color: theme.textBright },
  ul: { margin: '2px 0', paddingLeft: 20 },
  ol: { margin: '2px 0', paddingLeft: 20 },
  li: { margin: '1px 0' },
  strong: { color: theme.textBright },
  p: { margin: '2px 0' },
}

const mdComponents = {
  h1: ({ children }) => <h1 style={mdStyles.h1}>{children}</h1>,
  h2: ({ children }) => <h2 style={mdStyles.h2}>{children}</h2>,
  h3: ({ children }) => <h3 style={mdStyles.h3}>{children}</h3>,
  code: ({ inline, children }) =>
    inline
      ? <code style={mdStyles.inlineCode}>{children}</code>
      : <pre style={mdStyles.pre}><code style={mdStyles.codeBlock}>{children}</code></pre>,
  ul: ({ children }) => <ul style={mdStyles.ul}>{children}</ul>,
  ol: ({ children }) => <ol style={mdStyles.ol}>{children}</ol>,
  li: ({ children }) => <li style={mdStyles.li}>{children}</li>,
  strong: ({ children }) => <strong style={mdStyles.strong}>{children}</strong>,
  p: ({ children }) => <p style={mdStyles.p}>{children}</p>,
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
    color: theme.textMuted,
    fontSize: 14,
  },
  waiting: {
    color: theme.textMuted,
    padding: '20px 0',
    fontStyle: 'italic',
  },
  header: {
    display: 'flex',
    gap: 12,
    alignItems: 'center',
    padding: '8px 0',
    marginBottom: 8,
    borderBottom: `1px solid ${theme.border}`,
  },
  label: { fontWeight: 700, color: theme.accent, fontSize: 14 },
  role: { color: theme.purple, fontSize: 11, fontWeight: 600 },
  branch: { color: theme.textMuted, fontSize: 11 },
  lines: { color: theme.textMuted, fontSize: 11, marginLeft: 'auto' },
  line: {
    padding: '1px 0',
    wordBreak: 'break-word',
  },
  linePrefix: {
    color: theme.accent,
    fontWeight: 600,
    fontSize: 11,
  },
}
