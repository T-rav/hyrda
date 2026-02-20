import React from 'react'
import { theme } from '../theme'

export function HITLTable({ items, onRefresh }) {
  if (items.length === 0) {
    return <div style={styles.empty}>No stuck PRs</div>
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.headerText}>
          {items.length} issue{items.length !== 1 ? 's' : ''} stuck on CI
        </span>
        <button onClick={onRefresh} style={styles.refresh}>Refresh</button>
      </div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>Issue</th>
            <th style={styles.th}>Title</th>
            <th style={styles.th}>PR</th>
            <th style={styles.th}>Branch</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => (
            <tr key={i}>
              <td style={styles.td}>
                <a href={item.issueUrl || '#'} target="_blank" rel="noreferrer" style={styles.link}>
                  #{item.issue}
                </a>
              </td>
              <td style={styles.td}>{item.title}</td>
              <td style={styles.td}>
                {item.pr > 0 ? (
                  <a href={item.prUrl || '#'} target="_blank" rel="noreferrer" style={styles.link}>
                    #{item.pr}
                  </a>
                ) : (
                  <span style={styles.noPr}>No PR</span>
                )}
              </td>
              <td style={styles.td}>{item.branch}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const styles = {
  container: { padding: 12 },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 12,
  },
  headerText: { color: theme.red, fontWeight: 600, fontSize: 13 },
  refresh: {
    background: theme.surfaceInset, border: `1px solid ${theme.border}`, color: theme.text,
    padding: '4px 12px', borderRadius: 6, cursor: 'pointer', fontSize: 11,
  },
  empty: {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    height: 200, color: theme.textMuted, fontSize: 13,
  },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
  th: {
    textAlign: 'left', padding: 8, borderBottom: `1px solid ${theme.border}`,
    color: theme.textMuted, fontSize: 11,
  },
  td: { padding: 8, borderBottom: `1px solid ${theme.border}` },
  link: { color: theme.accent, textDecoration: 'none' },
  noPr: { color: theme.textMuted, fontStyle: 'italic' },
}
