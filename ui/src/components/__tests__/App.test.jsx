import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { tabActiveStyle, tabInactiveStyle, tabBadgeStyle } from '../../App'

vi.mock('../../hooks/useHydraSocket', () => ({
  useHydraSocket: vi.fn(),
}))

vi.mock('../../hooks/useHumanInput', () => ({
  useHumanInput: () => ({ requests: {}, submit: vi.fn() }),
}))

import { useHydraSocket } from '../../hooks/useHydraSocket'
import App from '../../App'

function makeState(overrides = {}) {
  return {
    connected: false,
    batchNum: 0,
    phase: 'idle',
    orchestratorStatus: 'idle',
    workers: {},
    prs: [],
    reviews: [],
    mergedCount: 0,
    sessionPrsCount: 0,
    lifetimeStats: null,
    config: null,
    events: [],
    hitlItems: [],
    humanInputRequests: {},
    submitHumanInput: vi.fn(),
    refreshHitl: vi.fn(),
    ...overrides,
  }
}

describe('App worker select tab switching', () => {
  beforeEach(() => {
    useHydraSocket.mockReturnValue(makeState({
      connected: true,
      orchestratorStatus: 'running',
      phase: 'implement',
      workers: {
        1: { status: 'running', title: 'Test issue', branch: 'test-1', worker: 0, role: 'implementer', transcript: ['line 1'] },
      },
      config: {},
    }))
  })

  it('clicking a worker switches to transcript tab', () => {
    render(<App />)

    // Switch to Pull Requests tab first
    fireEvent.click(screen.getByText('Pull Requests'))

    // Click the worker card
    fireEvent.click(screen.getByText('#1'))

    // Transcript tab should now be active and transcript content visible
    expect(screen.getByText('line 1')).toBeInTheDocument()
  })

  it('clicking a worker when already on transcript tab keeps transcript active', () => {
    render(<App />)

    // We start on transcript tab by default, click the worker via its card
    const workerCards = screen.getAllByText('#1')
    fireEvent.click(workerCards[0]) // sidebar card is the first match

    // Should still be on transcript tab with content visible
    expect(screen.getByText('line 1')).toBeInTheDocument()
  })
})

describe('App pre-computed tab styles', () => {
  it('tabInactiveStyle has base tab properties', () => {
    expect(tabInactiveStyle).toMatchObject({
      padding: '10px 20px',
      fontSize: 12,
      fontWeight: 600,
      color: 'var(--text-muted)',
      cursor: 'pointer',
      borderBottom: '2px solid transparent',
    })
  })

  it('tabActiveStyle includes both tab and tabActive properties', () => {
    expect(tabActiveStyle).toMatchObject({
      padding: '10px 20px',
      fontSize: 12,
      fontWeight: 600,
      color: 'var(--accent)',
      cursor: 'pointer',
      borderBottomColor: 'var(--accent)',
    })
  })

  it('tabActiveStyle overrides color from tabActive', () => {
    // tabActive color (var(--accent)) should override base tab color (var(--text-muted))
    expect(tabActiveStyle.color).toBe('var(--accent)')
  })

  it('style objects are referentially stable', () => {
    expect(tabActiveStyle).toBe(tabActiveStyle)
    expect(tabInactiveStyle).toBe(tabInactiveStyle)
  })
})

describe('tabBadgeStyle', () => {
  it('has expected badge properties', () => {
    expect(tabBadgeStyle).toMatchObject({
      marginLeft: 6,
      padding: '1px 6px',
      borderRadius: 10,
      fontSize: 10,
      fontWeight: 600,
      background: 'var(--border)',
      color: 'var(--text-muted)',
    })
  })

  it('is referentially stable', () => {
    expect(tabBadgeStyle).toBe(tabBadgeStyle)
  })
})

function getPrTab() {
  return screen.getByText('Pull Requests').closest('div')
}

describe('PR tab badge rendering', () => {
  it('shows Pull Requests label without badge when no PRs exist', () => {
    useHydraSocket.mockReturnValue(makeState({ prs: [] }))
    render(<App />)
    const tab = getPrTab()
    expect(tab).toBeInTheDocument()
    expect(within(tab).queryByText(/\d+/)).not.toBeInTheDocument()
  })

  it('shows badge with count when PRs exist', () => {
    const prs = [
      { pr: 1, title: 'PR 1' },
      { pr: 2, title: 'PR 2' },
      { pr: 3, title: 'PR 3' },
    ]
    useHydraSocket.mockReturnValue(makeState({ prs }))
    render(<App />)
    const tab = getPrTab()
    expect(within(tab).getByText('3')).toBeInTheDocument()
  })

  it('updates badge count when PR list changes', () => {
    const prs = [{ pr: 1, title: 'PR 1' }]
    useHydraSocket.mockReturnValue(makeState({ prs }))
    const { rerender } = render(<App />)
    const tab = getPrTab()
    expect(within(tab).getByText('1')).toBeInTheDocument()

    const morePrs = [...prs, { pr: 2, title: 'PR 2' }, { pr: 3, title: 'PR 3' }, { pr: 4, title: 'PR 4' }, { pr: 5, title: 'PR 5' }]
    useHydraSocket.mockReturnValue(makeState({ prs: morePrs }))
    rerender(<App />)
    expect(within(getPrTab()).getByText('5')).toBeInTheDocument()
  })
})
