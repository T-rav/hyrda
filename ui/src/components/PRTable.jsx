import React from 'react'
import { theme } from '../theme'

export function PRTable({ prs }) {
  if (prs.length === 0) {
    return <div style={styles.empty}>No pull requests yet</div>
  }

  return (
    <div style={styles.container}>
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
  container: { padding: 12 },
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
  merged: { color: theme.green, fontWeight: 600 },
}
