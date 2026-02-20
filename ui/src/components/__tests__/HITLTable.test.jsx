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
    status: 'from review',
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
  it('renders table with items', () => {
    render(<HITLTable items={mockItems} onRefresh={() => {}} />)
    expect(screen.getByText('#42')).toBeInTheDocument()
    expect(screen.getByText('Fix widget')).toBeInTheDocument()
    expect(screen.getByText('#99')).toBeInTheDocument()
    expect(screen.getByText('agent/issue-42')).toBeInTheDocument()
  })

  it('shows empty state when no items', () => {
    render(<HITLTable items={[]} onRefresh={() => {}} />)
    expect(screen.getByText('No stuck PRs')).toBeInTheDocument()
  })

  it('renders status column header', () => {
    render(<HITLTable items={mockItems} onRefresh={() => {}} />)
    expect(screen.getByText('Status')).toBeInTheDocument()
  })

  it('renders status badges for each item', () => {
    render(<HITLTable items={mockItems} onRefresh={() => {}} />)
    expect(screen.getByText('from review')).toBeInTheDocument()
    expect(screen.getByText('processing')).toBeInTheDocument()
  })

  it('renders from triage status badge', () => {
    const items = [{ ...mockItems[0], status: 'from triage' }]
    render(<HITLTable items={items} onRefresh={() => {}} />)
    expect(screen.getByText('from triage')).toBeInTheDocument()
  })

  it('renders from plan status badge', () => {
    const items = [{ ...mockItems[0], status: 'from plan' }]
    render(<HITLTable items={items} onRefresh={() => {}} />)
    expect(screen.getByText('from plan')).toBeInTheDocument()
  })

  it('renders from implement status badge', () => {
    const items = [{ ...mockItems[0], status: 'from implement' }]
    render(<HITLTable items={items} onRefresh={() => {}} />)
    expect(screen.getByText('from implement')).toBeInTheDocument()
  })

  it('renders unknown status with fallback styling without crashing', () => {
    const items = [{ ...mockItems[0], status: 'unknown-status' }]
    render(<HITLTable items={items} onRefresh={() => {}} />)
    expect(screen.getByText('unknown-status')).toBeInTheDocument()
  })

  it('expands row on click to show detail panel', () => {
    render(<HITLTable items={mockItems} onRefresh={() => {}} />)
    fireEvent.click(screen.getByTestId('hitl-row-42'))
    expect(screen.getByTestId('hitl-detail-42')).toBeInTheDocument()
    expect(screen.getByTestId('hitl-textarea-42')).toBeInTheDocument()
    expect(screen.getByTestId('hitl-retry-42')).toBeInTheDocument()
    expect(screen.getByTestId('hitl-skip-42')).toBeInTheDocument()
    expect(screen.getByTestId('hitl-close-42')).toBeInTheDocument()
  })

  it('collapses row on second click', () => {
    render(<HITLTable items={mockItems} onRefresh={() => {}} />)
    fireEvent.click(screen.getByTestId('hitl-row-42'))
    expect(screen.getByTestId('hitl-detail-42')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('hitl-row-42'))
    expect(screen.queryByTestId('hitl-detail-42')).not.toBeInTheDocument()
  })

  it('shows cause badge when cause is non-empty', () => {
    render(<HITLTable items={mockItems} onRefresh={() => {}} />)
    fireEvent.click(screen.getByTestId('hitl-row-42'))
    expect(screen.getByTestId('hitl-cause-42')).toBeInTheDocument()
    expect(screen.getByText('Cause: CI failure')).toBeInTheDocument()
  })

  it('hides cause badge when cause is empty', () => {
    render(<HITLTable items={mockItems} onRefresh={() => {}} />)
    fireEvent.click(screen.getByTestId('hitl-row-10'))
    expect(screen.queryByTestId('hitl-cause-10')).not.toBeInTheDocument()
  })

  it('updates correction text area state', () => {
    render(<HITLTable items={mockItems} onRefresh={() => {}} />)
    fireEvent.click(screen.getByTestId('hitl-row-42'))
    const textarea = screen.getByTestId('hitl-textarea-42')
    fireEvent.change(textarea, { target: { value: 'Mock the DB' } })
    expect(textarea.value).toBe('Mock the DB')
  })

  it('retry button is disabled when textarea is empty', () => {
    render(<HITLTable items={mockItems} onRefresh={() => {}} />)
    fireEvent.click(screen.getByTestId('hitl-row-42'))
    expect(screen.getByTestId('hitl-retry-42')).toBeDisabled()
  })

  it('retry button is enabled when textarea has text', () => {
    render(<HITLTable items={mockItems} onRefresh={() => {}} />)
    fireEvent.click(screen.getByTestId('hitl-row-42'))
    const textarea = screen.getByTestId('hitl-textarea-42')
    fireEvent.change(textarea, { target: { value: 'Fix the tests' } })
    expect(screen.getByTestId('hitl-retry-42')).not.toBeDisabled()
  })

  it('calls correct API on retry click', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    global.fetch = fetchMock
    const onRefresh = vi.fn()

    render(<HITLTable items={mockItems} onRefresh={onRefresh} />)
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
    await waitFor(() => {
      expect(onRefresh).toHaveBeenCalled()
    })
  })

  it('calls correct API on skip click', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    global.fetch = fetchMock
    const onRefresh = vi.fn()

    render(<HITLTable items={mockItems} onRefresh={onRefresh} />)
    fireEvent.click(screen.getByTestId('hitl-row-42'))
    fireEvent.click(screen.getByTestId('hitl-skip-42'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/hitl/42/skip', {
        method: 'POST',
      })
    })
    await waitFor(() => {
      expect(onRefresh).toHaveBeenCalled()
    })
  })

  it('calls correct API on close click with confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    global.fetch = fetchMock
    const onRefresh = vi.fn()

    render(<HITLTable items={mockItems} onRefresh={onRefresh} />)
    fireEvent.click(screen.getByTestId('hitl-row-42'))
    fireEvent.click(screen.getByTestId('hitl-close-42'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/hitl/42/close', {
        method: 'POST',
      })
    })
    await waitFor(() => {
      expect(onRefresh).toHaveBeenCalled()
    })
  })

  it('does not call close API when confirmation is cancelled', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const fetchMock = vi.fn()
    global.fetch = fetchMock

    render(<HITLTable items={mockItems} onRefresh={() => {}} />)
    fireEvent.click(screen.getByTestId('hitl-row-42'))
    fireEvent.click(screen.getByTestId('hitl-close-42'))
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows item count in header', () => {
    render(<HITLTable items={mockItems} onRefresh={() => {}} />)
    expect(screen.getByText('2 issues stuck on CI')).toBeInTheDocument()
  })

  it('shows singular form for one item', () => {
    render(<HITLTable items={[mockItems[0]]} onRefresh={() => {}} />)
    expect(screen.getByText('1 issue stuck on CI')).toBeInTheDocument()
  })

  it('refresh button calls onRefresh prop', () => {
    const onRefresh = vi.fn()
    render(<HITLTable items={mockItems} onRefresh={onRefresh} />)
    fireEvent.click(screen.getByText('Refresh'))
    expect(onRefresh).toHaveBeenCalledOnce()
  })

  it('does not fetch data on mount (no side effects)', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    render(<HITLTable items={[]} onRefresh={() => {}} />)
    expect(fetchSpy).not.toHaveBeenCalled()
    fetchSpy.mockRestore()
  })

  it('shows "No PR" when pr is 0', () => {
    render(<HITLTable items={mockItems} onRefresh={() => {}} />)
    expect(screen.getByText('No PR')).toBeInTheDocument()
  })

  it('container has overflowX auto for horizontal scrolling', () => {
    render(<HITLTable items={mockItems} onRefresh={() => {}} />)
    const table = screen.getByText('Fix widget').closest('table')
    const container = table.parentElement
    expect(container.style.overflowX).toBe('auto')
  })

  it('table has minWidth to prevent column squishing', () => {
    render(<HITLTable items={mockItems} onRefresh={() => {}} />)
    const table = screen.getByText('Fix widget').closest('table')
    expect(table.style.minWidth).toBe('600px')
  })
})
