import React from 'react'
import { theme } from '../theme'
import { HumanInputBanner } from './HumanInputBanner'

const statusConfig = {
  submitted:    { label: 'Submitted',     bg: theme.mutedSubtle,   fg: theme.textMuted },
  triaging:     { label: 'Triaging',      bg: theme.greenSubtle,   fg: theme.triageGreen },
  planning:     { label: 'Planning',      bg: theme.purpleSubtle,  fg: theme.purple },
  implementing: { label: 'Implementing',  bg: theme.accentSubtle,  fg: theme.accent },
  reviewing:    { label: 'Reviewing',     bg: theme.orangeSubtle,  fg: theme.orange },
  merged:       { label: 'Merged',        bg: theme.greenSubtle,   fg: theme.green },
  done:         { label: 'Done',          bg: theme.greenSubtle,   fg: theme.green },
  failed:       { label: 'Failed',        bg: theme.redSubtle,     fg: theme.red },
  stuck:        { label: 'Needs Help',    bg: theme.redSubtle,     fg: theme.red },
}

const STAGE_ORDER = ['submitted', 'triaging', 'planning', 'implementing', 'reviewing']

function getTranscriptExcerpt(workers, issueNumber) {
  // Find the most relevant worker for this issue (implementer first, then planner, then triage)
  const keys = [
    issueNumber,
    `plan-${issueNumber}`,
    `triage-${issueNumber}`,
  ]
  for (const key of keys) {
    const worker = workers[key]
    if (worker && worker.transcript && worker.transcript.length > 0) {
      return worker.transcript.slice(-3)
    }
  }
  return []
}

function getReviewWorker(workers, issueNumber) {
  // Find review worker for this issue by scanning review-* keys
  return Object.entries(workers).find(([key, w]) =>
    key.startsWith('review-') && w.title && w.title.includes(`Issue #${issueNumber}`)
  )
}

export function IssueCard({
  issue,
  workers = {},
  expanded = false,
  onToggle,
  humanInputRequests = {},
  onHumanInputSubmit,
}) {
  const sc = statusConfig[issue.status] || statusConfig.submitted
  const isActive = STAGE_ORDER.includes(issue.status)
  const showExpanded = expanded || isActive

  const excerpt = showExpanded ? getTranscriptExcerpt(workers, issue.number) : []
  const reviewEntry = getReviewWorker(workers, issue.number)

  // Check for HITL request on this issue
  const hitlQuestion = humanInputRequests[issue.number]

  return (
    <div style={styles.card} onClick={onToggle} role="article">
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.issueNum}>#{issue.number}</span>
          <span style={styles.title}>{issue.title}</span>
        </div>
        <div style={styles.headerRight}>
          <span style={{ ...styles.badge, background: sc.bg, color: sc.fg }}>
            {sc.label}
          </span>
          <span style={styles.time}>
            {new Date(issue.createdAt).toLocaleTimeString()}
          </span>
        </div>
      </div>

      {showExpanded && (
        <div style={styles.body}>
          {/* Intent */}
          {issue.body && (
            <div style={styles.stage}>
              <span style={styles.stageIcon}>You</span>
              <span style={styles.stageText}>{issue.body}</span>
            </div>
          )}

          {/* Plan summary */}
          {issue.planSummary && (
            <div style={styles.stage}>
              <span style={{ ...styles.stageIcon, color: theme.purple }}>Planner</span>
              <span style={styles.stageText}>{issue.planSummary}</span>
            </div>
          )}

          {/* Transcript excerpt */}
          {excerpt.length > 0 && (
            <div style={styles.stage}>
              <span style={{ ...styles.stageIcon, color: theme.accent }}>Agent</span>
              <div style={styles.excerpt}>
                {excerpt.map((line, i) => (
                  <div key={i} style={styles.excerptLine}>{line}</div>
                ))}
              </div>
            </div>
          )}

          {/* Review verdict */}
          {issue.verdict && (
            <div style={styles.stage}>
              <span style={{ ...styles.stageIcon, color: theme.orange }}>Reviewer</span>
              <span style={styles.stageText}>{issue.verdict}</span>
            </div>
          )}

          {/* Review worker status */}
          {reviewEntry && !issue.verdict && (
            <div style={styles.stage}>
              <span style={{ ...styles.stageIcon, color: theme.orange }}>Reviewer</span>
              <span style={styles.stageText}>Reviewing PR...</span>
            </div>
          )}

          {/* PR link */}
          {issue.prUrl && (
            <div style={styles.stage}>
              <span style={{ ...styles.stageIcon, color: theme.green }}>PR</span>
              <a
                href={issue.prUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={styles.prLink}
                onClick={(e) => e.stopPropagation()}
              >
                PR #{issue.prNumber} {issue.status === 'merged' ? '(merged)' : ''}
              </a>
            </div>
          )}

          {/* HITL inline */}
          {hitlQuestion && onHumanInputSubmit && (
            <div style={styles.hitlContainer} onClick={(e) => e.stopPropagation()}>
              <HumanInputBanner
                requests={{ [issue.number]: hitlQuestion }}
                onSubmit={onHumanInputSubmit}
              />
            </div>
          )}
        </div>
      )}

      {!showExpanded && issue.prUrl && (
        <div style={styles.collapsedMeta}>
          <a
            href={issue.prUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={styles.prLink}
            onClick={(e) => e.stopPropagation()}
          >
            PR #{issue.prNumber}
          </a>
        </div>
      )}
    </div>
  )
}

const styles = {
  card: {
    padding: '12px 16px',
    borderBottom: `1px solid ${theme.border}`,
    cursor: 'pointer',
    transition: 'background 0.1s',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flex: 1,
    minWidth: 0,
  },
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexShrink: 0,
  },
  issueNum: {
    fontWeight: 700,
    color: theme.textBright,
    fontSize: 13,
    flexShrink: 0,
  },
  title: {
    fontSize: 13,
    color: theme.text,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  badge: {
    fontSize: 11,
    padding: '2px 8px',
    borderRadius: 8,
    fontWeight: 600,
    whiteSpace: 'nowrap',
  },
  time: {
    fontSize: 11,
    color: theme.textMuted,
    whiteSpace: 'nowrap',
  },
  body: {
    marginTop: 10,
    paddingLeft: 4,
  },
  stage: {
    display: 'flex',
    gap: 10,
    marginBottom: 8,
    fontSize: 12,
    lineHeight: 1.5,
  },
  stageIcon: {
    fontWeight: 600,
    color: theme.textMuted,
    minWidth: 60,
    flexShrink: 0,
    fontSize: 11,
    textTransform: 'uppercase',
  },
  stageText: {
    color: theme.text,
    flex: 1,
    wordBreak: 'break-word',
  },
  excerpt: {
    flex: 1,
    fontFamily: 'monospace',
    fontSize: 11,
    color: theme.textMuted,
    lineHeight: 1.4,
  },
  excerptLine: {
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  prLink: {
    color: theme.accent,
    textDecoration: 'none',
    fontSize: 12,
    fontWeight: 600,
  },
  hitlContainer: {
    marginTop: 4,
    borderRadius: 6,
    overflow: 'hidden',
  },
  collapsedMeta: {
    marginTop: 6,
    paddingLeft: 4,
  },
}

// Pre-computed style exports for testing
export const cardStyles = styles
export const issueStatusConfig = statusConfig
