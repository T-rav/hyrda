import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup, act } from '@testing-library/react'
import { PRTable } from '../PRTable'

const makePR = (overrides = {}) => ({
  pr: 42,
  issue: 10,
  branch: 'agent/issue-10',
  url: 'https://github.com/org/repo/pull/42',
  merged: false,
  draft: false,
  ...overrides,
})

function mockFetchWith(data) {
  global.fetch = vi.fn().mockResolvedValue({
    json: () => Promise.resolve(data),
  })
}

describe('PRTable', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    cleanup()
  })

  it('shows loading state initially', () => {
    global.fetch = vi.fn().mockReturnValue(new Promise(() => {}))
    render(<PRTable />)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('fetches PRs on mount', () => {
    global.fetch = vi.fn().mockReturnValue(new Promise(() => {}))
    render(<PRTable />)
    expect(global.fetch).toHaveBeenCalledWith('/api/prs')
  })

  it('renders PR data after fetch', async () => {
    const prs = [
      makePR({ pr: 1, issue: 5, branch: 'agent/issue-5' }),
      makePR({ pr: 2, issue: 6, branch: 'agent/issue-6', merged: true }),
    ]
    mockFetchWith(prs)

    render(<PRTable />)
    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument()
    })

    expect(screen.getByText('#5')).toBeInTheDocument()
    expect(screen.getByText('agent/issue-5')).toBeInTheDocument()
    expect(screen.getByText('#2')).toBeInTheDocument()
    expect(screen.getByText('Merged')).toBeInTheDocument()
  })

  it('shows empty state when no PRs', async () => {
    mockFetchWith([])

    render(<PRTable />)
    await waitFor(() => {
      expect(screen.getByText('No pull requests yet')).toBeInTheDocument()
    })
  })

  it('refresh button calls fetch again', async () => {
    mockFetchWith([makePR()])

    render(<PRTable />)
    await waitFor(() => {
      expect(screen.getByText('Refresh')).toBeInTheDocument()
    })

    global.fetch.mockClear()
    fireEvent.click(screen.getByText('Refresh'))
    expect(global.fetch).toHaveBeenCalledWith('/api/prs')
  })

  it('shows PR count in header', async () => {
    mockFetchWith([makePR({ pr: 1 }), makePR({ pr: 2 }), makePR({ pr: 3 })])

    render(<PRTable />)
    await waitFor(() => {
      expect(screen.getByText('3 pull requests')).toBeInTheDocument()
    })
  })

  it('shows singular "pull request" for count of 1', async () => {
    mockFetchWith([makePR()])

    render(<PRTable />)
    await waitFor(() => {
      expect(screen.getByText('1 pull request')).toBeInTheDocument()
    })
  })

  it('auto-refreshes every 30s', () => {
    vi.useFakeTimers()
    mockFetchWith([makePR()])

    render(<PRTable />)
    // Initial mount fetch
    expect(global.fetch).toHaveBeenCalledTimes(1)

    // Advance past the 30s interval
    act(() => { vi.advanceTimersByTime(30000) })
    expect(global.fetch).toHaveBeenCalledTimes(2)

    act(() => { vi.advanceTimersByTime(30000) })
    expect(global.fetch).toHaveBeenCalledTimes(3)

    vi.useRealTimers()
  })

  it('cleans up interval on unmount', () => {
    vi.useFakeTimers()
    mockFetchWith([makePR()])

    const { unmount } = render(<PRTable />)
    expect(global.fetch).toHaveBeenCalledTimes(1)

    unmount()

    act(() => { vi.advanceTimersByTime(60000) })
    // No additional calls after unmount
    expect(global.fetch).toHaveBeenCalledTimes(1)

    vi.useRealTimers()
  })

  it('handles fetch errors gracefully', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'))

    render(<PRTable />)
    await waitFor(() => {
      expect(screen.getByText('No pull requests yet')).toBeInTheDocument()
    })
  })
})
