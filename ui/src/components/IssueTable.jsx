import React, { useState, useEffect, useCallback } from 'react'
import { theme } from '../theme'
import { PIPELINE_STAGES } from '../constants'

/** Map pipeline stage key to its color from PIPELINE_STAGES. */
const stageColorMap = Object.fromEntries(
  PIPELINE_STAGES.map(s => [s.key, s.color])
)

/** Extra status colors not in PIPELINE_STAGES. */
const extraStatusColors = {
  backlog: theme.textMuted,
  hitl: theme.red,
  failed: theme.red,
}

function getStatusColor(status) {
  return stageColorMap[status] || extraStatusColors[status] || theme.textMuted
}

/**
 * Extract issue number from a worker key.
 * Handles: "triage-42", "plan-42", "42", "review-101" (PR-keyed).
 */
function extractIssueFromWorkerKey(key, worker) {
  // Direct numeric key = implementer issue number
  if (!isNaN(Number(key))) return Number(key)

  // triage-N or plan-N
  const match = key.match(/^(?:triage|plan)-(\d+)$/)
  if (match) return Number(match[1])

  // review-N: keyed by PR number, extract issue from title
  if (key.startsWith('review-') && worker?.title) {
    const issueMatch = worker.title.match(/Issue #(\d+)/)
    if (issueMatch) return Number(issueMatch[1])
  }

  return null
}

/**
 * Map worker role to pipeline status key.
 */
function roleToStatus(role) {
  switch (role) {
    case 'triage': return 'triage'
    case 'planner': return 'plan'
    case 'implementer': return 'implement'
    case 'reviewer': return 'review'
    default: return 'backlog'
  }
}

export function IssueTable({ workers = {} }) {
  const [issues, setIssues] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('session')

  const fetchIssues = useCallback(() => {
    setLoading(true)
    fetch('/api/issues')
      .then(r => r.json())
      .then(data => setIssues(data))
      .catch(() => setIssues([]))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchIssues()
    const interval = setInterval(fetchIssues, 30000)
    return () => clearInterval(interval)
  }, [fetchIssues])

  // Build session issues from workers state
  const sessionIssues = React.useMemo(() => {
    const issueMap = new Map()

    for (const [key, worker] of Object.entries(workers)) {
      const issueNum = extractIssueFromWorkerKey(key, worker)
      if (issueNum === null) continue

      // Use highest-priority status if an issue appears in multiple workers
      const existing = issueMap.get(issueNum)
      const status = worker.status === 'done' || worker.status === 'failed'
        ? worker.status === 'failed' ? 'failed' : roleToStatus(worker.role)
        : roleToStatus(worker.role)

      if (!existing) {
        issueMap.set(issueNum, {
          issue: issueNum,
          title: worker.title || `Issue #${issueNum}`,
          url: '',
          status,
          pr: worker.pr?.pr || worker.pr?.number || 0,
          prUrl: worker.pr?.url || '',
          labels: [],
        })
      }
    }

    // Enrich session issues with API data (titles, URLs, PR info)
    for (const apiIssue of issues) {
      const entry = issueMap.get(apiIssue.issue)
      if (entry) {
        entry.url = apiIssue.url || entry.url
        entry.title = apiIssue.title || entry.title
        if (apiIssue.pr && !entry.pr) {
          entry.pr = apiIssue.pr
          entry.prUrl = apiIssue.prUrl
        }
        entry.labels = apiIssue.labels || entry.labels
      }
    }

    return Array.from(issueMap.values())
  }, [workers, issues])

  const displayIssues = filter === 'session' ? sessionIssues : issues

  if (loading && issues.length === 0 && filter === 'backlog') {
    return <div style={styles.empty}>Loading...</div>
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.headerText}>
            {displayIssues.length} issue{displayIssues.length !== 1 ? 's' : ''}
          </span>
          <div style={styles.filterGroup}>
            <button
              onClick={() => setFilter('session')}
              style={filter === 'session' ? styles.filterActive : styles.filterInactive}
            >
              Session
            </button>
            <button
              onClick={() => setFilter('backlog')}
              style={filter === 'backlog' ? styles.filterActive : styles.filterInactive}
            >
              All
            </button>
          </div>
        </div>
        <button onClick={fetchIssues} style={styles.refresh}>Refresh</button>
      </div>

      {displayIssues.length === 0 ? (
        <div style={styles.emptyTable}>
          {filter === 'session' ? 'No issues this session' : 'No issues yet'}
        </div>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Issue</th>
              <th style={styles.th}>Title</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>PR</th>
            </tr>
          </thead>
          <tbody>
            {displayIssues.map((item) => (
              <tr key={item.issue}>
                <td style={styles.td}>
                  <a
                    href={item.url || '#'}
                    target="_blank"
                    rel="noreferrer"
                    style={styles.link}
                  >
                    #{item.issue}
                  </a>
                </td>
                <td style={styles.td}>{item.title}</td>
                <td style={styles.td}>
                  <span style={{
                    ...styles.statusBadge,
                    color: getStatusColor(item.status),
                    background: getStatusColor(item.status) + '1a',
                  }}>
                    {item.status}
                  </span>
                </td>
                <td style={styles.td}>
                  {item.pr ? (
                    <a
                      href={item.prUrl || '#'}
                      target="_blank"
                      rel="noreferrer"
                      style={styles.link}
                    >
                      #{item.pr}
                    </a>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

const styles = {
  container: { padding: 12, flex: 1, overflowY: 'auto', overflowX: 'auto' },
  header: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 12,
  },
  headerLeft: {
    display: 'flex', alignItems: 'center', gap: 12,
  },
  headerText: { color: theme.text, fontWeight: 600, fontSize: 13 },
  filterGroup: {
    display: 'flex', gap: 4,
  },
  filterActive: {
    background: theme.accent, border: 'none', color: theme.white,
    padding: '4px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 11,
    fontWeight: 600,
  },
  filterInactive: {
    background: theme.surfaceInset, border: `1px solid ${theme.border}`, color: theme.textMuted,
    padding: '4px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 11,
  },
  refresh: {
    background: theme.surfaceInset, border: `1px solid ${theme.border}`, color: theme.text,
    padding: '4px 12px', borderRadius: 6, cursor: 'pointer', fontSize: 11,
  },
  empty: {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    height: 200, color: theme.textMuted, fontSize: 13,
  },
  emptyTable: {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    height: 120, color: theme.textMuted, fontSize: 13,
  },
  table: { width: '100%', minWidth: 500, borderCollapse: 'collapse', fontSize: 12 },
  th: {
    textAlign: 'left', padding: 8, borderBottom: `1px solid ${theme.border}`,
    color: theme.textMuted, fontSize: 11,
  },
  td: { padding: 8, borderBottom: `1px solid ${theme.border}` },
  link: { color: theme.accent, textDecoration: 'none' },
  statusBadge: {
    padding: '2px 8px',
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 600,
    textTransform: 'capitalize',
  },
}
