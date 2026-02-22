import React, { useState, useEffect, useRef } from 'react'
import { theme } from '../theme'

export function TranscriptPreview({ transcript, maxCollapsedLines = 3, maxHeight = 200 }) {
  const [expanded, setExpanded] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => {
    if (expanded && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [expanded, transcript])

  if (!transcript || transcript.length === 0) return null

  const visibleLines = expanded
    ? transcript
    : transcript.slice(-maxCollapsedLines)

  return (
    <div style={styles.container} data-testid="transcript-preview">
      <div
        ref={scrollRef}
        style={expanded ? { ...styles.lines, maxHeight, overflowY: 'auto' } : styles.lines}
      >
        {visibleLines.map((line, i) => (
          <div key={expanded ? i : transcript.length - maxCollapsedLines + i} style={styles.line}>
            {line}
          </div>
        ))}
      </div>
      <div
        style={styles.toggle}
        onClick={() => setExpanded(v => !v)}
        data-testid="transcript-toggle"
      >
        {expanded ? 'Collapse' : `Show all (${transcript.length} lines)`}
      </div>
    </div>
  )
}

const styles = {
  container: {
    borderTop: `1px solid ${theme.border}`,
    marginTop: 4,
    paddingTop: 4,
  },
  lines: {
    fontFamily: 'monospace',
    fontSize: 10,
    color: theme.textMuted,
    lineHeight: 1.5,
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all',
  },
  line: {
    padding: '1px 0',
  },
  toggle: {
    fontSize: 10,
    fontWeight: 600,
    color: theme.accent,
    cursor: 'pointer',
    paddingTop: 4,
  },
}
