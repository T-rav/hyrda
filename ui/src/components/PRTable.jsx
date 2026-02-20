import React, { useState, useEffect, useCallback } from 'react'
import { theme } from '../theme'

export function PRTable() {
  const [prs, setPrs] = useState([])
  const [loading, setLoading] = useState(true)

  const fetchPRs = useCallback(() => {
    setLoading(true)
    fetch('/api/prs')
      .then(r => r.json())
      .then(data => setPrs(data))
      .catch(() => setPrs([]))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchPRs()
    const interval = setInterval(fetchPRs, 30000)
    return () => clearInterval(interval)
  }, [fetchPRs])

  if (loading && prs.length === 0) {
    return <div style={styles.empty}>Loading...</div>
  }

  if (prs.length === 0) {
    return <div style={styles.empty}>No pull requests yet</div>
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.headerText}>
          {prs.length} pull request{prs.length !== 1 ? 's' : ''}
        </span>
        <button onClick={fetchPRs} style={styles.refresh}>Refresh</button>
      </div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>PR</th>
            <th style={styles.th}>Issue</th>
            <th style={styles.th}>Branch</th>
            <th style={styles.th}>Status</th>
          </tr>
        </thead>
        <tbody>
          {prs.map((p, i) => (
            <tr key={i}>
              <td style={styles.td}>
                <a href={p.url || '#'} target="_blank" rel="noreferrer" style={styles.link}>
                  #{p.pr}
                </a>
              </td>
              <td style={styles.td}>#{p.issue}</td>
              <td style={styles.td}>{p.branch}</td>
              <td style={styles.td}>
                {p.merged
                  ? <span style={styles.merged}>Merged</span>
                  : p.draft ? 'Draft' : 'Ready'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const styles = {
  container: { padding: 12, flex: 1, overflowY: 'auto', overflowX: 'auto' },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 12,
  },
  headerText: { color: theme.text, fontWeight: 600, fontSize: 13 },
  refresh: {
    background: theme.surfaceInset, border: `1px solid ${theme.border}`, color: theme.text,
    padding: '4px 12px', borderRadius: 6, cursor: 'pointer', fontSize: 11,
  },
  empty: {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    height: 200, color: theme.textMuted, fontSize: 13,
  },
  table: { width: '100%', minWidth: 500, borderCollapse: 'collapse', fontSize: 12 },
  th: {
    textAlign: 'left', padding: 8, borderBottom: `1px solid ${theme.border}`,
    color: theme.textMuted, fontSize: 11,
  },
  td: { padding: 8, borderBottom: `1px solid ${theme.border}` },
  link: { color: theme.accent, textDecoration: 'none' },
  merged: { color: theme.green, fontWeight: 600 },
}
