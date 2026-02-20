import React, { useRef, useEffect, useState } from 'react'
import { theme } from '../theme'
import { IssueCard } from './IssueCard'

const STATUS_PRIORITY = {
  implementing: 1,
  reviewing: 2,
  planning: 3,
  triaging: 4,
  submitted: 5,
  stuck: 6,
  failed: 7,
  done: 8,
  merged: 9,
}

function sortIssues(issues) {
  return Object.values(issues).sort((a, b) => {
    const pa = STATUS_PRIORITY[a.status] || 10
    const pb = STATUS_PRIORITY[b.status] || 10
    if (pa !== pb) return pa - pb
    // Within same priority, newest first
    return new Date(b.createdAt) - new Date(a.createdAt)
  })
}

export function StreamView({
  issues = {},
  workers = {},
  humanInputRequests = {},
  onHumanInputSubmit,
}) {
  const containerRef = useRef(null)
  const [expandedCards, setExpandedCards] = useState({})
  const [userScrolled, setUserScrolled] = useState(false)

  const sorted = sortIssues(issues)

  // Auto-scroll to keep newest active items visible (unless user scrolled)
  useEffect(() => {
    if (!userScrolled && containerRef.current) {
      containerRef.current.scrollTop = 0
    }
  }, [issues, userScrolled])

  const handleScroll = () => {
    if (!containerRef.current) return
    setUserScrolled(containerRef.current.scrollTop > 50)
  }

  const toggleCard = (issueNumber) => {
    setExpandedCards(prev => ({
      ...prev,
      [issueNumber]: !prev[issueNumber],
    }))
  }

  if (sorted.length === 0) {
    return (
      <div style={styles.empty}>
        <div style={styles.emptyTitle}>No activity yet</div>
        <div style={styles.emptyHint}>
          Type something above to get started, or create issues on GitHub with Hydra labels.
        </div>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      style={styles.container}
      onScroll={handleScroll}
    >
      {sorted.map((issue) => (
        <IssueCard
          key={issue.number}
          issue={issue}
          workers={workers}
          expanded={!!expandedCards[issue.number]}
          onToggle={() => toggleCard(issue.number)}
          humanInputRequests={humanInputRequests}
          onHumanInputSubmit={onHumanInputSubmit}
        />
      ))}
    </div>
  )
}

const styles = {
  container: {
    flex: 1,
    overflowY: 'auto',
  },
  empty: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
    color: theme.textMuted,
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: 600,
    color: theme.textMuted,
    marginBottom: 8,
  },
  emptyHint: {
    fontSize: 13,
    color: theme.textInactive,
    textAlign: 'center',
    maxWidth: 400,
  },
}

// Pre-computed style exports for testing
export const streamStyles = styles
