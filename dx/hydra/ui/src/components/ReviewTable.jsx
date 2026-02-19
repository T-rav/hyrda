import React from 'react'

const verdictColors = {
  approve: '#3fb950',
  'request-changes': '#f85149',
  comment: '#d29922',
}

export function ReviewTable({ reviews }) {
  if (reviews.length === 0) {
    return <div style={styles.empty}>No reviews yet</div>
  }

  return (
    <div style={styles.container}>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>PR</th>
            <th style={styles.th}>Verdict</th>
            <th style={styles.th}>Summary</th>
          </tr>
        </thead>
        <tbody>
          {reviews.map((r, i) => (
            <tr key={i}>
              <td style={styles.td}>#{r.pr}</td>
              <td style={{ ...styles.td, color: verdictColors[r.verdict] || '#c9d1d9' }}>
                {r.verdict}
              </td>
              <td style={styles.td}>{r.summary || ''}</td>
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
    height: 200, color: '#8b949e', fontSize: 13,
  },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
  th: {
    textAlign: 'left', padding: 8, borderBottom: '1px solid #30363d',
    color: '#8b949e', fontSize: 11,
  },
  td: { padding: 8, borderBottom: '1px solid #30363d' },
}
