import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { HITLTable } from '../HITLTable'

const mockItems = [
  {
    issue: 42,
    title: 'Fix widget',
    issueUrl: 'https://github.com/org/repo/issues/42',
    pr: 99,
    prUrl: 'https://github.com/org/repo/pull/99',
    branch: 'agent/issue-42',
    cause: 'CI failure',
    status: 'pending',
  },
  {
    issue: 10,
    title: 'Broken thing',
    issueUrl: '',
    pr: 0,
    prUrl: '',
    branch: 'agent/issue-10',
    cause: '',
    status: 'processing',
  },
]

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('HITLTable component', () => {
  it('renders table with items after fetch', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockItems),
    })

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByText('#42')).toBeInTheDocument()
    })
    expect(screen.getByText('Fix widget')).toBeInTheDocument()
    expect(screen.getByText('#99')).toBeInTheDocument()
    expect(screen.getByText('agent/issue-42')).toBeInTheDocument()
  })

  it('shows loading state initially', () => {
    global.fetch = vi.fn().mockReturnValue(new Promise(() => {}))

    render(<HITLTable />)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('shows empty state when no items', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    })

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByText('No stuck PRs')).toBeInTheDocument()
    })
  })

  it('renders status column header', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockItems),
    })

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByText('Status')).toBeInTheDocument()
    })
  })

  it('renders status badges for each item', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockItems),
    })

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByText('pending')).toBeInTheDocument()
      expect(screen.getByText('processing')).toBeInTheDocument()
    })
  })

  it('expands row on click to show detail panel', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockItems),
    })

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByTestId('hitl-row-42')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('hitl-row-42'))

    expect(screen.getByTestId('hitl-detail-42')).toBeInTheDocument()
    expect(screen.getByTestId('hitl-textarea-42')).toBeInTheDocument()
    expect(screen.getByTestId('hitl-retry-42')).toBeInTheDocument()
    expect(screen.getByTestId('hitl-skip-42')).toBeInTheDocument()
    expect(screen.getByTestId('hitl-close-42')).toBeInTheDocument()
  })

  it('collapses row on second click', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockItems),
    })

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByTestId('hitl-row-42')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('hitl-row-42'))
    expect(screen.getByTestId('hitl-detail-42')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('hitl-row-42'))
    expect(screen.queryByTestId('hitl-detail-42')).not.toBeInTheDocument()
  })

  it('shows cause badge when cause is non-empty', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockItems),
    })

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByTestId('hitl-row-42')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('hitl-row-42'))
    expect(screen.getByTestId('hitl-cause-42')).toBeInTheDocument()
    expect(screen.getByText('Cause: CI failure')).toBeInTheDocument()
  })

  it('hides cause badge when cause is empty', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockItems),
    })

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByTestId('hitl-row-10')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('hitl-row-10'))
    expect(screen.queryByTestId('hitl-cause-10')).not.toBeInTheDocument()
  })

  it('updates correction text area state', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockItems),
    })

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByTestId('hitl-row-42')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('hitl-row-42'))

    const textarea = screen.getByTestId('hitl-textarea-42')
    fireEvent.change(textarea, { target: { value: 'Mock the DB' } })
    expect(textarea.value).toBe('Mock the DB')
  })

  it('retry button is disabled when textarea is empty', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockItems),
    })

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByTestId('hitl-row-42')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('hitl-row-42'))
    expect(screen.getByTestId('hitl-retry-42')).toBeDisabled()
  })

  it('retry button is enabled when textarea has text', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockItems),
    })

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByTestId('hitl-row-42')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('hitl-row-42'))

    const textarea = screen.getByTestId('hitl-textarea-42')
    fireEvent.change(textarea, { target: { value: 'Fix the tests' } })
    expect(screen.getByTestId('hitl-retry-42')).not.toBeDisabled()
  })

  it('calls correct API on retry click', async () => {
    const fetchMock = vi.fn()
    // First call: fetchHITL
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockItems),
    })
    // Second call: POST correction
    fetchMock.mockResolvedValueOnce({ ok: true })
    // Third call: refetch after action
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockItems),
    })
    global.fetch = fetchMock

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByTestId('hitl-row-42')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('hitl-row-42'))

    const textarea = screen.getByTestId('hitl-textarea-42')
    fireEvent.change(textarea, { target: { value: 'Fix the tests' } })
    fireEvent.click(screen.getByTestId('hitl-retry-42'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/hitl/42/correct', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ correction: 'Fix the tests' }),
      })
    })
  })

  it('calls correct API on skip click', async () => {
    const fetchMock = vi.fn()
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockItems),
    })
    fetchMock.mockResolvedValueOnce({ ok: true })
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([]),
    })
    global.fetch = fetchMock

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByTestId('hitl-row-42')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('hitl-row-42'))
    fireEvent.click(screen.getByTestId('hitl-skip-42'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/hitl/42/skip', {
        method: 'POST',
      })
    })
  })

  it('calls correct API on close click with confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    const fetchMock = vi.fn()
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockItems),
    })
    fetchMock.mockResolvedValueOnce({ ok: true })
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([]),
    })
    global.fetch = fetchMock

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByTestId('hitl-row-42')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('hitl-row-42'))
    fireEvent.click(screen.getByTestId('hitl-close-42'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/hitl/42/close', {
        method: 'POST',
      })
    })
  })

  it('does not call close API when confirmation is cancelled', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)

    const fetchMock = vi.fn()
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockItems),
    })
    global.fetch = fetchMock

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByTestId('hitl-row-42')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('hitl-row-42'))
    fireEvent.click(screen.getByTestId('hitl-close-42'))

    // Only the initial fetch should have been called
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('shows item count in header', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockItems),
    })

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByText('2 issues stuck on CI')).toBeInTheDocument()
    })
  })

  it('shows singular form for one item', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([mockItems[0]]),
    })

    render(<HITLTable />)

    await waitFor(() => {
      expect(screen.getByText('1 issue stuck on CI')).toBeInTheDocument()
    })
  })
})
