import React, { useState, useEffect, useCallback } from 'react'

export function HITLTable() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  const fetchHITL = useCallback(() => {
    setLoading(true)
    fetch('/api/hitl')
      .then(r => r.json())
      .then(data => setItems(data))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchHITL()
    const interval = setInterval(fetchHITL, 30000)
    return () => clearInterval(interval)
  }, [fetchHITL])

  if (loading && items.length === 0) {
    return <div style={styles.empty}>Loading...</div>
  }

  if (items.length === 0) {
    return <div style={styles.empty}>No stuck PRs</div>
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.headerText}>
          {items.length} issue{items.length !== 1 ? 's' : ''} stuck on CI
        </span>
        <button onClick={fetchHITL} style={styles.refresh}>Refresh</button>
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
  headerText: { color: '#f85149', fontWeight: 600, fontSize: 13 },
  refresh: {
    background: '#21262d', border: '1px solid #30363d', color: '#c9d1d9',
    padding: '4px 12px', borderRadius: 6, cursor: 'pointer', fontSize: 11,
  },
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
  link: { color: '#58a6ff', textDecoration: 'none' },
  noPr: { color: '#8b949e', fontStyle: 'italic' },
}
