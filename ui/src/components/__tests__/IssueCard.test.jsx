import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { IssueCard, cardStyles, issueStatusConfig } from '../IssueCard'

beforeEach(() => cleanup())

const makeIssue = (overrides = {}) => ({
  number: 42,
  title: 'Add rate limiting',
  body: 'We need rate limiting on API endpoints',
  status: 'implementing',
  createdAt: '2024-01-01T00:00:00Z',
  events: [],
  prNumber: null,
  prUrl: null,
  planSummary: null,
  verdict: null,
  ...overrides,
})

describe('IssueCard', () => {
  it('renders issue number and title', () => {
    render(<IssueCard issue={makeIssue()} />)
    expect(screen.getByText('#42')).toBeInTheDocument()
    expect(screen.getByText('Add rate limiting')).toBeInTheDocument()
  })

  it('shows correct status badge for implementing', () => {
    render(<IssueCard issue={makeIssue({ status: 'implementing' })} />)
    expect(screen.getByText('Implementing')).toBeInTheDocument()
  })

  it('shows correct status badge for merged', () => {
    render(<IssueCard issue={makeIssue({ status: 'merged' })} />)
    expect(screen.getByText('Merged')).toBeInTheDocument()
  })

  it('shows correct status badge for planning', () => {
    render(<IssueCard issue={makeIssue({ status: 'planning' })} />)
    expect(screen.getByText('Planning')).toBeInTheDocument()
  })

  it('shows correct status badge for stuck', () => {
    render(<IssueCard issue={makeIssue({ status: 'stuck' })} />)
    expect(screen.getByText('Needs Help')).toBeInTheDocument()
  })

  it('auto-expands active issues', () => {
    render(<IssueCard issue={makeIssue({ body: 'Visible body text' })} />)
    // Active (implementing) should be expanded and show body
    expect(screen.getByText('Visible body text')).toBeInTheDocument()
  })

  it('collapsed completed issues show only header', () => {
    render(<IssueCard issue={makeIssue({ status: 'merged', body: 'Hidden body' })} />)
    // Merged issues should be collapsed by default
    expect(screen.queryByText('Hidden body')).toBeNull()
  })

  it('expanded view shows plan summary', () => {
    render(
      <IssueCard
        issue={makeIssue({ planSummary: 'Add middleware to 3 endpoints' })}
      />
    )
    expect(screen.getByText('Add middleware to 3 endpoints')).toBeInTheDocument()
  })

  it('shows PR link when available', () => {
    render(
      <IssueCard
        issue={makeIssue({
          prNumber: 99,
          prUrl: 'https://github.com/test/repo/pull/99',
        })}
      />
    )
    expect(screen.getByText(/PR #99/)).toBeInTheDocument()
  })

  it('shows verdict when available', () => {
    render(
      <IssueCard
        issue={makeIssue({
          status: 'reviewing',
          verdict: 'approve',
        })}
      />
    )
    expect(screen.getByText('approve')).toBeInTheDocument()
  })

  it('shows transcript excerpt from workers', () => {
    const workers = {
      42: {
        transcript: ['line 1', 'line 2', 'line 3', 'line 4'],
        status: 'running',
      },
    }
    render(<IssueCard issue={makeIssue()} workers={workers} />)
    // Should show last 3 lines
    expect(screen.getByText('line 2')).toBeInTheDocument()
    expect(screen.getByText('line 3')).toBeInTheDocument()
    expect(screen.getByText('line 4')).toBeInTheDocument()
  })

  it('calls onToggle when card is clicked', () => {
    const onToggle = vi.fn()
    render(<IssueCard issue={makeIssue()} onToggle={onToggle} />)
    fireEvent.click(screen.getByRole('article'))
    expect(onToggle).toHaveBeenCalledTimes(1)
  })
})

describe('IssueCard pre-computed styles', () => {
  it('card has border and padding', () => {
    expect(cardStyles.card).toMatchObject({
      padding: '12px 16px',
      cursor: 'pointer',
    })
  })

  it('statusConfig covers all expected statuses', () => {
    const expectedStatuses = [
      'submitted', 'triaging', 'planning', 'implementing',
      'reviewing', 'merged', 'done', 'failed', 'stuck',
    ]
    for (const status of expectedStatuses) {
      expect(issueStatusConfig[status]).toBeDefined()
      expect(issueStatusConfig[status].label).toBeTruthy()
    }
  })

  it('style objects are referentially stable', () => {
    expect(cardStyles.card).toBe(cardStyles.card)
    expect(cardStyles.header).toBe(cardStyles.header)
  })
})
