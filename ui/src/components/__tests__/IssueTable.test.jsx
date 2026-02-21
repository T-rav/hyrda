import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup, act } from '@testing-library/react'
import { IssueTable } from '../IssueTable'

const makeIssue = (overrides = {}) => ({
  issue: 42,
  title: 'Fix the frobnicator',
  url: 'https://github.com/org/repo/issues/42',
  status: 'implement',
  pr: 101,
  prUrl: 'https://github.com/org/repo/pull/101',
  labels: ['hydra-ready'],
  ...overrides,
})

function mockFetchWith(data) {
  global.fetch = vi.fn().mockResolvedValue({
    json: () => Promise.resolve(data),
  })
}

describe('IssueTable', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    cleanup()
  })

  it('fetches issues on mount', () => {
    global.fetch = vi.fn().mockReturnValue(new Promise(() => {}))
    render(<IssueTable />)
    expect(global.fetch).toHaveBeenCalledWith('/api/issues')
  })

  it('renders issue data after fetch when in backlog mode', async () => {
    const issues = [
      makeIssue({ issue: 1, title: 'Bug fix', status: 'implement', pr: 10, prUrl: 'https://github.com/org/repo/pull/10' }),
      makeIssue({ issue: 2, title: 'Feature', status: 'review', pr: 0, prUrl: '' }),
    ]
    mockFetchWith(issues)

    render(<IssueTable />)

    // Switch to All/backlog filter
    await waitFor(() => {
      expect(screen.getByText('All')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('All'))

    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument()
    })

    expect(screen.getByText('Bug fix')).toBeInTheDocument()
    expect(screen.getByText('#10')).toBeInTheDocument()
    expect(screen.getByText('#2')).toBeInTheDocument()
    expect(screen.getByText('Feature')).toBeInTheDocument()
  })

  it('shows empty state when no issues in session', async () => {
    mockFetchWith([])

    render(<IssueTable workers={{}} />)
    await waitFor(() => {
      expect(screen.getByText('No issues this session')).toBeInTheDocument()
    })
  })

  it('shows empty state when no issues in backlog', async () => {
    mockFetchWith([])

    render(<IssueTable workers={{}} />)
    await waitFor(() => {
      expect(screen.getByText('Session')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('All'))

    await waitFor(() => {
      expect(screen.getByText('No issues yet')).toBeInTheDocument()
    })
  })

  it('shows issue count in header', async () => {
    mockFetchWith([
      makeIssue({ issue: 1 }),
      makeIssue({ issue: 2 }),
      makeIssue({ issue: 3 }),
    ])

    render(<IssueTable />)
    // Switch to backlog to see API data
    await waitFor(() => {
      expect(screen.getByText('All')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('All'))

    await waitFor(() => {
      expect(screen.getByText('3 issues')).toBeInTheDocument()
    })
  })

  it('shows singular "issue" for count of 1', async () => {
    mockFetchWith([makeIssue()])

    render(<IssueTable />)
    await waitFor(() => {
      expect(screen.getByText('All')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('All'))

    await waitFor(() => {
      expect(screen.getByText('1 issue')).toBeInTheDocument()
    })
  })

  it('refresh button calls fetch again', async () => {
    mockFetchWith([makeIssue()])

    render(<IssueTable />)
    await waitFor(() => {
      expect(screen.getByText('Refresh')).toBeInTheDocument()
    })

    global.fetch.mockClear()
    fireEvent.click(screen.getByText('Refresh'))
    expect(global.fetch).toHaveBeenCalledWith('/api/issues')
  })

  it('auto-refreshes every 30s', () => {
    vi.useFakeTimers()
    mockFetchWith([makeIssue()])

    render(<IssueTable />)
    expect(global.fetch).toHaveBeenCalledTimes(1)

    act(() => { vi.advanceTimersByTime(30000) })
    expect(global.fetch).toHaveBeenCalledTimes(2)

    act(() => { vi.advanceTimersByTime(30000) })
    expect(global.fetch).toHaveBeenCalledTimes(3)

    vi.useRealTimers()
  })

  it('cleans up interval on unmount', () => {
    vi.useFakeTimers()
    mockFetchWith([makeIssue()])

    const { unmount } = render(<IssueTable />)
    expect(global.fetch).toHaveBeenCalledTimes(1)

    unmount()

    act(() => { vi.advanceTimersByTime(60000) })
    expect(global.fetch).toHaveBeenCalledTimes(1)

    vi.useRealTimers()
  })

  it('handles fetch errors gracefully', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'))

    render(<IssueTable />)
    // Switch to backlog to verify error handling
    await waitFor(() => {
      expect(screen.getByText('All')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('All'))

    await waitFor(() => {
      expect(screen.getByText('No issues yet')).toBeInTheDocument()
    })
  })

  it('container has overflowX auto for horizontal scrolling', async () => {
    mockFetchWith([makeIssue()])

    render(<IssueTable />)
    // Switch to backlog to render the table
    await waitFor(() => {
      expect(screen.getByText('All')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('All'))

    await waitFor(() => {
      expect(screen.getByText('#42')).toBeInTheDocument()
    })
    const table = screen.getByText('#42').closest('table')
    const container = table.parentElement
    expect(container.style.overflowX).toBe('auto')
  })

  it('table has minWidth to prevent column squishing', async () => {
    mockFetchWith([makeIssue()])

    render(<IssueTable />)
    await waitFor(() => {
      expect(screen.getByText('All')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('All'))

    await waitFor(() => {
      expect(screen.getByText('#42')).toBeInTheDocument()
    })
    const table = screen.getByText('#42').closest('table')
    expect(table.style.minWidth).toBe('500px')
  })

  it('status badges display pipeline status', async () => {
    mockFetchWith([
      makeIssue({ issue: 1, status: 'implement' }),
      makeIssue({ issue: 2, status: 'review' }),
    ])

    render(<IssueTable />)
    await waitFor(() => {
      expect(screen.getByText('All')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('All'))

    await waitFor(() => {
      expect(screen.getByText('implement')).toBeInTheDocument()
    })
    expect(screen.getByText('review')).toBeInTheDocument()
  })

  it('issue number links to GitHub issue URL', async () => {
    mockFetchWith([makeIssue({
      issue: 42,
      url: 'https://github.com/org/repo/issues/42',
    })])

    render(<IssueTable />)
    await waitFor(() => {
      expect(screen.getByText('All')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('All'))

    await waitFor(() => {
      const link = screen.getByText('#42')
      expect(link.closest('a').href).toBe('https://github.com/org/repo/issues/42')
    })
  })

  it('PR number links to PR URL when present', async () => {
    mockFetchWith([makeIssue({
      pr: 101,
      prUrl: 'https://github.com/org/repo/pull/101',
    })])

    render(<IssueTable />)
    await waitFor(() => {
      expect(screen.getByText('All')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('All'))

    await waitFor(() => {
      const prLink = screen.getByText('#101')
      expect(prLink.closest('a').href).toBe('https://github.com/org/repo/pull/101')
    })
  })

  it('shows no PR link when pr is 0', async () => {
    mockFetchWith([makeIssue({ pr: 0, prUrl: '' })])

    render(<IssueTable />)
    await waitFor(() => {
      expect(screen.getByText('All')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('All'))

    await waitFor(() => {
      expect(screen.getByText('#42')).toBeInTheDocument()
    })
    // The PR column should be empty
    expect(screen.queryByText('#0')).toBeNull()
  })

  describe('Session filter', () => {
    it('defaults to session filter', async () => {
      mockFetchWith([])

      render(<IssueTable workers={{}} />)
      await waitFor(() => {
        expect(screen.getByText('No issues this session')).toBeInTheDocument()
      })
    })

    it('derives issues from workers with numeric keys (implementers)', async () => {
      mockFetchWith([])
      const workers = {
        42: {
          status: 'running',
          worker: 0,
          role: 'implementer',
          title: 'Issue #42',
          branch: 'agent/issue-42',
          transcript: [],
          pr: null,
        },
      }

      render(<IssueTable workers={workers} />)
      await waitFor(() => {
        expect(screen.getByText('#42')).toBeInTheDocument()
      })
      expect(screen.getByText('implement')).toBeInTheDocument()
    })

    it('derives issues from workers with triage-N keys', async () => {
      mockFetchWith([])
      const workers = {
        'triage-10': {
          status: 'running',
          worker: 0,
          role: 'triage',
          title: 'Triage Issue #10',
          branch: '',
          transcript: [],
          pr: null,
        },
      }

      render(<IssueTable workers={workers} />)
      await waitFor(() => {
        expect(screen.getByText('#10')).toBeInTheDocument()
      })
      expect(screen.getByText('triage')).toBeInTheDocument()
    })

    it('derives issues from workers with plan-N keys', async () => {
      mockFetchWith([])
      const workers = {
        'plan-20': {
          status: 'planning',
          worker: 0,
          role: 'planner',
          title: 'Plan Issue #20',
          branch: '',
          transcript: [],
          pr: null,
        },
      }

      render(<IssueTable workers={workers} />)
      await waitFor(() => {
        expect(screen.getByText('#20')).toBeInTheDocument()
      })
      expect(screen.getByText('plan')).toBeInTheDocument()
    })

    it('derives issues from review-N workers using title', async () => {
      mockFetchWith([])
      const workers = {
        'review-101': {
          status: 'reviewing',
          worker: 0,
          role: 'reviewer',
          title: 'PR #101 (Issue #55)',
          branch: '',
          transcript: [],
          pr: 101,
        },
      }

      render(<IssueTable workers={workers} />)
      await waitFor(() => {
        expect(screen.getByText('#55')).toBeInTheDocument()
      })
      expect(screen.getByText('review')).toBeInTheDocument()
    })

    it('enriches session issues with API data', async () => {
      const apiIssues = [
        makeIssue({
          issue: 42,
          title: 'Fix the frobnicator',
          url: 'https://github.com/org/repo/issues/42',
          pr: 101,
          prUrl: 'https://github.com/org/repo/pull/101',
        }),
      ]
      mockFetchWith(apiIssues)

      const workers = {
        42: {
          status: 'running',
          worker: 0,
          role: 'implementer',
          title: 'Issue #42',
          branch: 'agent/issue-42',
          transcript: [],
          pr: null,
        },
      }

      render(<IssueTable workers={workers} />)
      await waitFor(() => {
        expect(screen.getByText('Fix the frobnicator')).toBeInTheDocument()
      })
      expect(screen.getByText('#101')).toBeInTheDocument()
    })
  })

  describe('Filter toggle', () => {
    it('switches between session and backlog views', async () => {
      const apiIssues = [
        makeIssue({ issue: 99, title: 'Backlog item', status: 'plan' }),
      ]
      mockFetchWith(apiIssues)

      render(<IssueTable workers={{}} />)
      await waitFor(() => {
        expect(screen.getByText('No issues this session')).toBeInTheDocument()
      })

      // Switch to All
      fireEvent.click(screen.getByText('All'))
      await waitFor(() => {
        expect(screen.getByText('Backlog item')).toBeInTheDocument()
      })

      // Switch back to Session
      fireEvent.click(screen.getByText('Session'))
      await waitFor(() => {
        expect(screen.getByText('No issues this session')).toBeInTheDocument()
      })
    })
  })
})
